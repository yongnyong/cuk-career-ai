"""FastAPI integration, composed with the existing application session dependency."""

from collections.abc import Callable
from datetime import datetime
from threading import Lock
from time import monotonic
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from .contracts import (
    ChatRequest, ChatResult, Contract, DocumentRecord, Draft, DraftEdit, DraftRequest, Fact,
    Identifier, MemoryEdit, NarrativeRequest, NarrativeResult, Screen,
)
from .document_formats import MAX_UPLOAD_BYTES, MIME_TYPES
from .errors import AssistantError, UploadTooLarge
from .service import AssistantService


def _error(error: AssistantError) -> HTTPException:
    return HTTPException(error.status, {"code": error.code, "message": str(error)})


class AssistantRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def run(request: Request):
            try:
                response = await handler(request)
            except AssistantError as error:
                raise _error(error) from None
            except RequestValidationError:
                raise HTTPException(422, {"code": "invalid_input", "message": "요청 입력값을 확인해 주세요."}) from None
            response.headers["Cache-Control"] = "no-store"
            return response

        return run


class HistoryItem(Contract):
    timestamp: datetime
    message: str
    result: ChatResult
    context: Screen


class HistoryResponse(Contract):
    conversation_id: Identifier
    summary: str
    messages: list[HistoryItem]


class _RateLimit:
    def __init__(self, limit: int = 20, window: int = 60):
        self.limit = limit
        self.window = window
        self.entries: dict[str, int] = {}
        self.started = monotonic()
        self.lock = Lock()

    def check(self, user_id: str):
        with self.lock:
            now = monotonic()
            if now - self.started >= self.window:
                self.entries.clear()
                self.started = now
            count = self.entries.get(user_id, 0)
            if count >= self.limit:
                raise HTTPException(
                    429, {"code": "rate_limited", "message": "요청이 많아요. 잠시 후 다시 시도해 주세요."},
                    headers={"Retry-After": str(max(1, int(self.window - (now - self.started))))},
                )
            self.entries[user_id] = count + 1


def make_router(current_user: Callable, service: AssistantService) -> APIRouter:
    """Reuse main.current_user. Never read a user ID from headers, query, or body."""
    router = APIRouter(prefix="/api/assistant", tags=["career-assistant"], route_class=AssistantRoute)
    limit = _RateLimit()

    def owner(user=Depends(current_user)) -> str:
        return user.id

    def limited_owner(user_id: str = Depends(owner)) -> str:
        limit.check(user_id)
        return user_id

    @router.post("/chat", response_model=ChatResult)
    def chat(body: ChatRequest, user_id: str = Depends(limited_owner)):
        return service.chat(user_id, body)

    @router.get("/conversations/{conversation_id}", response_model=HistoryResponse)
    def history(conversation_id: Identifier, user_id: str = Depends(owner)):
        conversation = service.history(user_id, conversation_id)
        messages = [HistoryItem(timestamp=turn.timestamp, message=turn.message,
                                result=turn.result, context=turn.context) for turn in conversation.turns]
        return HistoryResponse(conversation_id=conversation_id, summary=conversation.summary, messages=messages)

    @router.get("/memory", response_model=list[Fact])
    def memory(user_id: str = Depends(owner)):
        return service.memory(user_id)

    @router.post("/memory", status_code=201, response_model=Fact)
    def add_memory(body: MemoryEdit, user_id: str = Depends(limited_owner)):
        return service.add_memory(user_id, body)

    @router.patch("/memory/{memory_id}", response_model=Fact)
    def edit_memory(memory_id: Identifier, body: MemoryEdit, user_id: str = Depends(limited_owner)):
        return service.edit_memory(user_id, memory_id, body)

    @router.delete("/memory/{memory_id}", status_code=204)
    def delete_memory(memory_id: Identifier, user_id: str = Depends(limited_owner)):
        service.delete_memory(user_id, memory_id)
        return Response(status_code=204)

    @router.post("/documents", status_code=201, response_model=DocumentRecord, openapi_extra={
        "requestBody": {"required": True, "content": {
            media: {"schema": {"type": "string", "format": "binary"}} for media in MIME_TYPES.values()
        }}
    })
    async def upload(request: Request, filename: str, user_id: str = Depends(limited_owner)):
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > MAX_UPLOAD_BYTES:
                raise UploadTooLarge("문서 크기는 최대 5MiB예요.")
            content.extend(chunk)
        return await run_in_threadpool(service.documents.upload, user_id, filename, bytes(content))

    @router.get("/documents/{document_id}", response_model=DocumentRecord)
    def get_document(document_id: Identifier, user_id: str = Depends(owner)):
        return service.documents.get(user_id, document_id)

    @router.post("/documents/{document_id}/draft", response_model=Draft)
    def create_draft(document_id: Identifier, body: DraftRequest, user_id: str = Depends(limited_owner)):
        return service.documents.generate(user_id, document_id, body)

    @router.patch("/documents/{document_id}/draft", response_model=Draft)
    def edit_draft(document_id: Identifier, body: DraftEdit, user_id: str = Depends(limited_owner)):
        return service.documents.edit(user_id, document_id, body)

    @router.get("/documents/{document_id}/draft/download", response_class=Response)
    def download(document_id: Identifier, user_id: str = Depends(limited_owner)):
        filename, media, contents = service.documents.download(user_id, document_id)
        return Response(contents, media_type=media, headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "X-Content-Type-Options": "nosniff",
        })

    @router.post("/narrative", response_model=NarrativeResult)
    def narrative(body: NarrativeRequest, user_id: str = Depends(limited_owner)):
        profile = service.data.get_profile(user_id)
        return service.documents.narrative(profile, body.topic, service.memory(user_id), options=body)

    return router
