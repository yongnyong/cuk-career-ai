class AssistantError(Exception):
    status = 400
    code = "invalid_request"


class NotFound(AssistantError):
    status = 404
    code = "not_found"


class Conflict(AssistantError):
    status = 409
    code = "conflict"


class StorageUnavailable(AssistantError):
    status = 503
    code = "storage_unavailable"


class ModelUnavailable(AssistantError):
    status = 503
    code = "model_unavailable"

    def __init__(self, message: str, *, upstream_status: int | None = None,
                 operation: str | None = None, reason: str | None = None):
        super().__init__(message)
        self.upstream_status = upstream_status
        self.operation = operation
        self.reason = reason


class ModelTimeout(ModelUnavailable):
    status = 504
    code = "model_timeout"


class ModelRateLimited(ModelUnavailable):
    status = 429
    code = "model_rate_limited"


class ModelServiceUnavailable(ModelUnavailable):
    code = "model_service_unavailable"
    retries_taken = 0


class ModelNotFound(ModelUnavailable):
    status = 502
    code = "model_not_found"


class ModelAuthenticationError(ModelUnavailable):
    status = 502
    code = "model_authentication"


class ModelAccessDenied(ModelUnavailable):
    status = 502
    code = "model_access_denied"


class ModelRequestRejected(ModelUnavailable):
    status = 502
    code = "model_request_rejected"


class ModelNetworkError(ModelUnavailable):
    code = "model_network_error"


class ModelInvalidResponse(ModelUnavailable):
    status = 502
    code = "model_invalid_response"


class ModelInvalidJSON(ModelInvalidResponse):
    code = "model_invalid_json"


class UnsupportedDocument(AssistantError):
    status = 415
    code = "unsupported_document"


class UploadTooLarge(AssistantError):
    status = 413
    code = "upload_too_large"
