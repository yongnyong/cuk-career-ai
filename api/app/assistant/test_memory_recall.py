"""Offline reproduction of the skill lab's user memory and recall flow."""

import json
import logging

from . import model, skill_lab
from .errors import StorageUnavailable
from .test_chat import ask, update
from .test_documents import client_for
from .test_gemini_diagnostics import candidate
from .test_gemini_retries import install_transport
from .test_skill_lab import lab_service

STATEMENT = (
    "나는 Python 기초 문법은 어느 정도 알고 있지만, "
    "실제 데이터 분석 프로젝트를 해본 적은 없어. 이 내용을 기억해줘."
)
RECALL = "내가 직접 말했던 Python 실력과 데이터 분석 프로젝트 경험을 각각 알려줘. 가상 사용자 데이터와 구분해줘."
SKILL_QUOTE = "Python 기초 문법은 어느 정도 알고 있지만"
ABSENCE_QUOTE = "데이터 분석 프로젝트를 해본 적은 없어."


def test_skill_lab_remembers_direct_statements_across_job_changes(monkeypatch, tmp_path, capsys):
    calls, _ = install_transport(
        monkeypatch,
        candidate({"updates": [
            update("skill", "add", "Python", SKILL_QUOTE, progress="beginner"),
            update("project", "add", "데이터 분석 프로젝트", ABSENCE_QUOTE, progress="not_held"),
        ]}),
        candidate({"answer": "말씀하신 내용을 기억하겠습니다."}),
        candidate({"updates": []}),
        candidate({"answer": "직접 발화한 내용이 없고, 모두 가상 예시(fixture)입니다."}),
    )
    service = lab_service(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    actions = iter([
        ":job mock-ai-engineer", ":node mock-data-analysis", STATEMENT,
        ":job mock-ai-engineer", ":node mock-pandas", ":job mock-data-engineer", ":node mock-pipeline",
        RECALL, ":quit",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(actions))
    skill_lab.run_session(service)
    output = capsys.readouterr().out

    assert "다음 내용을 기억에 저장했어요" in output
    assert "기초 문법은 어느 정도 알고 있다고" in output and "데이터 분석 프로젝트" in output and "경험이 없다고" in output
    assert "Campus Data Lab" in output and "가상" in output and "(fixture)" not in output
    persisted = lab_service(tmp_path).store.get_state("demo001")
    assert {(fact.kind, fact.value, fact.progress, fact.source) for fact in persisted.memory} == {
        ("skill", "Python", "beginner", "conversation"),
        ("project", "데이터 분석 프로젝트", "not_held", "conversation"),
    }
    first, second = persisted.conversations["skill-lab"].turns
    assert first.result.memory_updated and second.context.skill_id == "mock-pipeline"
    assert len(calls) == 1


def test_memory_survives_when_model_omits_candidates_and_after_many_consultations(monkeypatch, tmp_path, caplog):
    calls, _ = install_transport(
        monkeypatch, candidate({"updates": []}),
        *(candidate({"answer": "fixture와 facts를 바탕으로 표를 만들어 보세요."}) for _ in range(8)),
    )
    service = lab_service(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    with caplog.at_level(logging.INFO, logger=model.__name__):
        saved = ask(service, STATEMENT, page="tree", job_id="mock-ai-engineer", skill_id="mock-data-analysis")
        immediate = ask(service, RECALL, page="tree", job_id="mock-ai-engineer", skill_id="mock-pandas")
    assert saved.memory_updated and "저장했어요" in saved.answer
    assert "기초 문법은 어느 정도 알고 있다고" in immediate.answer and "해 본 경험이 없다고" in immediate.answer
    _, example = immediate.answer.split("\n\n", 1)
    assert "가상 사용자 데이터" in example and "상담용 예시" in example and "Campus Data Lab" in example
    assert len(calls) == 1
    for _ in range(8):
        answer = ask(service, "이 노드를 어떤 실습부터 시작하면 좋을까?", page="tree",
                     job_id="mock-data-engineer", skill_id="mock-pipeline")
        assert "fixture" not in answer.answer and "facts" not in answer.answer

    reloaded = lab_service(tmp_path, service.model)
    remembered = ask(reloaded, RECALL, page="tree", job_id="mock-data-engineer", skill_id="mock-pipeline")
    assert remembered.answer == immediate.answer and len(calls) == 9
    payload = json.loads(json.loads(calls[-1].data)["contents"][0]["parts"][0]["text"])
    origins = {(fact["value"], fact["provenance"], fact.get("progress")) for fact in payload["facts"]}
    assert ("데이터 분석 프로젝트", "user_statement", "not_held") in origins
    assert ("Python", "user_statement", "beginner") in origins
    assert STATEMENT not in json.dumps(payload["conversation"], ensure_ascii=False)
    assert "fixture-key" not in caplog.text and SKILL_QUOTE not in caplog.text and ABSENCE_QUOTE not in caplog.text


def test_positive_and_negative_experience_and_skill_corrections_update_existing_rows(tmp_path):
    service = lab_service(tmp_path)
    assert ask(service, STATEMENT).memory_updated
    initial = {fact.kind: fact.id for fact in service.memory("alice")}
    positive = "Python은 이제 중급이야. 데이터 분석 프로젝트에서 실제로 보고서 작성을 맡았어."
    service.model.updates[positive] = [
        update("skill", "set", "Python", "Python은 이제 중급이야.", progress="intermediate"),
        update("project", "add", "데이터 분석 프로젝트", "데이터 분석 프로젝트에서 실제로 보고서 작성을 맡았어."),
    ]
    assert ask(service, positive).memory_updated
    facts = {fact.kind: fact for fact in service.memory("alice")}
    assert {kind: fact.id for kind, fact in facts.items()} == initial
    assert facts["project"].progress is None and facts["skill"].progress == "intermediate"
    assert "직접 경험했다고" in ask(service, RECALL).answer

    correction = "사실 데이터 분석 프로젝트 경험은 없어."
    # The model may omit the progress field and mistake denial for a deletion request.
    service.model.updates[correction] = [update("project", "remove", "데이터 분석 프로젝트", correction)]
    assert ask(service, correction).memory_updated
    assert "해 본 경험이 없다고" in ask(service, RECALL).answer
    project = next(fact for fact in service.memory("alice") if fact.kind == "project")
    assert (project.id, project.progress) == (initial["project"], "not_held")


def test_negative_experience_requires_an_actual_personal_assertion(tmp_path):
    service = lab_service(tmp_path)
    for message in (
        "친구는 데이터 분석 프로젝트 경험이 없어. 이 내용을 기억해줘.",
        "만약 내가 데이터 분석 프로젝트 경험이 없다면 좋을까? 이 내용을 기억해줘.",
        "데이터 분석 프로젝트 경험이 없다고 자기소개서에 써줘.",
    ):
        service.model.updates[message] = [update("project", "add", "데이터 분석 프로젝트", message, progress="not_held")]
        result = ask(service, message)
        assert not result.memory_updated and not service.memory("alice")
        assert "기억에 저장했어요" not in result.answer


def test_http_and_cli_return_same_direct_recall_and_isolate_users(monkeypatch, tmp_path, capsys):
    service = lab_service(tmp_path)
    http = client_for(service)
    body = {"conversationId": "skill-lab", "context": {"page": "tree", "jobId": "mock-ai-engineer", "skillId": "mock-pandas"}}
    http.cookies.set("cuk_session", "alice-session")
    stored = http.post("/api/assistant/chat", json={**body, "message": STATEMENT})
    assert stored.status_code == 200 and stored.json()["memoryUpdated"]
    recall = http.post("/api/assistant/chat", json={**body, "message": RECALL}).json()
    entries = http.get("/api/assistant/memory").json()
    assert any(fact["kind"] == "project" and fact["progress"] == "not_held" for fact in entries)

    http.cookies.set("cuk_session", "bob-session")
    assert http.get("/api/assistant/memory").json() == []
    empty = http.post("/api/assistant/chat", json={**body, "message": RECALL}).json()["answer"]
    assert "직접 말씀하신 내용은 저장돼 있지 않아요" in empty and "해 본 경험이 없다고" not in empty

    actions = iter([":job mock-ai-engineer", ":node mock-pandas", STATEMENT, RECALL, ":quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(actions))
    skill_lab.run_session(service)
    output = capsys.readouterr().out
    assert [answer.strip() for answer in output.split("AI: ")[1:]][-1] == recall["answer"]
    assert service.memory("demo002") == [] and len(service.model.calls) == 2


def test_unconfirmed_and_failed_write_never_acknowledge_storage(monkeypatch, tmp_path):
    service = lab_service(tmp_path)
    http = client_for(service)
    http.cookies.set("cuk_session", "alice-session")
    empty = http.post("/api/assistant/chat", json={"message": "이 내용을 기억해줘."}).json()
    assert not empty["memoryUpdated"] and "새로 저장된 내용은 없어요" in empty["answer"]
    before = service.store.get_state("alice").revision

    def fail_save(user_id, state):
        raise StorageUnavailable("대화 상태를 저장할 수 없어요.")

    monkeypatch.setattr(service.store, "save_state", fail_save)
    reply = http.post("/api/assistant/chat", json={"message": STATEMENT})
    assert reply.status_code == 503 and reply.json()["detail"]["code"] == "storage_unavailable"
    assert "저장했어요" not in reply.text
    assert service.store.get_state("alice").revision == before and service.memory("alice") == []


def test_model_cannot_claim_an_implicit_write_if_extraction_failed(tmp_path):
    service = lab_service(tmp_path)
    service.model.answer = {"answer": "말씀하신 내용을 기억해 둘게요. 기초부터 연습해 보세요."}
    response = ask(service, "공부를 시작해 볼래.")
    assert "기억해 둘게요" not in response.answer and "기초부터 연습" in response.answer
    assert service.memory("alice") == []


def test_same_recovery_works_for_another_skill_and_project(tmp_path):
    service = lab_service(tmp_path)
    statement = "나는 자바스크립트 기본 문법은 조금 알아. 배포 자동화 프로젝트 경험은 아직 없어요. 기억해 주세요."
    assert ask(service, statement).memory_updated
    entries = service.memory("alice")
    assert {(fact.value, fact.progress) for fact in entries} == {
        ("자바스크립트", "beginner"), ("배포 자동화 프로젝트", "not_held"),
    }
    answer = ask(service, "내가 이야기한 기술 수준과 프로젝트 경험을 알려줘. 가상 기록과 구분해서 보여줘.").answer
    assert "자바스크립트" in answer and "배포 자동화 프로젝트" in answer
    assert "기초" in answer or "기본 문법" in answer


def test_negative_experience_cannot_fill_document_as_work_done(tmp_path):
    service = lab_service(tmp_path)
    assert ask(service, STATEMENT).memory_updated
    request = "실제 데이터 분석 프로젝트 경험을 바탕으로 지원동기를 작성해줘."
    draft = service.documents.narrative(service.data.get_profile("alice"), request, service.memory("alice")).draft
    assert draft.status == "missing" and draft.value is None and not draft.sources
