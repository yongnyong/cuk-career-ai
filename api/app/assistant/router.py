"""FastAPI integration, composed with the existing application session dependency."""

from collections.abc import Callable
from datetime import datetime
from threading import Lock
from time import monotonic
from urllib.parse import quote
from typing import Literal
from pydantic import Field

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


class OpportunitySearchRequest(Contract):
    query: str = Field(max_length=600)
    kind: Literal["employment", "startup"]
    focus: str = Field(default="", max_length=240)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)


class OpportunityExplanationRequest(Contract):
    query: str = Field(max_length=600)
    posting_ids: list[Identifier] = Field(min_length=1, max_length=3)


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
        from .startup_plan import chat_plan, is_plan_message
        from .service_data import FOCUS, RETRIEVAL_QUERY
        focus = FOCUS.set(tuple(body.retrieval.posting_ids)) if body.retrieval is not None else None
        query = RETRIEVAL_QUERY.set(body.retrieval.query) if body.retrieval is not None else None
        try:
            state = service.store.get_state(user_id)
            if body.mode == "startup_intake" or body.context.startup_node_id or (
                state.startup_plan and is_plan_message(body.message)):
                return chat_plan(service, user_id, body)
            return service.chat(user_id, body)
        finally:
            if focus is not None:
                FOCUS.reset(focus)
            if query is not None:
                RETRIEVAL_QUERY.reset(query)

    @router.post("/opportunity-search")
    def search_opportunities(body: OpportunitySearchRequest, user_id: str = Depends(owner)):
        search = getattr(getattr(service, "data", None), "search", None)
        if search is None:
            raise HTTPException(503, "공고 검색을 준비 중이에요.")
        return search.search(body.query, body.kind, offset=body.offset, limit=body.limit, focus=body.focus)

    @router.post("/opportunity-explanation")
    def explain_opportunities(body: OpportunityExplanationRequest, user_id: str = Depends(limited_owner)):
        from ..career.opportunity_rag import explain
        search = getattr(getattr(service, "data", None), "search", None)
        if search is None:
            raise HTTPException(503, "공고 근거를 읽지 못했어요.")
        return explain(search, service.model, body.query, body.posting_ids)

    from .startup_plan import PlanPatch, StartupPlan, select_opportunity, update_plan
    from .startup_application import ApplicationRequest, apply_request, application_view

    @router.get("/startup-plan")
    def startup_plan(user_id: str = Depends(owner)):
        state = service.store.get_state(user_id)
        return {"revision": state.revision, "plan": state.startup_plan,
                "application_stale": application_view(state.startup_plan)}

    @router.post("/startup-application")
    def startup_application(body: ApplicationRequest, user_id: str = Depends(limited_owner)):
        from .errors import Conflict
        state = service.store.get_state(user_id)
        if state.revision != body.revision:
            raise Conflict("다른 창에서 변경됐어요. 최신 계획을 읽고 다시 적용해 주세요.")
        plan = state.startup_plan
        if not plan or not plan.idea or not plan.customer or not plan.project_id:
            raise HTTPException(422, "팀의 아이디어와 대상 고객을 먼저 등록해 주세요.")
        try:
            plan = apply_request(plan.model_copy(deep=True), body)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        state.startup_plan = update_plan(plan, {})
        service.store.save_state(user_id, state)
        return {"revision": state.revision + 1, "plan": state.startup_plan,
                "application_stale": application_view(state.startup_plan)}

    @router.patch("/startup-plan")
    def patch_startup_plan(body: PlanPatch, user_id: str = Depends(owner)):
        from .errors import Conflict
        state = service.store.get_state(user_id)
        if state.revision != body.revision:
            raise Conflict("다른 창에서 변경됐어요. 최신 계획을 읽고 다시 적용해 주세요.")
        if any(k not in ("idea", "customer", "artifacts", "goal", "action") or len(v) > 240 for k, v in body.fields.items()):
            raise HTTPException(422, "허용된 창업 정보만 수정할 수 있어요.")
        if body.fields.get("action") not in (None, "", "preorder", "demo", "launch", "competition", "customer"):
            raise HTTPException(422, "지원하는 창업 목표를 선택해 주세요.")
        plan = update_plan(state.startup_plan or StartupPlan(), body.fields, new_project=body.new_project)
        if body.opportunity_id:
            if not plan.idea or not plan.customer or not plan.goal or plan.action != "competition":
                raise HTTPException(422, "팀 정보와 대회·지원사업 목표를 먼저 설정해 주세요.")
            posting = service.data.get_startup_posting(body.opportunity_id)
            selected = select_opportunity(posting)
            for node in plan.nodes:
                if node.active and node.action == "choose_opportunity":
                    node.completed = True
            plan.opportunity = selected
        if body.node_id:
            node = next((n for n in plan.nodes if n.id == body.node_id), None)
            if node is None or body.completed is None:
                raise HTTPException(422, "이 계정의 퀘스트와 완료 여부를 확인하세요.")
            if body.completed and any(n.id in node.requires and not n.completed for n in plan.nodes):
                raise HTTPException(422, "먼저 필요한 시제품 퀘스트를 완료해 주세요.")
            node.completed = body.completed
        plan = update_plan(plan, {})
        state.startup_plan = plan
        service.store.save_state(user_id, state)
        return {"revision": state.revision + 1, "plan": plan}

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
