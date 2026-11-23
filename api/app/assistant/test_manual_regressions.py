"""Reproduce the manual chat reports through offline Gemini HTTP fixtures."""

import json
import logging
import sys
from urllib.error import URLError

import pytest

from . import demo, model
from .contracts import ChatRequest, Fact, MemoryEdit, Profile
from .test_chat import ask, make_assistant, update
from .test_documents import client_for, json_template
from .test_gemini_diagnostics import candidate
from .test_gemini_retries import http_error, install_transport

CORRECTION = "나 SQLD 자격증을 취득했어. 사실 취득한 건 아니고 지금 준비 중이야. 그럼 내가 취득한 자격증은 뭐야?"
COMPARISON = (
    "나는 인공지능학과 학생이고 데이터 분석에 관심이 있어. "
    "데이터 분석가와 데이터 엔지니어 중 무엇이 더 잘 맞을까? 추천 이유와 부족한 역량도 알려줘."
)
MOTIVATION = "데이터 분석 직무 지원동기를 300자 이내로 작성해줘. 내가 말하지 않은 프로젝트나 경력은 넣지 마."
FIRST_MOTIVATION = "데이터 분석 직무 지원동기를 300자 이내로 작성해줘.\n없는 경력은 만들지 마."
REVISION = "방금 작성한 지원동기를 120자 이내로 줄이고, SQLD는 취득한 것이 아니라 준비 중인 것으로 표현해줘."
REWRITE_FROM_DISCUSSION = "방금 이야기한 내 관심과 SQLD 준비 상태를 반영해서\n지원동기를 다시 작성해줘."
REWRITE_WITH_DETAILS = (
    "아까 데이터 분석 직무 지원동기를 300자 이내로\n다시 작성해줘. "
    "지금까지 말한 관심사와\nSQLD 준비 상태를 반영해줘."
)
FIT = "데이터 분석가와 데이터 엔지니어 중 무엇이 더 잘 맞을까?"


@pytest.mark.parametrize("shape", ["replace_only", "reordered", "stale_only", "empty"])
def test_same_turn_correction_uses_latest_assertion(monkeypatch, tmp_path, shape):
    assertion, correction, _ = CORRECTION.split(". ")
    earlier = update("certification", "add", "SQLD", assertion, progress="completed")
    later = update("certification", "replace", "", correction, progress="preparing")
    updates = {"replace_only": [later], "reordered": [later, earlier], "stale_only": [earlier], "empty": []}
    calls, _ = install_transport(monkeypatch, candidate({"updates": updates[shape]}))
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    service.add_memory("alice", MemoryEdit(kind="certification", value="ADsP"))

    reply = ask(service, CORRECTION)

    assert reply.memory_updated and not reply.needs_confirmation
    assert "SQLD · 준비 중" in reply.answer
    assert "확인이 필요한 기록 · ADsP" in reply.answer
    assert {fact.value: fact.progress for fact in service.memory("alice")} == {"ADsP": None, "SQLD": "preparing"}
    assert len(calls) == 1


def test_same_turn_correction_is_domain_generic_and_official_record_is_retained(tmp_path):
    service = make_assistant(tmp_path)
    issuer = Fact(id="issuer", kind="certification", value="정보처리기사", source="official")
    service.data.profiles["demo001"] = Profile(facts=[issuer])
    reply = ask(service, "나 정보처리기사에 합격했어. 사실 합격한 건 아니고 시험 준비 중이야. 내가 취득한 자격증은?")

    assert "공식 확인 기록 · 정보처리기사" in reply.answer and "현재 진술이 서로 달라요" in reply.answer
    [stored] = service.memory("alice")
    assert (stored.value, stored.progress, stored.source) == ("정보처리기사", "preparing", "conversation")
    assert service.data.get_profile("alice").facts == [issuer]


@pytest.mark.parametrize("message", [CORRECTION, CORRECTION.replace("아니고 지금", "아니고\n지금")])
def test_certificate_recall_after_draft_does_not_resume_writing(monkeypatch, tmp_path, message):
    calls, _ = install_transport(monkeypatch, candidate({"updates": []}))
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    assert ask(service, MOTIVATION).answer.startswith("[AI 초안]")
    assert "SQLD 자격증을 준비 중" in ask(service, REVISION).answer
    assert len(calls) == 0

    result = ask(service, message)
    assert "[AI 초안]" not in result.answer
    assert "SQLD · 준비 중" in result.answer and result.memory_updated
    assert service.history("alice", "career").turns[-1].narrative_prompt is None
    reloaded = make_assistant(tmp_path, service.model)
    assert [(fact.value, fact.progress) for fact in reloaded.memory("alice")] == [("SQLD", "preparing")]
    assert "SQLD · 준비 중" in ask(reloaded, "내가 취득한 자격증은?", conversation="fresh").answer
    assert reloaded.memory("bob") == [] and len(calls) == 1


def test_http_explicit_recall_preempts_selected_document_and_saves_corrected_fact(monkeypatch, tmp_path):
    calls, _ = install_transport(monkeypatch, candidate({"updates": []}))
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    cert = service.add_memory("alice", MemoryEdit(kind="certification", value="SQLD", progress="completed"))
    document = service.documents.upload("alice", "resume.json", json_template())
    http = client_for(service)
    http.cookies.set("cuk_session", "alice-session")
    screen = {"page": "documents", "documentId": document.id}
    first = http.post("/api/assistant/chat", json={
        "message": "이 이력서 양식을 내 정보로 작성해 줘.", "context": screen,
    })
    assert first.status_code == 200 and first.json()["document"]["revision"] == 1

    reply = http.post("/api/assistant/chat", json={"message": CORRECTION, "context": screen})
    assert reply.status_code == 200 and reply.json()["document"] is None
    assert reply.json()["memoryUpdated"] and "SQLD · 준비 중" in reply.json()["answer"]
    memory = http.get("/api/assistant/memory").json()
    assert [(item["id"], item["progress"]) for item in memory] == [(cert.id, "preparing")]
    assert service.documents.get("alice", document.id).draft.revision == 1
    http.cookies.set("cuk_session", "bob-session")
    assert http.get("/api/assistant/memory").json() == []
    assert "SQLD · 준비 중" not in http.post("/api/assistant/chat", json={
        "message": "내가 취득한 자격증은?",
    }).json()["answer"]
    assert len(calls) == 1


def test_switch_between_consultation_and_fresh_drafts_in_long_conversation(monkeypatch, tmp_path):
    calls, _ = install_transport(
        monkeypatch,
        candidate({"answer": "데이터 분석을 연습하려면 표를 집계해 보세요."}),
        candidate({"answer": "역량 점검은 작은 실습부터 시작해 보세요."}),
    )
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    assert "연습" in ask(service, "데이터 분석은 어떻게 공부할까?").answer
    assert "데이터 분석 직무" in ask(service, MOTIVATION).answer
    assert "SQLD" in ask(service, REVISION).answer

    result = ask(service, "데이터 분석가에게 어떤 역량이 부족한지 어떻게 확인할까?",
                 page="documents", document_id="stale-document")
    assert result.answer == "역량 점검은 작은 실습부터 시작해 보세요."
    assert result.document is None and len(calls) == 2
    context = json.loads(json.loads(calls[-1].data)["contents"][0]["parts"][0]["text"])
    history = context["conversation"]
    assert any("데이터 분석은 어떻게 공부할까" in turn["user"] for turn in history["recent"])
    assert "[AI 초안]" not in json.dumps(history, ensure_ascii=False) and "SQLD" not in str(history)

    new_draft = ask(service, "품질 관리 직무 지원동기를 새로 300자 이내로 작성해 줘.")
    assert "품질 관리 직무" in new_draft.answer and "SQLD" not in new_draft.answer
    assert "데이터 분석 직무" not in new_draft.answer


def test_cli_starts_new_conversation_and_uses_same_user_memory(monkeypatch, tmp_path, capsys):
    calls, _ = install_transport(monkeypatch, candidate({"updates": []}))
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    ask(service, MOTIVATION, user="demo001", conversation="default")
    monkeypatch.setattr(demo, "build_demo", lambda user, store: service)
    monkeypatch.setattr(sys, "argv", ["service", "--store", str(tmp_path)])
    inputs = iter([CORRECTION, "exit", "내가 취득한 자격증은?", "exit", "60자 이내로 줄여줘.", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    demo.main()
    demo.main()

    state = service.store.get_state("demo001")
    assert len(state.conversations) == 3 and len(state.conversations["default"].turns) == 1
    assert all(len(item.turns) == 1 for item in state.conversations.values())
    output = capsys.readouterr().out
    assert output.count("SQLD · 준비 중") == 2 and "[AI 초안]" not in output
    assert [(fact.value, fact.progress) for fact in state.memory] == [("SQLD", "preparing")]
    assert service.memory("demo002") == [] and len(calls) == 1

    monkeypatch.setattr(sys, "argv", ["service", "--store", str(tmp_path), "--conversation-id", "default"])
    demo.main()
    resumed = service.history("demo001", "default")
    assert len(resumed.turns) == 2 and resumed.turns[-1].result.answer.startswith("[AI 초안]")
    assert len(resumed.turns[-1].result.answer.splitlines()[1]) <= 60 and len(calls) == 1


def test_unclear_same_turn_correction_does_not_store_disputed_acquisitions(tmp_path):
    service = make_assistant(tmp_path)
    first = "SQLD와 ADsP를 취득했어."
    message = f"{first} 사실 취득한 건 아니고 준비 중이야. 내가 취득한 자격증은?"
    service.model.updates[message] = [
        update("certification", "add", name, first, progress="completed") for name in ("SQLD", "ADsP")
    ]
    result = ask(service, message)
    assert result.needs_confirmation and not result.memory_updated and not service.memory("alice")


def test_reported_comparison_returns_advice_and_remembers_evidence_in_one_call(monkeypatch, tmp_path, caplog):
    statement = COMPARISON.split(". ")[0]
    generated = {
        "answer": "현재 관심을 보면 데이터 분석가가 더 가까워요. 데이터 엔지니어는 파이프라인을 구축해요. "
                  "SQL과 데이터 모델링 경험은 아직 확인되지 않았으니 작은 실습으로 점검해 보세요.",
        "updates": [update("department", "set", "인공지능학과", statement),
                    update("interest", "add", "데이터 분석", statement)],
    }
    calls, _ = install_transport(monkeypatch, candidate(generated))
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))

    with caplog.at_level(logging.INFO, logger=model.__name__):
        reply = ask(service, COMPARISON)

    assert reply.memory_updated and "데이터 분석가가 더 가까워요" in reply.answer
    assert {(fact.kind, fact.value, fact.source) for fact in service.memory("alice")} == {
        ("department", "인공지능학과", "conversation"), ("interest", "데이터 분석", "conversation"),
    }
    [request] = calls
    body = json.loads(request.data)
    assert set(body["generationConfig"]["responseSchema"]["required"]) == {"answer", "updates"}
    payload = json.loads(body["contents"][0]["parts"][0]["text"])
    assert [role["name"] for role in payload["careerCandidates"]] == ["데이터 분석가"]
    assert "general industry context" in body["systemInstruction"]["parts"][0]["text"]
    assert len(request.data) < 7500
    assert "stage=consultation_with_memory" in caplog.text and "calls=1 attempts=1" in caplog.text
    assert "request_bytes=" in caplog.text and "timeout_ms=8000" in caplog.text
    for private in ("fixture-key", COMPARISON, "인공지능학과", "개인정보", "데이터 분석가"):
        assert private not in caplog.text


def test_comparison_surfaces_owned_interests_and_skill_evidence_even_with_generic_model_reply(monkeypatch, tmp_path):
    generic = "데이터 분석가는 지표를 해석하고, 데이터 엔지니어는 데이터 흐름을 구축해요."
    calls, _ = install_transport(monkeypatch, candidate({"answer": generic}), candidate({"answer": generic}))
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    service.data.profiles["demo001"] = Profile(facts=[Fact(id="confirmed-sql", kind="skill", value="SQL", source="official")])
    service.add_memory("alice", MemoryEdit(kind="interest", value="데이터 분석"))
    service.add_memory("alice", MemoryEdit(kind="goal", value="AI 엔지니어"))

    alice = ask(service, FIT, conversation="new-comparison")
    bob = ask(service, FIT, user="bob", conversation="new-comparison")

    assert "말씀하신 데이터 분석" in alice.answer and "데이터 분석가부터" in alice.answer
    assert "공식 기록에서 SQL 역량을 확인" in alice.answer and "데이터 시각화 역량은 어느 정도" in alice.answer
    assert " · " not in alice.answer and " / " not in alice.answer
    assert generic in alice.answer and "AI 엔지니어" not in alice.answer
    assert "판단하기 어려워요" in bob.answer and "공식 기록에서 SQL" not in bob.answer
    assert len(calls) == 2


@pytest.mark.parametrize("failure, status, code", [
    (TimeoutError("private upstream timeout"), 504, "model_timeout"),
    (URLError("private upstream network error"), 503, "model_network_error"),
])
def test_comparison_transport_errors_are_retryable_by_client_without_partial_state(
    monkeypatch, tmp_path, caplog, failure, status, code,
):
    calls, waits = install_transport(monkeypatch, failure, candidate({"answer": "비교 상담 답변", "updates": []}))
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    http = client_for(service)
    http.cookies.set("cuk_session", "alice-session")
    body = {"message": COMPARISON, "requestId": "comparison"}
    with caplog.at_level(logging.INFO, logger=model.__name__):
        error = http.post("/api/assistant/chat", json=body)
    assert error.status_code == status and error.json()["detail"]["code"] == code
    assert "다시" in error.json()["detail"]["message"]
    assert service.store.get_state("alice").revision == 0 and len(calls) == 1 and not waits
    assert "phase=upstream_open " in caplog.text and f"error={code}" in caplog.text
    assert "private upstream" not in caplog.text
    recovered = http.post("/api/assistant/chat", json=body)
    assert "비교 상담 답변" in recovered.json()["answer"]
    assert http.post("/api/assistant/chat", json=body).json() == recovered.json()
    assert service.store.get_state("alice").revision == 1 and len(calls) == 2


def test_retry_budget_counts_backoff_and_never_starts_an_attempt_after_expiry(monkeypatch, tmp_path, caplog):
    seconds = [0]
    timeouts = []
    pending = iter([http_error(), http_error()])

    def fetch(request, timeout):
        timeouts.append(timeout)
        seconds[0] += 4 if len(timeouts) == 1 else 2
        raise next(pending)

    monkeypatch.setattr(model, "monotonic", lambda: seconds[0])
    monkeypatch.setattr(model, "sleep", lambda delay: seconds.__setitem__(0, seconds[0] + delay))
    monkeypatch.setattr(model, "urlopen", fetch)
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture", timeout=6, request_budget=8))
    with caplog.at_level(logging.INFO, logger=model.__name__), pytest.raises(model.ModelServiceUnavailable):
        service.chat("alice", ChatRequest(message=COMPARISON))
    assert timeouts == [6, 3]
    assert service.store.get_state("alice").revision == 0
    assert "upstream_ms=6000 backoff_ms=1000 calls=1 attempts=2" in caplog.text


def test_separate_answer_has_only_remaining_budget_and_does_not_save_memory_on_timeout(monkeypatch, tmp_path):
    seconds = [0]
    limits = []
    claim = "나 SQLD 취득했어."

    def fetch(request, timeout):
        limits.append(timeout)
        if len(limits) == 1:
            seconds[0] = 7
            return candidate({"updates": [update("certification", "add", "SQLD", claim)]})
        raise TimeoutError

    monkeypatch.setattr(model, "urlopen", fetch)
    monkeypatch.setattr(model, "monotonic", lambda: seconds[0])
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    with pytest.raises(model.ModelTimeout):
        ask(service, claim)
    assert limits == [8, 5] and service.store.get_state("alice").revision == 0


def test_motivation_and_revision_with_or_without_previous_draft(monkeypatch, tmp_path):
    calls, _ = install_transport(monkeypatch)
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    first = ask(service, MOTIVATION)
    assert first.answer.startswith("[AI 초안]\n")
    assert "데이터 분석 직무" in first.answer.splitlines()[1] and len(first.answer.splitlines()[1]) <= 300
    assert "Campus Data Lab" not in first.answer and "가상 예시" not in first.answer
    assert "범위" in first.answer and first.answer.count("?") == 1

    service = make_assistant(tmp_path, service.model)
    for conversation in ("career", "no-draft"):
        revised = ask(service, REVISION, conversation=conversation)
        assert revised.answer.startswith("[AI 초안]\n")
        body = revised.answer.splitlines()[1]
        assert len(body) <= 120 and "SQLD 자격증을 준비 중" in body and "취득했습니다" not in body
        assert "Campus Data Lab" not in body
        if conversation == "career":
            assert "데이터 분석 직무" in body
            assert len(body) < len(first.answer.splitlines()[1])
    assert calls == [] and service.memory("alice") == []


@pytest.mark.parametrize("message", [
    FIRST_MOTIVATION,
    FIRST_MOTIVATION.replace("만들지 마", "만들어 내지 마"),
    "경력은 없고 데이터 분석 직무 지원동기를 300자 이내로 작성해줘.",
])
def test_first_draft_treats_unsupported_career_as_a_source_restriction(monkeypatch, tmp_path, message):
    calls, _ = install_transport(monkeypatch)
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))

    answer = ask(service, message).answer

    assert answer.startswith("[AI 초안]\n")
    assert "데이터 분석 직무" in answer.splitlines()[1] and len(answer.splitlines()[1]) <= 300
    assert "Campus Data Lab" not in answer and answer.count("?") == 1
    assert not calls


def test_rewrite_after_consultation_reuses_role_interest_and_preparation(monkeypatch, tmp_path):
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    assert "데이터 분석 직무" in ask(service, MOTIVATION).answer
    service.add_memory("alice", MemoryEdit(kind="interest", value="데이터 분석"))
    service.add_memory("alice", MemoryEdit(kind="certification", value="SQLD", progress="preparing"))
    skill = service.add_memory("alice", MemoryEdit(kind="skill", value="SQL", progress="beginner"))
    calls, _ = install_transport(
        monkeypatch, candidate({"answer": "데이터 분석부터 탐색해 볼 만해요."}), candidate({"factIds": [skill.id]}),
    )
    ask(service, FIT)
    service = make_assistant(tmp_path, service.model)

    result = ask(service, REWRITE_FROM_DISCUSSION)
    body = result.answer.splitlines()[1]

    assert result.answer.startswith("[AI 초안]\n") and len(body) <= 300
    assert "데이터 분석 직무" in body and "데이터 분석에 대한 관심" in body and "SQLD 자격증을 준비" in body
    assert "어떤 직무" not in result.answer and "취득했습니다" not in body
    assert "Campus Data Lab" not in body and len(calls) <= 2
    payload = json.loads(json.loads(calls[-1].data)["contents"][0]["parts"][0]["text"])
    assert payload["targetRole"] == "데이터 분석" and payload["maxCharacters"] == 300


def test_rewrite_with_trailing_instruction_stays_on_document_path(monkeypatch, tmp_path, caplog):
    statement = COMPARISON.split(". ")[0]
    calls, _ = install_transport(
        monkeypatch,
        candidate({"updates": []}),
        candidate({"answer": "두 직무의 차이를 고려해 보세요.",
                   "updates": [update("interest", "add", "데이터 분석", statement)]}),
        candidate({"updates": []}),
        candidate({"answer": "글을 직접 작성해 드리는 것은 지침에 따라 안내되지 않습니다."}),
    )
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    assert ask(service, FIRST_MOTIVATION).answer.startswith("[AI 초안]")
    assert "SQLD · 준비 중" in ask(service, CORRECTION).answer
    assert "두 직무의 차이" in ask(service, COMPARISON).answer
    count_before = len(calls)

    with caplog.at_level(logging.INFO, logger=model.__name__):
        revised = ask(service, REWRITE_WITH_DETAILS)

    assert revised.answer.startswith("[AI 초안]")
    body = revised.answer.splitlines()[1]
    assert "데이터 분석 직무" in body and "데이터 분석에 대한 관심" in body
    assert "아까" not in body and "SQLD 자격증을 준비" in body and len(body) <= 300
    assert len(calls) == count_before and "stage=memory" not in caplog.text and "stage=consultation" not in caplog.text
    assert "phase=draft_render" in caplog.text and "calls=0 attempts=0" in caplog.text
    reloaded = make_assistant(tmp_path, service.model)
    context = reloaded.history("alice", "career").turns[-1].narrative_context
    assert (context.target_role, context.max_characters, context.question) == ("데이터 분석", 300, "motivation")


def test_revise_change_role_and_shorten_after_other_topics(monkeypatch, tmp_path):
    calls, _ = install_transport(
        monkeypatch, candidate({"answer": "조인은 두 표의 값을 연결해요."}),
        candidate({"answer": "버전 관리에서 커밋은 변경을 기록해요."}),
    )
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    first = ask(service, "데이터 분석 직무 지원동기를 140~300자로 작성해줘.")
    assert 140 <= len(first.answer.splitlines()[1]) <= 300
    ask(service, "SQL 조인은 무엇인가요?")
    changed = ask(service, "앞서 초안의 지원 직무를 데이터 엔지니어로 바꿔줘.")
    assert "데이터 엔지니어 직무" in changed.answer and "데이터 분석 직무" not in changed.answer
    adjusted = ask(service, "초안을 95자 이내로 축약할 수 있나요?")
    assert "데이터 엔지니어 직무" in adjusted.answer and len(adjusted.answer.splitlines()[1]) <= 95
    ask(service, "버전 관리에서 커밋은 뭐야?")

    restored = make_assistant(tmp_path, service.model)
    rewritten = ask(restored, "그 지원동기를 다시 작성해줘. 맡은 과제에 대한 계획을 반영해줘.")
    assert "데이터 엔지니어 직무" in rewritten.answer and len(rewritten.answer.splitlines()[1]) <= 95
    context = restored.history("alice", "career").turns[-1].narrative_context
    assert (context.target_role, context.min_characters, context.max_characters) == ("데이터 엔지니어", 1, 95)
    assert len(calls) == 2


def test_resume_existing_attached_draft_after_consultation(monkeypatch, tmp_path):
    calls, _ = install_transport(monkeypatch, candidate({"answer": "집계는 결과를 요약하는 데 쓰여요."}))
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    record = service.documents.upload("alice", "resume.json", json_template())
    first = ask(service, FIRST_MOTIVATION, page="documents", document_id=record.id)
    assert first.document.id == record.id
    ask(service, "데이터 집계란 무엇인가요?")

    edited = ask(service, "아까 작성한 지원동기를 100자 이내로 줄여줘. 가상의 경험은 넣지 마.")
    assert edited.document.id == record.id and edited.document.revision == 2
    [field] = [item for item in service.documents.get("alice", record.id).draft.fields if item.field.kind == "narrative"]
    assert "데이터 분석 직무" in field.value and len(field.value.splitlines()[1]) <= 100
    assert len(calls) == 1


def test_new_conversation_drafts_with_verified_facts_using_narrative_stage(monkeypatch, tmp_path, caplog):
    project = Fact(id="verified-project", kind="project", value="공개 통계 검토", source="official")
    calls, _ = install_transport(monkeypatch, candidate({"factIds": [project.id, "demo-project", "invented-award"]}))
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    service.data.profiles["demo001"] = Profile(facts=[project])
    service.add_memory("alice", MemoryEdit(kind="interest", value="데이터 분석"))
    service.add_memory("alice", MemoryEdit(kind="certification", value="SQLD", progress="preparing"))

    with caplog.at_level(logging.INFO, logger=model.__name__):
        result = ask(service, REWRITE_WITH_DETAILS, conversation="fresh")

    body = result.answer.splitlines()[1]
    assert "공개 통계 검토" in body and "SQLD 자격증을 준비" in body and len(body) <= 300
    assert "Campus Data Lab" not in body and len(calls) == 1
    payload = json.loads(json.loads(calls[0].data)["contents"][0]["parts"][0]["text"])
    assert [(fact["id"], fact["provenance"]) for fact in payload["facts"]] == [(project.id, "verified")]
    assert "stage=narrative" in caplog.text and "stage=memory" not in caplog.text


def test_http_and_cli_use_same_draft_continuation(monkeypatch, tmp_path, capsys):
    messages = [FIRST_MOTIVATION, CORRECTION, COMPARISON, REWRITE_WITH_DETAILS]
    statement = COMPARISON.split(". ")[0]

    def run_with_fixture(path):
        calls, _ = install_transport(
            monkeypatch, candidate({"updates": []}),
            candidate({"answer": "말씀하신 관심으로 비교해 볼게요.",
                       "updates": [update("interest", "add", "데이터 분석", statement)]}),
        )
        return make_assistant(path, model.GeminiModel("fixture-key", "gemini-fixture")), calls

    web_service, web_calls = run_with_fixture(tmp_path / "http")
    http = client_for(web_service)
    http.cookies.set("cuk_session", "alice-session")
    http_answers = []
    for message in messages:
        response = http.post("/api/assistant/chat", json={"conversationId": "workflow", "message": message})
        assert response.status_code == 200
        http_answers.append(response.json()["answer"])
    assert len(web_calls) == 2

    cli_service, cli_calls = run_with_fixture(tmp_path / "cli")
    cli_service.data.users["demo001"] = "demo001"
    monkeypatch.setattr(demo, "build_demo", lambda user, store: cli_service)
    monkeypatch.setattr(sys, "argv", ["service", "--conversation-id", "workflow"])
    inputs = iter([*(" ".join(message.split()) for message in messages), "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    demo.main()

    output = capsys.readouterr().out
    assert [answer.strip() for answer in output.split("AI: ")[1:]] == http_answers
    assert http_answers[-1].startswith("[AI 초안]") and len(cli_calls) == 2


def test_narrative_http_distinguishes_motivation_from_required_internship_evidence(monkeypatch, tmp_path):
    calls, _ = install_transport(monkeypatch)
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    service.add_memory("alice", MemoryEdit(kind="goal", value="데이터 분석가"))
    service.add_memory("alice", MemoryEdit(kind="interest", value="데이터 분석"))
    service.add_memory("alice", MemoryEdit(kind="certification", value="SQLD", progress="preparing"))
    http = client_for(service)
    http.cookies.set("cuk_session", "alice-session")

    rewritten = http.post("/api/assistant/narrative", json={"topic": REWRITE_FROM_DISCUSSION, "maxCharacters": 300})
    assert rewritten.status_code == 200
    draft = rewritten.json()["draft"]
    assert draft["status"] == "draft" and "데이터 분석가 직무" in draft["value"]
    assert {fact["kind"] for fact in draft["sources"]} == {"interest", "certification"}
    assert "Campus Data Lab" not in draft["value"] and "어떤 직무" not in draft["note"]

    experience = http.post("/api/assistant/narrative", json={
        "topic": "실제 인턴 경력을 바탕으로 지원동기를 작성해줘. 없는 경력은 만들지 마.",
        "maxCharacters": 300,
    })
    assert experience.status_code == 200
    draft = experience.json()["draft"]
    assert draft["status"] == "missing" and draft["value"] is None and draft["note"].count("?") == 1
    assert not calls


def test_motivation_connects_supported_facts_to_intended_work_in_300_characters(monkeypatch, tmp_path):
    calls, _ = install_transport(monkeypatch)
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    interest = service.add_memory("alice", MemoryEdit(kind="interest", value="데이터 분석"))
    preparation = service.add_memory("alice", MemoryEdit(kind="certification", value="SQLD", progress="preparing"))
    service.add_memory("alice", MemoryEdit(kind="certification", value="전기기사", progress="preparing"))

    draft = service.documents.narrative(service.data.get_profile("alice"), MOTIVATION, service.memory("alice")).draft
    content = draft.value.splitlines()[1]

    assert 130 <= len(content) <= 300
    assert "데이터 분석에 대한 관심을 실제 업무에 연결" in content
    assert "SQLD 자격증을 준비" in content and "판단 기준" in content
    assert "Campus Data Lab" not in content and "취득" not in content and "전기기사" not in content
    assert {fact.id for fact in draft.sources} == {interest.id, preparation.id}
    assert draft.note.count("?") == 1 and not calls


def test_revision_preserves_previous_evidence_and_corrects_credential_only_in_draft(monkeypatch, tmp_path):
    base = make_assistant(tmp_path)
    project = base.add_memory("alice", MemoryEdit(kind="project", value="공개 통계 분석", detail="월별 지표 시각화"))
    cert = base.add_memory("alice", MemoryEdit(kind="certification", value="SQLD", progress="completed"))
    calls, _ = install_transport(monkeypatch, candidate({"factIds": [cert.id, project.id]}))
    service = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    assert "SQLD" in ask(service, MOTIVATION).answer

    body = ask(service, REVISION).answer.splitlines()[1]
    assert "공개 통계 분석" in body and "SQLD 자격증을 준비 중" in body and len(body) <= 120
    assert "취득했습니다" not in body and len(calls) == 1
    assert {fact.id: fact.progress for fact in service.memory("alice")}[cert.id] == "completed"


def test_introduction_uses_owned_background_but_experience_question_needs_real_experience(tmp_path):
    service = make_assistant(tmp_path)
    service.add_memory("alice", MemoryEdit(kind="department", value="통계학과"))
    intro = ask(service, "내가 말한 정보만으로 자기소개를 작성해줘.", conversation="intro")
    experience = ask(service, "실제 문제 해결 경험을 중심으로 자기소개서 문항을 작성해줘.", conversation="experience")
    assert "통계학과 학생입니다" in intro.answer and "인공지능학과" not in intro.answer
    assert "[AI 초안]" not in experience.answer and experience.answer.count("?") == 1
