"""Consultation routing, redaction, and live-plan checks without Gemini access."""

import json

import pytest

from . import live_check, model
from .privacy import redact
from .prompts import CONSULTATION, SKILL
from .test_chat import ask, make_assistant
from .test_gemini_diagnostics import candidate


def test_object_label_does_not_exempt_a_later_personal_name():
    text = "예시 이름은 새벽지도이고 제 실제 이름은 가상학생입니다. 메일 fixture@example.invalid."
    safe = redact(text, object_names=("새벽지도", "가상학생"))
    assert "이름은 새벽지도" in safe
    assert "가상학생" not in safe and "fixture@example.invalid" not in safe
    assert "가상학생" not in redact("제 **이름은** 가상학생입니다.", object_names=("가상학생",))
    assert "새벽지도" not in redact("이름은 새벽지도입니다.")
    topic = "학습 주제의 이름은 \x60새벽지도\x60입니다."
    assert redact(topic, object_names=("새벽지도",)) == topic


def test_named_example_survives_redaction_and_store_reload_across_pages(tmp_path):
    first = make_assistant(tmp_path)
    first.model.answer = {"answer": "이름은 새벽지도입니다."}
    request = "가상의 학습 예시 이름을 새벽지도라고 정하고 그 이름을 써 줄래?"
    response = ask(first, request, conversation="screen-change", page="home")
    assert response.answer == "이름은 새벽지도입니다."

    restored = make_assistant(tmp_path)
    restored.model.answer = {"answer": "이름은 **새벽 지도**예요."}
    followup = ask(restored, "아까 정한 그 이름을 다시 알려줄래?", conversation="screen-change", page="profile")
    assert "새벽 지도" in followup.answer
    assert response.conversation_id == followup.conversation_id == "screen-change"
    _, payload, _ = restored.model.calls[-1]
    assert payload["page"] == "profile" and "conversationId" not in payload
    assert payload["conversation"]["recent"] == [{"page": "home", "user": request, "assistant": response.answer}]
    assert [turn.context.page for turn in restored.history("alice", "screen-change").turns] == ["home", "profile"]

    ask(restored, "그 이름을 따로 확인할 수 있나요?", conversation="another", page="profile")
    assert restored.model.calls[-1][1]["conversation"]["recent"] == []


def test_current_node_beats_old_opportunity_and_keeps_the_career_goal_separate(tmp_path):
    service = make_assistant(tmp_path)
    first = ask(service, "이 공고의 마감은?", conversation="selection", page="opportunities",
                opportunity_id="mock-job-001")
    assert first.opportunities[0].id == "mock-job-001"
    service.model.answer = {"answer": "이 노드의 이름은 데이터 분석입니다. 먼저 Python 기초를 익혀요."}
    result = ask(service, "이 노드의 이름과 선수학습 조건은 뭔가요?", conversation="selection",
                 page="tree", job_id="mock-ai-engineer", skill_id="mock-data-analysis")
    assert not result.opportunities and not result.context_issues
    assert "이름은 데이터 분석입니다" in result.answer
    instruction, data, _ = service.model.calls[-1]
    assert CONSULTATION in instruction and SKILL in instruction
    assert data["conversation"]["recent"][-1]["page"] == "opportunities"
    assert data["page"] == "tree"
    node = data["selectedSkill"]
    assert (node["jobId"], node["skillId"], node["skillName"], node["prerequisites"]) == (
        "mock-ai-engineer", "mock-data-analysis", "데이터 분석", ["Python 기초"],
    )
    goals = [fact["value"] for fact in data["facts"] if fact["kind"] == "goal"]
    assert goals == ["취업"] and node["jobName"] == "AI 엔지니어"


@pytest.mark.parametrize(("text", "prerequisite", "expected"), [
    ("먼저 파이썬 입문부터 해보세요.", "Python 기초", True),
    ("선행해서 HTTPS 기본을 익혀 보세요.", "HTTPS 기초", True),
    ("Python 기초 자료가 있어요.", "Python 기초", False),
    ("Python 기초가 선수학습에 필요 없어요.", "Python 기초", False),
    ("Python 기초는 먼저 익힐 필요가 없어요.", "Python 기초", False),
    ("먼저 SQL 기초를 배워 보세요.", "Python 기초", False),
])
def test_skill_check_requires_a_grounded_prerequisite_and_its_order(text, prerequisite, expected):
    assert live_check._explains_prerequisite(text, prerequisite) is expected


def test_context_only_sends_three_requests_and_projects_only_fixture_diagnostics(monkeypatch, capsys):
    replies = iter([
        candidate({"answer": "예시 이름은 별빛노트입니다. 출력하면 안 되는 모의 응답 표식."}),
        candidate({"answer": "앞에서 정한 이름은 **별빛 노트**예요."}),
        candidate({"answer": "노드의 이름은 데이터-분석입니다. 먼저 파이썬 입문부터 해보세요."}),
    ])
    payloads = []

    def fetch(request, timeout):
        body = json.loads(request.data)
        payloads.append(json.loads(body["contents"][0]["parts"][0]["text"]))
        return next(replies)

    monkeypatch.setattr(model, "urlopen", fetch)
    assert live_check.run_live("fixture-key", "gemini-fixture", scope="context", retries=0, trace_context=True) == 0

    output = capsys.readouterr().out
    traces = [json.loads(line.split(" · ", 1)[1]) for line in output.splitlines() if line.startswith("가상 맥락 진단")]
    assert len(payloads) == 3
    assert [entry["page"] for entry in payloads] == ["home", "profile", "tree"]
    assert traces[0]["localConversationId"] == traces[1]["localConversationId"] == "history"
    assert traces[1]["previousPages"] == ["home"] and traces[1]["priorAssistantHasLabel"]
    assert not traces[1]["conversationIdSent"] and traces[1]["displayAnswerHasLabel"]
    assert traces[2]["selectedSkill"]["skillId"] == "mock-data-analysis"
    assert traces[2]["displayAnswerHasLabel"] and traces[2]["displayAnswerExplainsPrerequisite"]
    assert "Gemini 요청 시도 3회 / 상한 3회" in output
    assert "모의 응답 표식" not in output and "fixture-key" not in output
