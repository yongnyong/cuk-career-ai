"""Adjacent regressions for the seven assistant audit fixes (offline)."""

import json
import logging
from urllib.error import URLError

import pytest

from . import model
from .contracts import Fact, MemoryEdit, Profile
from .errors import AssistantError, ModelInvalidResponse
from .privacy import redact
from .test_assistant_audit import AuditModel, block_transport, schedule
from .test_chat import ask, make_assistant, update
from .test_documents import client_for
from .test_gemini_retries import install_transport


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(model, "urlopen", block_transport)


@pytest.mark.parametrize(("text", "value"), [
    ("X-API-Key: synthetic-header_4832", "synthetic-header_4832"),
    ("Authorization: Bearer synthetic-token_4832", "synthetic-token_4832"),
    ('DB_PASSWORD="가상 암호 4832"', "가상 암호 4832"),
    ('{"client_secret": "synthetic client value 4832"}', "synthetic client value 4832"),
    ("https://example.invalid?access_token=synth-query_4832&mode=read", "synth-query_4832"),
    ("GEMINI_API_KEY=synthetic-env_4832", "synthetic-env_4832"),
    ("sk-auditfixtureplaceholder4832예요.", "sk-auditfixtureplaceholder4832"),
    ("-----BEGIN PRIVATE KEY-----\nYXVkAW5vbnJlYWx4bG9uZ2RhdGE=\n-----END PRIVATE KEY-----",
     "YXVkAW5vbnJlYWx4bG9uZ2RhdGE="),
])
def test_credential_formats_are_masked_without_erasing_the_rest(text, value):
    safe = redact(f"{text}\n이 기술은 무엇을 하나요?")
    assert value not in safe and "[비밀정보 삭제]" in safe and safe.endswith("이 기술은 무엇을 하나요?")
    assert redact(safe) == safe


def test_legitimate_technology_explanation_remains_readable():
    text = ("API 키는 인증에 쓰여요. 토큰은 문장을 나눈 단위예요. Authorization: Bearer <ACCESS_TOKEN>은 헤더 예시예요. "
            "-----BEGIN PRIVATE KEY-----는 PEM 시작 표지예요.")
    assert redact(text) == text


def test_credential_is_not_forwarded_saved_or_echoed_by_chat(tmp_path):
    service = make_assistant(tmp_path, AuditModel())
    marker = "synthetic-auth_4832"
    message = f"Authorization: Bearer {marker}\n{marker}\n진로 상담은 어떻게 하나요?"
    service.model.answer = {"answer": f"진로를 차근히 살펴봐요. {marker}"}
    service.model.updates[message] = [update("interest", "add", marker, marker)]
    result = ask(service, message)
    assert marker not in result.answer and "진로" in result.answer
    assert marker not in json.dumps(service.model.calls, ensure_ascii=False)
    assert marker not in service.store._state("alice").read_text(encoding="utf-8")
    assert not service.memory("alice")
    with pytest.raises(AssistantError, match="저장할 수 없어요"):
        service.add_memory("alice", MemoryEdit(kind="interest", value="데이터 분석", detail=f"password={marker}"))


def test_failed_transport_redacts_input_and_keeps_exception_details_private(tmp_path, monkeypatch, caplog):
    key = "synthetic-input_4832"
    calls, _ = install_transport(monkeypatch, URLError(f"synthetic provider detail including {key}"))
    service = make_assistant(tmp_path, model.GeminiModel("synthetic-config-key", "gemini-fixture"))
    with client_for(service) as http, caplog.at_level(logging.INFO, logger=model.__name__):
        http.cookies.set("cuk_session", "alice-session")
        reply = http.post("/api/assistant/chat", json={"message": f"access_token={key}\n데이터 분석이 뭐야?"})
    assert reply.status_code == 503 and reply.json()["detail"]["code"] == "model_network_error"
    assert len(calls) == 1 and key not in calls[0].data.decode()
    assert key not in reply.text + caplog.text and "synthetic-config-key" not in caplog.text
    assert service.store.get_state("alice").revision == 0


def test_legacy_read_view_masks_linked_secret_without_rewriting_old_turns(tmp_path):
    service = make_assistant(tmp_path, AuditModel())
    marker = "synthetic-legacy_4832"
    ask(service, "진로 상담 가능한가요?")
    state = service.store.get_state("alice")
    old = state.conversations["career"].turns[0]
    old.message = f"client_secret={marker}"
    old.result.answer = f"적어주신 값은 {marker}예요."
    state.memory.append(Fact(id="legacy", kind="interest", value=marker, source="conversation"))
    service.store.save_state("alice", state)
    path = service.store._state("alice")
    original = path.read_bytes()
    assert marker not in service.history("alice", "career").model_dump_json()
    assert not service.memory("alice") and path.read_bytes() == original
    ask(service, "어떤 직무가 있나요?")
    assert marker not in json.dumps(service.model.calls[-1], ensure_ascii=False)
    ask(service, "진로 상담을 시작할 수 있나요?", conversation="fresh")
    assert marker not in json.dumps(service.model.calls[-1], ensure_ascii=False)
    still_stored = service.store.get_state("alice")
    assert still_stored.conversations["career"].turns[0] == old and still_stored.memory[0].value == marker


def test_short_correction_keeps_prior_turn_and_independent_official_evidence(tmp_path):
    service = make_assistant(tmp_path, AuditModel())
    verified = Fact(id="issuer", kind="certification", value="ADsP", source="official", progress="completed")
    service.data.profiles["demo001"] = Profile(facts=[verified])
    claim = "나 ADsP에 합격했어."
    service.model.updates[claim] = [update("certification", "add", "ADsP", claim, progress="completed")]
    ask(service, claim)
    memory_id = service.memory("alice")[0].id
    reply = ask(service, "아뇨, 아직 시험 준비 중이에요. 내가 취득한 자격증은 뭐야?")
    [fact] = service.memory("alice")
    assert (fact.id, fact.progress, fact.source) == (memory_id, "preparing", "conversation")
    assert "공식 확인 기록 · ADsP" in reply.answer and "서로 달라요" in reply.answer
    assert service.data.get_profile("alice").facts == [verified]
    assert service.history("alice", "career").turns[0].message == claim


def test_short_correction_does_not_guess_between_two_credentials(tmp_path):
    service = make_assistant(tmp_path)
    claim = "나 SQLD랑 ADsP를 취득했어."
    message = f"{claim} 아니, 아직 준비 중이야. 내가 취득한 자격증은 뭐야?"
    service.model.updates[message] = [update("certification", "add", value, claim, progress="completed")
                                     for value in ("SQLD", "ADsP")]
    reply = ask(service, message)
    assert reply.needs_confirmation and not service.memory("alice")


def test_named_skill_recall_does_not_substitute_other_sources(tmp_path):
    service = make_assistant(tmp_path)
    service.add_memory("alice", MemoryEdit(kind="skill", value="Python", progress="beginner"))
    service.data.profiles["demo001"] = Profile(facts=[
        Fact(id="issuer", kind="skill", value="Rust", source="official"),
        Fact(id="other", kind="skill", value="SQL", source="system"),
    ])
    result = ask(service, "내가 직접 이야기한 Rust의 실력을 알려줘. 공식 기록과 구분해줘.")
    assert "저장돼 있지" in result.answer and "공식 확인 기록에는 Rust" in result.answer
    assert "Python" not in result.answer and "SQL" not in result.answer
    general = ask(service, "내가 직접 이야기한 기술 수준을 알려줘.")
    assert "Python" in general.answer and not service.model.calls


def test_saved_budget_follows_user_and_latest_explicit_change_wins(tmp_path):
    service = make_assistant(tmp_path, AuditModel())
    service.add_memory("alice", MemoryEdit(kind="study_time", value="20분"))
    request = "SQL 3일 학습 계획은 어떻게 짜면 좋을까?"
    service.model.answer = schedule(3, 20)
    ask(service, request, conversation="first")
    assert service.model.calls[-1][1]["practiceRequest"]["dailyMinutes"] == 20
    limit = "이제 하루 30분 공부할 수 있어."
    change = f"{limit} {request}"
    service.model.updates[change] = [update("study_time", "set", "하루 30분", limit)]
    service.model.answer = schedule(3, 30)
    assert ask(service, change, conversation="change").memory_updated
    assert service.model.calls[-1][1]["practiceRequest"]["dailyMinutes"] == 30
    ask(service, request, conversation="fresh")
    assert service.model.calls[-1][2]["properties"]["schedule"]["items"]["properties"]["minutes"]["maximum"] == 30
    ask(service, request, user="bob", conversation="fresh")
    assert "dailyMinutes" not in service.model.calls[-1][1]["practiceRequest"]


@pytest.mark.parametrize("day", [None, {"task": "", "minutes": 0, "done": "쉬었어요."},
                                {"task": "함수를 구현해요.", "minutes": 0, "done": "테스트 완료"}])
def test_blank_or_unfinished_day_is_not_a_rest_day(tmp_path, day):
    service = make_assistant(tmp_path)
    service.model.answer = schedule(3, 15)
    service.model.answer["schedule"][2] = day
    with pytest.raises(ModelInvalidResponse):
        ask(service, "Python 3일 학습 계획에서 휴식도 어떻게 넣을까요?")
    assert not service.store.get_state("alice").conversations


def test_reported_progress_keeps_original_plan_and_does_not_certify_completion(tmp_path):
    service = make_assistant(tmp_path, AuditModel())
    service.model.answer = schedule(7, 15, "SQL 합계를 구하고 결과를 읽어요.")
    ask(service, "SQL 7일 학습 계획은 어떻게 세울까?")
    service.model.answer = {"answer": "내용을 나누어 연습해요."}
    for _ in range(7):
        ask(service, "개발자와 분석가의 업무 차이는 뭐야?")
    service.model.answer = {"answer": "4일차를 생각해 봐요.", "exercise": {
        "task": "SQL 집계를 연습해요.", "minutes": 15, "done": "결과가 숫자로 나와요.",
    }}
    ask(service, "3일차까지 끝냈어. 다음은?")
    ask(service, "다음은? 완료 기준도 알려줘.")
    _, data, schema = service.model.calls[-1]
    prior = [turn["assistant"] for turn in data["conversation"]["recent"] if turn.get("priorPractice")]
    assert len(prior) == 1 and "4일차" in prior[0] and "SQL 합계" in prior[0]
    assert data["practiceRequest"]["planDays"] == 7
    assert data["practiceRequest"]["reportedProgress"] == {"completedThroughDay": 3, "provenance": "user_statement"}
    assert "exercise" in schema["properties"]
    service.model.answer = {"answer": "7일차까지 마쳤다고 말씀하셨어요."}
    ask(service, "7일차까지 마쳤어. 다음은?")
    _, data, schema = service.model.calls[-1]
    assert data["practiceRequest"]["reportedProgress"]["completedThroughDay"] == 7
    assert data["practiceRequest"]["verify"] and "exercise" not in schema["properties"] and not service.memory("alice")


@pytest.mark.parametrize("tail", [" 🙂", "!  ", "?!…  ", "\n✨", " 1️⃣"])
def test_question_decoration_never_adds_a_memory_call(tmp_path, tail):
    service = make_assistant(tmp_path, AuditModel())
    ask(service, f"What does Python do?{tail}")
    assert service.model.stages == ["consultation"] and not service.memory("alice")


def test_decorated_question_followed_by_an_actual_fact_still_extracts(tmp_path):
    service = make_assistant(tmp_path, AuditModel())
    reply = ask(service, "Pandas가 뭔가요? 🙂\n나는 Python 기초 문법만 알아. 이 내용을 기억해줘.")
    assert reply.memory_updated and service.model.stages == ["memory"]
    [fact] = service.memory("alice")
    assert (fact.value, fact.progress, fact.source) == ("Python", "beginner", "conversation")
