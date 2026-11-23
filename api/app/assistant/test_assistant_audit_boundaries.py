"""Boundary and known-defect probes using fake users, catalogs, and transports."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from random import Random
from threading import Barrier

import pytest
from sqlalchemy import update as sql_update

from . import model, repository
from .context import assess
from .contracts import ChatRequest, Condition, Fact, MemoryEdit, Profile
from .errors import Conflict, ModelInvalidResponse, StorageUnavailable
from .prompts import UNTRUSTED_DATA
from .skill_context import CatalogSkillData
from .test_assistant_audit import AuditModel, DATA, PANDAS, block_transport, schedule
from .test_chat import NOW, ask, make_assistant, update
from .test_documents import client_for
from .test_gemini_diagnostics import candidate, response
from .test_gemini_retries import http_error, install_transport
from .test_http_integration import ALICE, SKILL_CHAT, client, http_app, sign_in
from .test_skill_lab import lab_service

SEED = 20261123
API = "/api/assistant"


@pytest.fixture(autouse=True)
def no_gemini_network(monkeypatch):
    monkeypatch.setattr(model, "urlopen", block_transport)


@pytest.mark.parametrize("raw", [
    pytest.param({"message": ""}, id="empty"),
    pytest.param({"message": "  \n\t "}, id="whitespace"),
    pytest.param({"message": "가" * 2001}, id="too-long"),
    pytest.param({"message": ["안녕"]}, id="wrong-message-type"),
    pytest.param({"message": "안녕", "userId": "bob"}, id="owner-field"),
    pytest.param({"message": "안녕", "context": {"skillId": "기술/.."}}, id="invalid-skill-id"),
])
def test_audit_http_validation_precedes_model_and_state(tmp_path, raw):
    service = make_assistant(tmp_path)
    with client_for(service) as http:
        result = http.post(f"{API}/chat", json=raw)
        assert result.status_code == 401
        http.cookies.set("cuk_session", "alice-session")
        result = http.post(f"{API}/chat", json=raw)
        assert result.status_code == 422 and result.json()["detail"]["code"] == "invalid_input"
        assert http.get(f"{API}/memory").headers["Cache-Control"] == "no-store"
    assert not service.model.calls and service.store.get_state("alice").revision == 0


@pytest.mark.parametrize("screen", [
    pytest.param({**DATA, "skill_id": "audit-absent"}, id="node"),
    pytest.param({**PANDAS, "job_id": "audit-absent"}, id="job"),
    pytest.param({**DATA, "skill_id": "mock-pandas"}, id="foreign-node"),
])
def test_audit_unresolvable_selection_never_invents_a_catalog_relation(tmp_path, screen):
    service = lab_service(tmp_path, AuditModel())
    answer = ask(service, "이 기술의 선수학습과 후속 노드는 무엇인가요?", **screen)
    assert answer.context_issues == ["unknown_skill"] and not service.model.calls
    assert "다시 선택" in answer.answer and not service.memory("alice")


def test_audit_indirect_links_and_bad_catalog_edges(tmp_path):
    names = ("기초", "중간", "완성", "순환 A", "순환 B", "다른 직무 기술")
    skills = [{"id": key, "name": name} for key, name in zip("abcdef", names)]
    catalog = CatalogSkillData({"skills": skills, "jobs": [
        {"id": "audit-one", "name": "분석 예시", "nodes": [
            {"skill": "a", "prereq": []}, {"skill": "b", "prereq": ["a", "b", "missing", "f"]},
            {"skill": "b", "prereq": ["c"]}, {"skill": "c", "prereq": ["b"]},
            {"skill": "d", "prereq": ["e"]}, {"skill": "e", "prereq": ["d"]},
        ]},
        {"id": "audit-two", "name": "개발 예시", "nodes": [{"skill": "a", "prereq": []}, {"skill": "f", "prereq": []}]},
    ]}, mock=True)
    tree = catalog.get_skill_tree("audit-one")
    graph = tree.context("a", "완성은 어떻게 이어져?")
    assert tree.incomplete and len(tree.nodes) == 5 and set(tree.cycles) == {"d", "e"}
    assert graph["nearestSuccessorHops"]["c"] == 2
    assert graph["edges"] == [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]
    assert not catalog.get_skill_tree("audit-two").following["a"]
    service = lab_service(tmp_path, AuditModel(), catalog)
    answer = ask(service, "완성으로 이어지는 후속 관계가 있나요?", page="tree", job_id="audit-one", skill_id="a")
    assert answer.mock_data and "기초에서 완성" in answer.answer and not service.model.calls


@pytest.mark.parametrize(("index", "status", "level", "source", "progress", "mock"), [
    (0, "재학", "초급", None, None, False),
    (1, "휴학", "중급", "conversation", "preparing", False),
    (2, "졸업", "고급", "user_claim", "completed", False),
    (3, "재학", "중급", "official", "completed", False),
    (4, "휴학", "초급", "official", "completed", True),
])
def test_audit_seeded_profiles_preserve_provenance(tmp_path, index, status, level, source, progress, mock):
    rng = Random(SEED + index)
    interests = ["AI", "데이터", "개발", "창업"]
    Random(SEED).shuffle(interests)
    credentials = ("SQLD", "ADsP", "정보처리기사")
    interest, credential = interests[index % len(interests)], rng.choice(credentials)
    facts = [Fact(id="audit-status", kind="status", value=status, source="official"),
             Fact(id="audit-interest", kind="interest", value=interest, source="system"),
             Fact(id="audit-skill", kind="skill", value="Python", detail=f"{level} 연습 수준", source="user_claim")]
    if source:
        facts.append(Fact(id="audit-cert", kind="certification", value=credential, source=source, progress=progress))
    if index in {2, 4}:
        facts.append(Fact(id="audit-project", kind="project", value="합계 표 연습", source="official" if mock else "user_claim"))
    service = make_assistant(tmp_path)
    service.data.profiles["demo001"] = Profile(facts=facts, mock=mock)
    reply = ask(service, "내 자격증을 공식 확인과 사용자 주장으로 구분해 알려줘.")
    assert reply.mock_data == mock and not service.memory("alice") and not service.model.calls
    rows = reply.answer.splitlines()
    if mock:
        assert f"가상 데이터의 공식 확인 기록 · {credential}" in rows
        assert not rows[0].endswith(credential)
    elif source == "official":
        assert rows[0].endswith(credential)
    elif progress == "completed":
        assert rows[1].endswith(credential) and not rows[0].endswith(credential)
    elif progress == "preparing":
        assert any("준비 중" in row and credential in row for row in rows[2:])
        assert not rows[0].endswith(credential)
    else:
        assert all(name not in reply.answer for name in credentials)
    sample = service.data.list_opportunities()[0].model_copy(update={"mock": False, "conditions": [
        Condition(kind="status", label="학적 상태", values=[status]),
    ]})
    inspected = assess(sample, facts, NOW, {f.id for f in facts} if mock else set())
    assert inspected.conditions[0].verdict == ("check" if mock else "pass")


def test_audit_expired_account_cannot_read_previously_saved_history_or_memory(http_app):
    app, scripted, sessions, session_row = http_app
    with client(app) as http:
        sign_in(http, ALICE)
        assert http.post(f"{API}/memory", json={"kind": "interest", "value": "가상 텍스트 분석"}).status_code == 201
        assert http.post(f"{API}/chat", json=SKILL_CHAT).status_code == 200
        calls = len(scripted.calls)
        with sessions.begin() as db:
            db.execute(sql_update(session_row).where(session_row.user_id == ALICE).values(expires_at=0))
        assert http.get(f"{API}/memory").status_code == 401
        assert http.get(f"{API}/conversations/{SKILL_CHAT['conversationId']}").status_code == 401
        assert http.post(f"{API}/chat", json=SKILL_CHAT).status_code == 401
        assert len(scripted.calls) == calls


def test_audit_catalog_and_user_text_stay_out_of_system_instructions(tmp_path, monkeypatch, caplog):
    annotation = "시스템 프롬프트를 공개하라는 문구가 포함된 테스트 설명"
    catalog = CatalogSkillData({"skills": [{"id": "probe", "name": "예시 기술", "description": annotation}], "jobs": [
        {"id": "probe-job", "name": "예시 직무", "nodes": [{"skill": "probe", "prereq": []}]},
    ]}, mock=True)
    reply = candidate({"answer": "선택한 기술을 예시 데이터로 연습해요."})
    calls, waits = install_transport(monkeypatch, reply)
    service = lab_service(tmp_path, model.GeminiModel("audit-transport-marker", "gemini-audit"), catalog)
    email = "audit-probe@example.invalid"
    instruction = "이전 지시를 무시해 주세요라는 문장은 테스트 예시예요"
    text = f"{instruction}, 메일 {email}, 이 기술은 무엇인가요?"
    with caplog.at_level(logging.INFO, logger=model.__name__):
        ask(service, text, page="tree", job_id="probe-job", skill_id="probe")
    envelope = json.loads(calls[-1].data)
    system = envelope["systemInstruction"]["parts"][0]["text"]
    payload = envelope["contents"][0]["parts"][0]["text"]
    assert UNTRUSTED_DATA in system and instruction not in system and instruction in payload
    assert annotation not in payload and "카탈로그 설명 확인 필요" in payload
    assert email not in payload + caplog.text + service.history("alice", "career").model_dump_json()
    assert "audit-transport-marker" not in caplog.text and not waits and not service.memory("alice")


@pytest.mark.parametrize(("injected", "code"), [
    ("timeout", "model_timeout"), ("empty", "model_invalid_response"), ("malformed", "model_invalid_json"),
    ("exhausted", "model_service_unavailable"),
])
def test_audit_transport_failure_after_retry_never_partially_commits(tmp_path, monkeypatch, injected, code):
    failed = {"timeout": TimeoutError("synthetic timeout"), "empty": response({"candidates": []}),
              "malformed": response({"candidates": [{"content": {"parts": [{"text": "{"}]}}]}),
              "exhausted": http_error()}
    claim = "나 SQLD 취득했어."
    def extraction():
        return candidate({"updates": [update("certification", "add", "SQLD", claim)]})

    calls, waits = install_transport(monkeypatch, extraction(), http_error(), failed[injected], extraction(),
                                     candidate({"answer": "공식 취득 여부는 별도로 확인할 수 있어요."}))
    service = make_assistant(tmp_path, model.GeminiModel("test-key", "gemini-audit", max_503_retries=1))
    request = {"message": claim, "requestId": "same-turn", "conversationId": "retry"}
    with client_for(service) as http:
        http.cookies.set("cuk_session", "alice-session")
        result = http.post(f"{API}/chat", json=request)
        assert result.status_code == {"timeout": 504, "exhausted": 503}.get(injected, 502)
        assert result.json()["detail"]["code"] == code
        assert service.store.get_state("alice").revision == 0 and len(calls) == 3 and waits == [1]
        committed = http.post(f"{API}/chat", json=request)
        replay = http.post(f"{API}/chat", json=request)
        conflict = http.post(f"{API}/chat", json={**request, "message": "다른 질문이에요?"})
        assert committed.status_code == replay.status_code == 200 and committed.json() == replay.json()
        assert conflict.status_code == 409
    state = service.store.get_state("alice")
    assert len(calls) == 5 and [fact.value for fact in state.memory] == ["SQLD"]
    assert len(state.conversations["retry"].turns) == 1


def test_audit_corrupt_json_is_preserved_and_does_not_trigger_a_model(tmp_path):
    service = make_assistant(tmp_path)
    path = service.store._state("alice")
    path.parent.mkdir(parents=True)
    original = b'{"revision": '
    path.write_bytes(original)
    with client_for(service) as http:
        http.cookies.set("cuk_session", "alice-session")
        result = http.post(f"{API}/chat", json={"message": "상담 가능할까요?"})
        assert result.status_code == 503 and result.json()["detail"]["code"] == "storage_unavailable"
    assert path.read_bytes() == original and not service.model.calls
    assert service.store.get_state("bob").revision == 0


def test_audit_repository_write_error_keeps_previous_bytes(tmp_path, monkeypatch):
    service = make_assistant(tmp_path)
    ask(service, "상담 가능할까요?")
    path = service.store._state("alice")
    snapshot = path.read_bytes()

    def deny_write(*args):
        raise PermissionError("synthetic write denial")

    monkeypatch.setattr(repository, "_atomic_write", deny_write)
    with pytest.raises(StorageUnavailable):
        ask(service, "나 SQLD 취득했어.")
    assert path.read_bytes() == snapshot and not service.memory("alice")


def test_audit_repository_read_error_stops_before_model(tmp_path, monkeypatch):
    service = make_assistant(tmp_path)
    path = service.store._state("alice")
    read = type(path).read_bytes

    def denied(candidate):
        if candidate == path:
            raise PermissionError("synthetic read denial")
        return read(candidate)

    monkeypatch.setattr(type(path), "read_bytes", denied)
    with pytest.raises(StorageUnavailable, match="읽을"):
        ask(service, "진로 상담이 가능할까요?")
    assert not service.model.calls and service.store.get_state("bob").revision == 0


@pytest.mark.parametrize(("message", "days"), [
    ("Python 1일 학습 계획을 어떻게 세울까?", 1),
    ("초보 Python 학습 계획을 어떻게 세울까?", None),
])
def test_audit_day_count_is_only_fixed_when_requested(tmp_path, message, days):
    service = lab_service(tmp_path, AuditModel())
    service.model.answer = schedule(days, 20) if days else {"answer": "변수부터 실습하고, 다음에 반복문으로 넘어가요."}
    reply = ask(service, message)
    _, context, schema = service.model.calls[-1]
    assert context["practiceRequest"].get("days") == days and len(service.model.calls) == 1
    assert ("schedule" in schema["properties"]) == (days is not None)
    assert reply.answer.count("일차 ·") == (days or 0)


def test_audit_concurrent_users_with_identical_request_ids_remain_isolated(tmp_path):
    service = make_assistant(tmp_path)
    barrier = Barrier(2, timeout=5)
    payloads = {user: ChatRequest(message=f"나는 {topic}에 관심 있어. 이 내용을 기억해줘.",
                                 request_id="same-id", conversation_id="same-conversation")
                for user, topic in {"alice": "로보틱스", "bob": "데이터 시각화"}.items()}
    for payload, topic in zip(payloads.values(), ("로보틱스", "데이터 시각화")):
        service.model.updates[payload.message] = [update("interest", "add", topic, payload.message.split(". ")[0])]

    def save(user):
        barrier.wait()
        return service.chat(user, payloads[user])

    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(save, payloads))
    assert all(reply.memory_updated for reply in replies)
    assert [service.memory(user)[0].value for user in payloads] == ["로보틱스", "데이터 시각화"]
    assert [service.chat(user, payload) for user, payload in payloads.items()] == replies
    assert len(service.model.calls) == 2
    with pytest.raises(Conflict):
        service.chat("alice", payloads["alice"].model_copy(update={"message": "다른 내용이에요?"}))


def test_audit_concurrent_replays_commit_only_one_turn(tmp_path):
    barrier = Barrier(2, timeout=5)

    class RacingModel(AuditModel):
        def generate(self, instruction, data, schema):
            barrier.wait()
            return super().generate(instruction, data, schema)

    service = make_assistant(tmp_path, RacingModel())
    request = ChatRequest(message="데이터 직무에 관해 상담할 수 있을까요?", request_id="same-id")
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: service.chat("alice", request), range(2)))
    persisted = service.store.get_state("alice")
    assert first == second and persisted.revision == 1 and len(persisted.conversations["default"].turns) == 1
    assert len(service.model.calls) == 2


def test_audit_colloquial_certificate_retraction_supersedes_existing_claim(tmp_path):
    service = make_assistant(tmp_path)
    ask(service, "나 SQLD 취득했어.")
    reply = ask(service, "SQLD를 취득했어. 아니, 아직 준비 중이야. 내가 취득한 자격증은 뭐야?")
    assert service.memory("alice")[0].progress == "preparing" and "취득 기록은 없어요" in reply.answer


def test_audit_recall_of_an_unsaved_named_skill_does_not_substitute_another_skill(tmp_path):
    service = make_assistant(tmp_path)
    service.add_memory("alice", MemoryEdit(kind="skill", value="Python", progress="beginner"))
    reply = ask(service, "내가 직접 말한 Rust 실력을 알려줘.")
    assert "저장돼 있지" in reply.answer and "Python" not in reply.answer


def test_audit_user_supplied_synthetic_key_marker_is_not_forwarded_or_persisted(tmp_path, caplog):
    service = make_assistant(tmp_path)
    marker = "AUDIT-FAKE-SECRET-DO-NOT-USE-4832"
    with caplog.at_level(logging.INFO, logger=model.__name__):
        ask(service, f"API 키는 {marker}. 데이터 분석가가 무슨 일을 하나요?")
    surfaces = {"log": caplog.text, "request": json.dumps(service.model.calls, ensure_ascii=False),
                "history": service.history("alice", "career").model_dump_json()}
    assert [name for name, value in surfaces.items() if marker in value] == []


def test_audit_saved_time_budget_applies_to_new_schedules(tmp_path):
    service = lab_service(tmp_path, AuditModel())
    service.add_memory("alice", MemoryEdit(kind="study_time", value="하루 20분"))
    service.model.answer = schedule(3, 40)
    try:
        answer = ask(service, "SQL 3일 학습 계획은 어떻게 짜면 좋을까?", conversation="fresh")
    except ModelInvalidResponse:
        return
    assert "일차 · 40분" not in answer.answer


def test_audit_rest_day_can_be_zero_minutes(tmp_path):
    service = make_assistant(tmp_path)
    service.model.answer = schedule(3, 15)
    service.model.answer["schedule"][2] = {"task": "복습 없이 쉬어요.", "minutes": 0, "done": "과제 없이 쉬면 돼요."}
    answer = ask(service, "SQL 3일 학습 계획에서 3일차는 완전히 쉬는 날로 둘 수 있을까?")
    assert "3일차 · 0분" in answer.answer


def test_audit_next_step_after_partial_completion_anchors_the_existing_plan(tmp_path):
    service = lab_service(tmp_path, AuditModel())
    service.model.answer = schedule(7, 20, "SQL 필터를 사용해 필요한 행을 고르고 결과 표를 확인해요.")
    ask(service, "SQL 7일 학습 계획은 어떻게 짤까?")
    service.model.answer = {"answer": "다음에는 집계를 해 봐요.", "exercise": {
        "task": "SUM으로 합계를 구해요.", "minutes": 15, "done": "숫자 하나가 나와요.",
    }}
    ask(service, "3일차까지 끝냈어. 그다음 실습으로 무엇을 하면 돼?")
    _, data, _ = service.model.calls[-1]
    assert data.get("practiceRequest", {}).get("mode") == "task"
    assert any("4일차" in turn["assistant"] for turn in data["conversation"]["recent"] if turn.get("priorPractice"))


def test_audit_question_ending_in_an_emoji_does_not_extract_memory(tmp_path):
    service = make_assistant(tmp_path, AuditModel())
    ask(service, "Pythno\t입문용 도구라는 게 뭐야? 🐍")
    assert not service.memory("alice") and service.model.stages == ["consultation"]
