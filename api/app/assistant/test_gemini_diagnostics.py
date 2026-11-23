"""Regression tests for Gemini payload diagnostics. All transport is simulated."""
import io
import json
from dataclasses import asdict
from urllib.error import HTTPError, URLError

import pytest

from . import live_check, model
from .contracts import ChatRequest
from .errors import (
    ModelAccessDenied, ModelAuthenticationError, ModelInvalidJSON, ModelInvalidResponse,
    ModelNetworkError, ModelNotFound, ModelRateLimited, ModelRequestRejected,
    ModelServiceUnavailable, ModelTimeout,
)
from .memory import MemoryDiagnostic
from .test_chat import FakeModel, make_assistant, update


def response(value):
    return io.BytesIO(json.dumps(value).encode("utf-8"))


def candidate(value):
    return response({"candidates": [{"content": {"parts": [{"text": json.dumps(value)}]}}]})


@pytest.mark.parametrize(("message", "value", "quote", "expected"), [
    ("나 SQLD 자격증을 취득했어.", "SQLD 자격증", "SQLD 자격증", "SQLD"),
    ("나 ADsP 자격증을 취득했어.", " ＡＤｓＰ 자격증 ", "ADsP", "ADsP"),
    ("나 정보처리기사　자격증에 합격했어.", "정보처리기사 자격증", "정보처리기사 자격증", "정보처리기사"),
])
def test_explicit_certificate_claim_is_normalized_and_persisted(tmp_path, message, value, quote, expected):
    assistant = make_assistant(tmp_path)
    assistant.model.updates[message] = [update(" CERTIFICATION ", "ADD", value, quote)]
    trace = MemoryDiagnostic()
    result = assistant.chat("alice", ChatRequest(message=message), memory_diagnostic=trace)
    [fact] = make_assistant(tmp_path).memory("alice")
    assert result.memory_updated and (fact.value, fact.source) == (expected, "conversation")
    assert trace.validation == {0: "accepted"} and trace.memory_committed
    assert trace.field_shapes[0]["kind"] == "certification"
    assert trace.field_shapes[0]["date"] == "missing"
    diagnostic_json = json.dumps(asdict(trace), ensure_ascii=False)
    assert message not in diagnostic_json and expected not in diagnostic_json


@pytest.mark.parametrize(("message", "quote", "reason"), [
    ("친구가 ADsP 자격증을 취득했어.", "ADsP", "not_user_assertion"),
    ("친구가 ADsP 자격증을 취득했어.", "ADsP 자격증을 취득했어.", "not_user_assertion"),
    ("나 ADsP를 취득할 거야.", "ADsP", "hypothetical_or_negated"),
    ("ADsP는 공부 중이고 SQLD를 취득했어.", "ADsP", "missing_acquisition_assertion"),
    ("ADsP 수업에서 공부했어.", "ADsP", "missing_acquisition_assertion"),
    ("나는 ADsP에 관심 있어.", "ADsP 취득", "quote_missing_or_unbound"),
])
def test_short_citation_cannot_accept_an_unrelated_or_nonpersonal_claim(tmp_path, message, quote, reason):
    assistant = make_assistant(tmp_path)
    assistant.model.updates[message] = [update("certification", "add", "ADsP", quote)]
    trace = MemoryDiagnostic()
    result = assistant.chat("alice", ChatRequest(message=message), memory_diagnostic=trace)
    assert not result.memory_updated and not assistant.memory("alice")
    assert trace.validation == {0: reason} and not trace.memory_committed


def test_memory_trace_distinguishes_a_candidate_from_a_committed_update(tmp_path):
    assistant = make_assistant(tmp_path)
    assistant.model.answer = {}
    trace = MemoryDiagnostic()
    with pytest.raises(ModelInvalidResponse) as failure:
        assistant.chat("alice", ChatRequest(message="나 SQLD 취득했어."), memory_diagnostic=trace)
    assert trace.validation == {0: "accepted"} and not trace.memory_committed
    assert not assistant.memory("alice")
    assert failure.value.reason == "answer_schema" and failure.value.operation == "consultation"


def test_diagnostic_distinguishes_missing_updates_from_empty(tmp_path):
    class MemoryShape(FakeModel):
        def __init__(self, payload):
            super().__init__()
            self.payload = payload

        def generate(self, instruction, data, schema):
            if instruction == model_memory:
                return self.payload
            return super().generate(instruction, data, schema)

    from .prompts import MEMORY as model_memory

    for payload, expected in (({}, "missing_updates"), ({"updates": "bad"}, "invalid_updates"),
                              ({"updates": []}, "empty_updates")):
        trace = MemoryDiagnostic()
        assistant = make_assistant(tmp_path, MemoryShape(payload))
        assistant.chat("alice", ChatRequest(message="데이터 분석을 공부했어."), memory_diagnostic=trace)
        assert trace.extraction == expected and not trace.memory_committed


@pytest.mark.parametrize(("status", "google_code", "detail", "error_type", "expected_reason"), [
    (404, "NOT_FOUND", None, ModelNotFound, "NOT_FOUND"),
    (429, "RESOURCE_EXHAUSTED", None, ModelRateLimited, "RESOURCE_EXHAUSTED"),
    (503, "UNAVAILABLE", None, ModelServiceUnavailable, "UNAVAILABLE"),
    (401, "UNAUTHENTICATED", None, ModelAuthenticationError, "UNAUTHENTICATED"),
    (403, "PERMISSION_DENIED", None, ModelAccessDenied, "PERMISSION_DENIED"),
    (400, "INVALID_ARGUMENT", "API_KEY_INVALID", ModelAuthenticationError, "API_KEY_INVALID"),
    (400, "INVALID_ARGUMENT", "untrusted-opaque-value", ModelRequestRejected, "INVALID_ARGUMENT"),
    (504, "DEADLINE_EXCEEDED", None, ModelTimeout, "DEADLINE_EXCEEDED"),
])
def test_preserves_http_status_and_allowlisted_google_reason(
    monkeypatch, status, google_code, detail, error_type, expected_reason,
):
    def fetch(request, timeout):
        raise HTTPError("https://example.invalid", status, "hidden reason", {"X-Debug": "hidden header"},
                        response({"error": {"status": google_code, "message": "hidden body",
                                            "details": [{"reason": detail}]}}))

    monkeypatch.setattr(model, "urlopen", fetch)
    with pytest.raises(error_type) as failure:
        model.GeminiModel("fixture-key", "gemini-fixture", max_503_retries=0).generate("fixture prompt", {}, {})
    error = failure.value
    assert (error.upstream_status, error.reason, error.operation) == (status, expected_reason, "generateContent")
    summary = live_check._error_summary(error)
    assert f"Gemini HTTP {status}" in summary
    assert all(value not in summary for value in
               ("hidden reason", "hidden body", "hidden header", "fixture-key", "fixture prompt",
                "untrusted-opaque-value"))


@pytest.mark.parametrize(("failure", "error_type"), [
    (TimeoutError("hidden timeout"), ModelTimeout),
    (URLError(TimeoutError("hidden timeout")), ModelTimeout),
    (URLError("hidden network reason"), ModelNetworkError),
])
def test_distinguishes_transport_failure_without_an_http_status(monkeypatch, failure, error_type):
    def fetch(*args, **kwargs):
        raise failure

    monkeypatch.setattr(model, "urlopen", fetch)
    with pytest.raises(error_type) as caught:
        model.GeminiModel("fixture-key", "gemini-fixture").generate("", {}, {})
    assert caught.value.upstream_status is None
    assert "hidden" not in live_check._error_summary(caught.value)


@pytest.mark.parametrize(("body", "error_type", "reason"), [
    (b"<non-json response>", ModelInvalidJSON, "response_json"),
    (b'{"candidates":[{"content":{"parts":[{"text":"{bad json"}]}}]}', ModelInvalidJSON, "candidate_json"),
    (b'{"candidates":[{"finishReason":"MAX_TOKENS","content":{"parts":[{"text":"{"}]}}]}',
     ModelInvalidJSON, "MAX_TOKENS"),
    (b'{"promptFeedback":{"blockReason":"SAFETY"}}', ModelInvalidResponse, "SAFETY"),
])
def test_distinguishes_json_fault_and_blocked_candidate(monkeypatch, body, error_type, reason):
    monkeypatch.setattr(model, "urlopen", lambda *args, **kwargs: io.BytesIO(body))
    with pytest.raises(error_type) as caught:
        model.GeminiModel("fixture-key", "gemini-fixture").generate("", {}, {})
    assert (caught.value.upstream_status, caught.value.reason) == (200, reason)


@pytest.mark.parametrize(("methods", "expected"), [(["generateContent"], True), (["countTokens"], False)])
def test_access_check_only_requests_model_metadata(monkeypatch, methods, expected):
    def fetch(request, timeout):
        assert request.method == "GET" and request.data is None
        assert request.full_url.endswith("/models/gemini-fixture")
        return response({"name": "models/gemini-fixture", "supportedGenerationMethods": methods})

    monkeypatch.setattr(model, "urlopen", fetch)
    assert model.GeminiModel("fixture-key", "gemini-fixture").check_access() is expected


def test_live_runner_reports_where_unavailable_occurred(monkeypatch, capsys):
    replies = iter([
        candidate({"updates": []}),
        candidate({"answer": "가상 답변"}),
        candidate({"answer": "별빛노트"}),
    ])
    count = 0

    def fetch(request, timeout):
        nonlocal count
        count += 1
        assert request.method == "POST"
        if count == 4:
            raise HTTPError("https://example.invalid", 503, "sensitive marker", {},
                            response({"error": {"status": "UNAVAILABLE"}}))
        return next(replies)

    monkeypatch.setattr(model, "urlopen", fetch)
    assert live_check.run_live("fixture-key", "gemini-fixture", retries=0) == 1
    output = capsys.readouterr().out
    assert count == 4
    assert '"extraction": "empty_updates"' in output
    assert "[미실행] 저장된 사용자 정보" in output
    assert "model_service_unavailable / generateContent / Gemini HTTP 503 / UNAVAILABLE" in output
    assert "통과 0, 실패 2, 미실행 4" in output
    assert "sensitive marker" not in output


def test_live_runner_can_limit_first_scenario_to_two_requests(monkeypatch, capsys):
    replies = iter([
        candidate({"updates": [update("certification", "add", "SQLD 자격증", "SQLD")]}),
        candidate({"answer": "가상 응답"}),
    ])
    monkeypatch.setattr(model, "urlopen", lambda *args, **kwargs: next(replies))
    assert live_check.run_live("fixture-key", "gemini-fixture", memory_only=True) == 0
    output = capsys.readouterr().out
    assert "Gemini 요청 시도 2회" in output and '"memory_committed": true' in output
    assert "SQLD" not in output
