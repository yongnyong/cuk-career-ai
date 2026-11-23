"""Exercise real adapter retries and live-check budgets without network or delays."""

import json
from urllib.error import HTTPError

import pytest

from . import live_check, model
from .contracts import ChatRequest
from .errors import ModelServiceUnavailable, ModelUnavailable
from .test_chat import make_assistant, update
from .test_gemini_diagnostics import candidate, response


def http_error(status=503):
    return HTTPError("https://example.invalid", status, "private upstream details", {},
                     response({"error": {"status": "UNAVAILABLE" if status == 503 else "UNKNOWN"}}))


def install_transport(monkeypatch, *replies):
    pending = iter(replies)
    calls = []
    waits = []

    def fetch(request, timeout):
        calls.append(request)
        reply = next(pending)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(model, "urlopen", fetch)
    monkeypatch.setattr(model, "sleep", waits.append)
    return calls, waits


def test_provider_retries_503_with_exponential_backoff(monkeypatch):
    calls, waits = install_transport(monkeypatch, http_error(), http_error(), candidate({"answer": "모의 답변"}))
    client = model.GeminiModel("fixture-key", "gemini-fixture")
    assert client.generate("fixture instruction", {}, {}) == {"answer": "모의 답변"}
    assert len(calls) == 3 and waits == [1, 2]
    assert all(request.method == "POST" and request.data == calls[0].data for request in calls)


@pytest.mark.parametrize("status", [302, 400, 401, 403, 404, 429, 500, 504])
def test_other_http_failures_are_not_retried(monkeypatch, status):
    calls, waits = install_transport(monkeypatch, http_error(status))
    with pytest.raises(ModelUnavailable) as failure:
        model.GeminiModel("fixture-key", "gemini-fixture").generate("", {}, {})
    assert failure.value.upstream_status == status
    assert len(calls) == 1 and waits == []


def test_retrying_a_chat_request_commits_one_turn_and_one_memory(monkeypatch, tmp_path):
    message = "나 SQLD 취득했어."
    calls, waits = install_transport(
        monkeypatch,
        candidate({"updates": [update("certification", "add", "SQLD", message)]}),
        http_error(), http_error(), candidate({"answer": "취득했다고 알려주신 내용을 기억할게요."}),
    )
    assistant = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    request = ChatRequest(message=message, request_id="fixture-turn")
    first = assistant.chat("alice", request)
    replayed = assistant.chat("alice", request)

    state = assistant.store.get_state("alice")
    assert first == replayed and first.memory_updated
    assert state.revision == 1 and [fact.value for fact in state.memory] == ["SQLD"]
    [turn] = state.conversations["default"].turns
    assert turn.request_id == "fixture-turn"
    assert len(calls) == 4 and waits == [1, 2]
    assert all(request.data == calls[1].data for request in calls[1:])


def test_failed_generation_after_last_retry_does_not_commit_the_turn(monkeypatch, tmp_path):
    message = "나 SQLD 취득했어."
    calls, waits = install_transport(
        monkeypatch,
        candidate({"updates": [update("certification", "add", "SQLD", message)]}),
        http_error(), http_error(), http_error(),
    )
    assistant = make_assistant(tmp_path, model.GeminiModel("fixture-key", "gemini-fixture"))
    with pytest.raises(ModelServiceUnavailable) as failure:
        assistant.chat("alice", ChatRequest(message=message))

    assert failure.value.upstream_status == 503 and failure.value.retries_taken == 2
    assert assistant.store.get_state("alice").revision == 0
    assert not assistant.memory("alice")
    assert not assistant.store.get_state("alice").conversations
    assert len(calls) == 4 and waits == [1, 2]


def test_probing_plain_text_and_stored_memory_use_distinct_payloads(monkeypatch, capsys):
    plain = response({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]})
    calls, waits = install_transport(monkeypatch, plain, candidate({"answer": "말씀하신 자격증은 SQLD예요."}))

    assert live_check.run_live("fixture-key", "gemini-fixture", scope="probe") == 0
    assert live_check.run_live("fixture-key", "gemini-fixture", scope="recall") == 0

    plain_request, recall_request = [json.loads(request.data) for request in calls]
    assert "systemInstruction" not in plain_request
    assert "responseSchema" not in plain_request["generationConfig"]
    assert "systemInstruction" in recall_request
    assert "responseSchema" in recall_request["generationConfig"]
    facts = json.loads(recall_request["contents"][0]["parts"][0]["text"])["facts"]
    assert any(fact["value"] == "SQLD" and fact["source"] == "user_claim" for fact in facts)
    assert len(calls) == 2 and waits == []
    output = capsys.readouterr().out
    assert "짧은 일반 텍스트 생성" in output and "저장된 사용자 정보로 새 대화 답변" in output
    assert "SQLD" not in output and "fixture-key" not in output


def test_repeated_503_fetches_one_metadata_page_within_the_probe_budget(monkeypatch, capsys):
    alternatives = response({"models": [
        {"name": "models/gemini-fixture", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.1-flash-image", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-no-generation", "supportedGenerationMethods": ["countTokens"]},
        {"name": "models/untrusted model name", "supportedGenerationMethods": ["generateContent"]},
    ], "nextPageToken": "private page cursor"})
    calls, waits = install_transport(monkeypatch, http_error(), http_error(), http_error(), alternatives)

    assert live_check.run_live("fixture-key", "gemini-fixture", scope="probe") == 1

    assert [request.method for request in calls] == ["POST", "POST", "POST", "GET"]
    assert calls[-1].data is None and "/models?" in calls[-1].full_url
    assert all("/models/gemini-fixture:generateContent" in request.full_url for request in calls[:3])
    assert waits == [1, 2]
    output = capsys.readouterr().out
    assert "대체 후보 · gemini-3.1-flash-lite" in output
    assert "Gemini 요청 시도 4회 / 상한 4회" in output
    assert "재시도 2회, 메타데이터 1회" in output
    assert "private page cursor" not in output and "private upstream details" not in output


def test_full_run_stops_at_eight_requests_including_a_retry(monkeypatch, capsys):
    calls, waits = install_transport(
        monkeypatch,
        candidate({"updates": [update("certification", "add", "SQLD", "나 SQLD 자격증을 취득했어.")]}),
        candidate({"answer": "기억해 둘게요."}),
        http_error(),
        candidate({"answer": "SQLD 자격증이에요."}),
        candidate({"answer": "별빛노트"}),
        candidate({"answer": "별빛노트"}),
        candidate({"answer": "데이터 분석의 선수학습은 Python 기초예요."}),
        candidate({"preparationIds": ["documents"]}),
    )

    assert live_check.run_live("fixture-key", "gemini-fixture") == 1

    assert len(calls) == 8 and waits == [1]
    output = capsys.readouterr().out
    assert "Gemini 요청 상한 8회에 도달" in output
    assert "Gemini 요청 시도 8회 / 상한 8회" in output
    assert "재시도 1회, 메타데이터 0회" in output


def test_candidate_lookup_never_bypasses_the_memory_mode_budget(monkeypatch, capsys):
    calls, waits = install_transport(monkeypatch, http_error(), http_error())
    assert live_check.run_live("fixture-key", "gemini-fixture", memory_only=True, retries=1) == 1

    assert [request.method for request in calls] == ["POST", "POST"] and waits == [1]
    output = capsys.readouterr().out
    assert "대체 모델 조회를 생략" in output
    assert "Gemini 요청 시도 2회 / 상한 2회" in output


def test_model_listing_has_an_independent_one_request_limit(monkeypatch, capsys):
    calls, waits = install_transport(monkeypatch, http_error())
    assert live_check.run_model_check("fixture-key", "gemini-fixture", list_models=True) == 1
    assert [request.method for request in calls] == ["GET"] and waits == []
    assert "models.list / Gemini HTTP 503" in capsys.readouterr().out


def test_preflight_shows_hard_limits_without_requests(monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    calls, waits = install_transport(monkeypatch)

    assert live_check.main([]) == 0
    assert live_check.main(["--probe"]) == 0
    assert live_check.main(["--recall-only", "--retries", "0"]) == 0

    output = capsys.readouterr().out
    assert all(f"총 요청 상한 {limit}회" in output for limit in (8, 4, 1))
    assert "fixture-key" not in output
    assert calls == [] and waits == []
