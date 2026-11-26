"""Gemini adapter with a separate system instruction and bounded responses."""
import json
import logging
import math
import re
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from http.client import HTTPException
from time import monotonic, sleep
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .errors import (
    ModelAccessDenied, ModelAuthenticationError, ModelInvalidJSON, ModelInvalidResponse,
    ModelNetworkError, ModelNotFound, ModelRateLimited, ModelRequestRejected,
    AssistantError, ModelServiceUnavailable, ModelTimeout, ModelUnavailable,
)
from .prompts import UNTRUSTED_DATA

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
_MAX_RESPONSE = 128 * 1024
MAX_503_RETRIES = 2
DEFAULT_REQUEST_BUDGET = 12
TIMEOUT_MESSAGE = "AI 응답 시간이 초과됐어요. 잠시 후 같은 질문을 다시 보내 주세요."
_LOGGER = logging.getLogger(__name__)
_NON_TEXT_MODEL = re.compile(r"-(?:live|audio|tts|image|embedding|robotics|transcribe|omni|nano-banana)(?:-|$)")
_AUTH_REASONS = {"API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_NOT_FOUND"}
_ERROR_CODES = _AUTH_REASONS | {
    "API_KEY_SERVICE_BLOCKED", "API_KEY_HTTP_REFERRER_BLOCKED", "API_KEY_IP_ADDRESS_BLOCKED",
    "FREE_TIER_VERIFICATION_REQUIRED", "SERVICE_DISABLED", "BILLING_DISABLED",
    "UNAUTHENTICATED", "PERMISSION_DENIED", "INVALID_ARGUMENT", "NOT_FOUND",
    "RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED", "INTERNAL",
}
_BLOCK_REASONS = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "OTHER", "IMAGE_SAFETY", "MODEL_ARMOR"}
_FINISH_REASONS = _BLOCK_REASONS | {"MAX_TOKENS", "RECITATION", "SPII", "LANGUAGE"}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # One transport attempt must never turn into another request outside its budget.
        return None


urlopen = build_opener(_NoRedirect()).open


class LanguageModel(Protocol):
    def generate(self, instruction: str, data: dict, schema: dict) -> dict: ...


@dataclass
class _RequestMetrics:
    started: float
    calls: int = 0
    attempts: int = 0
    upstream_seconds: float = 0
    backoff_seconds: float = 0
    local_phases: dict[str, float] = field(default_factory=dict)


_METRICS: ContextVar[_RequestMetrics | None] = ContextVar("gemini_metrics", default=None)
_STAGE = ContextVar("gemini_stage", default="generation")


def _ms(seconds: float) -> int:
    return round(seconds * 1000)


@contextmanager
def model_request(stage: str):
    """Share timing and retry budget across model calls in one assistant operation."""
    if _METRICS.get() is not None:
        yield
        return
    metrics = _RequestMetrics(started=monotonic())
    token = _METRICS.set(metrics)
    error_code = "none"
    try:
        yield
    except AssistantError as error:
        error_code = error.code
        raise
    except Exception:
        error_code = "internal_error"
        raise
    finally:
        elapsed = monotonic() - metrics.started
        if metrics.calls or "draft_render" in metrics.local_phases:
            for phase, duration in metrics.local_phases.items():
                _LOGGER.info("gemini stage=%s phase=%s elapsed_ms=%d", stage, phase, _ms(duration))
            _LOGGER.info(
                "gemini stage=%s elapsed_ms=%d local_ms=%d upstream_ms=%d backoff_ms=%d calls=%d attempts=%d error=%s",
                stage, _ms(elapsed), _ms(max(0, elapsed - metrics.upstream_seconds - metrics.backoff_seconds)),
                _ms(metrics.upstream_seconds), _ms(metrics.backoff_seconds), metrics.calls, metrics.attempts, error_code,
            )
        _METRICS.reset(token)


@contextmanager
def model_phase(phase: str):
    metrics = _METRICS.get()
    if metrics is None:
        yield
        return
    started = monotonic()
    try:
        yield
    finally:
        metrics.local_phases[phase] = metrics.local_phases.get(phase, 0) + monotonic() - started


def generate_for(model: LanguageModel, stage: str, instruction: str, data: dict, schema: dict) -> dict:
    token = _STAGE.set(stage)
    try:
        return model.generate(instruction, data, schema)
    finally:
        _STAGE.reset(token)


def _error_reason(error: HTTPError) -> str | None:
    # Keep only known Google enum values. Free-text errors can contain request data.
    if error.fp is None:
        return None
    try:
        with error:
            raw = error.read(8193)
        if len(raw) > 8192:
            return None
        body = json.loads(raw)["error"]
        for detail in body.get("details", []):
            reason = detail.get("reason") if isinstance(detail, dict) else None
            if isinstance(reason, str) and reason in _ERROR_CODES:
                return reason
        status = body.get("status")
        return status if isinstance(status, str) and status in _ERROR_CODES else None
    except (OSError, HTTPException, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return None


def _http_failure(error: HTTPError, operation: str) -> ModelUnavailable:
    status = error.code
    reason = _error_reason(error)
    context = {"upstream_status": status, "operation": operation, "reason": reason}
    if status == 401 or reason in _AUTH_REASONS:
        return ModelAuthenticationError("Gemini API 인증을 확인해 주세요.", **context)
    if status == 403:
        return ModelAccessDenied("Gemini 프로젝트 또는 모델에 접근할 수 없어요.", **context)
    if status == 404:
        return ModelNotFound("지정한 Gemini 모델 또는 API 경로를 찾을 수 없어요.", **context)
    if status == 429:
        return ModelRateLimited("AI 요청이 많아요. 잠시 후 다시 시도해 주세요.", **context)
    if status in (408, 504):
        return ModelTimeout(TIMEOUT_MESSAGE, **context)
    if status == 503:
        return ModelServiceUnavailable("AI 서비스가 일시적으로 응답하지 않아요. 잠시 후 다시 시도해 주세요.", **context)
    if 400 <= status < 500:
        return ModelRequestRejected("Gemini가 요청을 받아들이지 않았어요.", **context)
    return ModelUnavailable("AI 응답을 만들 수 없어요.", **context)


class GeminiModel:
    def __init__(
        self, api_key: str, model: str, timeout: float = 8, *,
        request_budget: float = DEFAULT_REQUEST_BUDGET,
        max_503_retries: int = MAX_503_RETRIES,
        before_request: Callable[[str, int], None] | None = None,
    ):
        if not api_key or not re.fullmatch(r"gemini-[A-Za-z0-9.-]+", model):
            raise ValueError("Gemini 모델과 인증 설정이 필요합니다.")
        if max_503_retries not in range(MAX_503_RETRIES + 1):
            raise ValueError("Gemini 503 재시도는 0~2회로 설정해 주세요.")
        if not (math.isfinite(timeout) and timeout > 0 and math.isfinite(request_budget) and request_budget > 0):
            raise ValueError("Gemini 시간 제한은 양수여야 합니다.")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.request_budget = request_budget
        self.max_503_retries = max_503_retries
        self.before_request = before_request

    def _remaining(self) -> float:
        return self.request_budget - (monotonic() - _METRICS.get().started)

    def _request(self, operation: str, body: bytes | None = None, *, retry: int = 0) -> tuple[dict, int]:
        generate = body is not None
        stage = _STAGE.get() if generate else operation
        metrics = _METRICS.get()
        wait = 2 ** (retry - 1) if retry else 0
        timeout = min(self.timeout, self._remaining() - wait)
        if timeout <= 0:
            _LOGGER.info("gemini stage=%s phase=budget timeout_ms=0 error=model_timeout", stage)
            raise ModelTimeout(TIMEOUT_MESSAGE, operation=operation, reason="request_budget")
        url = f"{_ENDPOINT}/{self.model}" + (":generateContent" if generate else "")
        if operation == "models.list":
            url = f"{_ENDPOINT}?pageSize=200&fields=models(name,supportedGenerationMethods),nextPageToken"
        request = Request(
            url, data=body,
            headers={"Content-Type": "application/json"} if generate else {},
            method="POST" if generate else "GET",
        )
        request.add_unredirected_header("x-goog-api-key", self.api_key)
        if self.before_request is not None:
            self.before_request(operation, retry)
        if wait:
            waiting = monotonic()
            sleep(wait)
            metrics.backoff_seconds += monotonic() - waiting
        timeout = min(self.timeout, self._remaining())
        if timeout <= 0:
            _LOGGER.info("gemini stage=%s phase=budget timeout_ms=0 error=model_timeout", stage)
            raise ModelTimeout(TIMEOUT_MESSAGE, operation=operation, reason="request_budget")
        metrics.attempts += 1
        transport_started = monotonic()
        status = None
        phase = "upstream_open"
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                self._log_transport(stage, phase, transport_started, metrics, retry, body, timeout)
                phase, transport_started = "upstream_read", monotonic()
                raw = response.read(_MAX_RESPONSE + 1)
        except HTTPError as error:
            failure = _http_failure(error, operation)
        except TimeoutError:
            failure = ModelTimeout(TIMEOUT_MESSAGE, upstream_status=status, operation=operation, reason="socket_timeout")
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                failure = ModelTimeout(TIMEOUT_MESSAGE, operation=operation, reason="socket_timeout")
            else:
                failure = ModelNetworkError("AI 서비스에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.",
                                            operation=operation)
        except (OSError, HTTPException):
            failure = ModelNetworkError("AI 서비스 연결이 끊겼어요. 잠시 후 다시 시도해 주세요.",
                                        upstream_status=status, operation=operation)
        else:
            failure = None
        self._log_transport(stage, phase, transport_started, metrics, retry, body, timeout, failure)
        if failure:
            raise failure from None
        if self._remaining() <= 0:
            _LOGGER.info("gemini stage=%s phase=budget timeout_ms=0 error=model_timeout", stage)
            raise ModelTimeout(TIMEOUT_MESSAGE, operation=operation, reason="request_budget")

        with model_phase("http_decode"):
            return self._decode(raw, status, operation), status

    @staticmethod
    def _log_transport(stage, phase, started, metrics, retry, body, timeout, error=None):
        duration = monotonic() - started
        metrics.upstream_seconds += duration
        if isinstance(error, ModelTimeout):
            error_type = "upstream_timeout" if error.upstream_status in (408, 504) else "socket_timeout"
        else:
            error_type = error.code if error else "none"
        _LOGGER.info(
            "gemini stage=%s phase=%s elapsed_ms=%d attempt=%d retry=%d request_bytes=%d timeout_ms=%d error=%s type=%s",
            stage, phase, _ms(duration), metrics.attempts, retry, len(body or b""), _ms(timeout),
            error.code if error else "none", error_type,
        )

    @staticmethod
    def _decode(raw, status, operation):
        context = {"upstream_status": status, "operation": operation}
        if len(raw) > _MAX_RESPONSE:
            raise ModelInvalidResponse("AI 응답이 허용 크기를 초과했어요.", reason="response_size", **context)
        try:
            payload = json.loads(raw)
        except (ValueError, RecursionError):
            raise ModelInvalidJSON("Gemini HTTP 응답을 JSON으로 해석할 수 없어요.",
                                   reason="response_json", **context) from None
        if not isinstance(payload, dict):
            raise ModelInvalidResponse("알 수 없는 Gemini 응답 구조예요.", reason="response_shape", **context)
        return payload

    @model_request("model_metadata")
    def check_access(self) -> bool:
        """Check metadata visibility and whether the model advertises generateContent."""
        _METRICS.get().calls += 1
        payload, status = self._request("models.get")
        methods = payload.get("supportedGenerationMethods")
        if payload.get("name") != f"models/{self.model}" or not isinstance(methods, list):
            raise ModelInvalidResponse("모델 메타데이터를 확인할 수 없어요.",
                                       upstream_status=status, operation="models.get", reason="model_metadata")
        return "generateContent" in methods

    @model_request("model_metadata")
    def list_alternatives(self) -> tuple[list[str], bool]:
        """Read one page of model metadata without generating or selecting a replacement."""
        _METRICS.get().calls += 1
        payload, status = self._request("models.list")
        entries = payload.get("models", [])
        if not isinstance(entries, list):
            raise ModelInvalidResponse("Gemini 모델 목록을 해석할 수 없어요.",
                                       upstream_status=status, operation="models.list", reason="model_metadata")
        alternatives = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name, methods = entry.get("name"), entry.get("supportedGenerationMethods")
            if not isinstance(name, str) or not re.fullmatch(r"models/gemini-[a-z0-9.-]+", name):
                continue
            model_id = name.removeprefix("models/")
            if (model_id != self.model and not _NON_TEXT_MODEL.search(model_id)
                    and isinstance(methods, list) and "generateContent" in methods):
                alternatives.add(model_id)
        return sorted(alternatives), bool(payload.get("nextPageToken"))

    def _generate(self, body: dict) -> tuple[dict, int]:
        # Only retry the provider request. The assistant owns a single later state commit.
        _METRICS.get().calls += 1
        with model_phase("request_encode"):
            body = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        retry = 0
        while True:
            try:
                return self._request("generateContent", body, retry=retry)
            except ModelServiceUnavailable as error:
                if error.upstream_status != 503 or retry == self.max_503_retries:
                    error.retries_taken = retry
                    raise
                delay = 2 ** retry
                if self._remaining() <= delay:
                    error.retries_taken = retry
                    _LOGGER.info("gemini stage=%s phase=budget timeout_ms=0 error=%s", _STAGE.get(), error.code)
                    raise
                retry += 1

    @model_request("probe")
    def probe_text(self) -> str:
        """Make a plain generation request with a fixed, non-personal prompt."""
        token = _STAGE.set("probe")
        try:
            payload, status = self._generate({
                "contents": [{"role": "user", "parts": [{"text": "Reply with only the word OK."}]}],
                "generationConfig": {"maxOutputTokens": 128},
            })
            with model_phase("candidate_decode"):
                return _candidate_text(payload, status)[0]
        finally:
            _STAGE.reset(token)

    @model_request("generation")
    def generate(self, instruction: str, data: dict, schema: dict) -> dict:
        started = monotonic()
        error_code = "none"
        try:
            with model_phase("request_encode"):
                data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            body = {
                "systemInstruction": {"parts": [{"text": f"{instruction}\n\n{UNTRUSTED_DATA}"}]},
                "contents": [{"role": "user", "parts": [{"text": data_json}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": schema,
                    "maxOutputTokens": 8192 if _STAGE.get() == "startup_nodes" else 2048,
                    "temperature": 0.2,
                },
            }
            payload, status = self._generate(body)
            with model_phase("candidate_decode"):
                return self._result(payload, status)
        except ModelUnavailable as error:
            error_code = error.code
            raise
        finally:
            _LOGGER.info("gemini stage=%s phase=generation elapsed_ms=%d error=%s",
                         _STAGE.get(), _ms(monotonic() - started), error_code)

    @staticmethod
    def _result(payload: dict, status: int) -> dict:
        usage = payload.get("usageMetadata")
        if isinstance(usage, dict):
            counts = [usage.get(name) for name in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount")]
            if any(type(count) is int and count >= 0 for count in counts):
                _LOGGER.info("gemini stage=%s phase=usage prompt_tokens=%d output_tokens=%d thinking_tokens=%d",
                             _STAGE.get(), *(count if type(count) is int and count >= 0 else 0 for count in counts))
        text, finish_reason = _candidate_text(payload, status)
        context = {"upstream_status": status, "operation": "generateContent"}
        try:
            result = json.loads(text)
        except (ValueError, RecursionError):
            raise ModelInvalidJSON("Gemini 답변 텍스트를 JSON으로 해석할 수 없어요.",
                                   reason=finish_reason or "candidate_json", **context) from None
        if not isinstance(result, dict):
            raise ModelInvalidResponse("Gemini 답변은 JSON 객체여야 해요.", reason="candidate_json_shape", **context)
        return result


def _candidate_text(payload: dict, status: int) -> tuple[str, str | None]:
    context = {"upstream_status": status, "operation": "generateContent"}
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        feedback = payload.get("promptFeedback")
        reason = feedback.get("blockReason") if isinstance(feedback, dict) else None
        raise ModelInvalidResponse("Gemini가 답변 후보를 반환하지 않았어요.",
                                   reason=reason if isinstance(reason, str) and reason in _BLOCK_REASONS
                                   else "missing_candidate", **context)
    candidate = candidates[0]
    finish_reason = candidate.get("finishReason") if isinstance(candidate, dict) else None
    if not isinstance(finish_reason, str) or finish_reason not in _FINISH_REASONS:
        finish_reason = None
    try:
        parts = candidate["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    except (KeyError, TypeError, AttributeError):
        text = ""
    if not text.strip():
        raise ModelInvalidResponse("Gemini 답변 후보에 텍스트가 없어요.",
                                   reason=finish_reason or "candidate_shape", **context)
    return text, finish_reason
