"""main.py에 개인 진로 비서를 붙인다.

- 로그인 계정: 세션 쿠키의 사용자. 기억·대화·문서를 Postgres에 저장한다.
- 공고: 브라우저가 X-Assistant-Focus로 웹 규칙 엔진의 추천 공고 ID를 보내면 그 안에서 고른다.
- 시연 계정: 서버 계정이 없으므로 서버가 무작위 값을 HttpOnly 쿠키(cuk_demo)로 발급해 브라우저를 구분한다.
  브라우저는 X-Demo-Id(시연 계정 이름, 예: demo-minji)와 X-Demo-Profile(시연 프로필, base64 JSON)만 보낸다.
  대화와 기억은 서버 메모리에만 잠시 두고, 시연 요청 전체에 분당 상한을 둔다(쿠키는 누구나 새로 받을 수 있으므로).
"""
import base64
import binascii
import json
import os
import re
import secrets
import time
from collections import OrderedDict, deque
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

from fastapi import Depends, HTTPException, Request, Response

from .contracts import Identifier
from .errors import ModelUnavailable
from .model import GeminiModel
from .router import make_router
from .service import AssistantService
from .service_data import FOCUS, ID, MemoryAssistantStore, RoutingStore, ServiceCareerData, make_pg_store

DEMO_ID = re.compile(r"^[a-z0-9-]{1,40}$")  # 시연 계정 이름(비밀 아님)
DEMO_COOKIE, DEMO_TOKEN = "cuk_demo", re.compile(r"^[A-Za-z0-9_-]{24,64}$")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
DEMO_LIMIT = 60  # 시연 요청 전체, 분당
MAX_PROFILE_BYTES = 8000
_recent: deque[float] = deque()  # 최근 1분간 시연 요청 시각


class _NoModel:
    """AI 키가 없을 때(로컬 개발·테스트). 모델이 필요한 질문은 '지금은 답할 수 없음'으로 끝난다."""

    def generate(self, instruction, data, schema):
        raise ModelUnavailable("AI 응답을 만들 수 없어요.")


def default_model():
    key = os.environ.get("GEMINI_API_KEY", "")
    name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    # 운영 측정(11/23): 호출 한 번이 1~8초, 질문 하나에 호출 1~3번. 8초·12초 상한에서는 시간 초과가 잦았다
    return GeminiModel(key, name, timeout=15, request_budget=25) if key else _NoModel()


def make_assistant(Base, SessionLocal, career_session, Posting, User, session_user, model=None):
    accounts = make_pg_store(Base, SessionLocal)
    demo_store = MemoryAssistantStore()
    demo_profiles: OrderedDict[str, dict] = OrderedDict()
    lock = Lock()

    def profile_of(user_id: str) -> dict | None:
        if user_id.startswith("demo:"):
            return demo_profiles.get(user_id)
        with SessionLocal() as db:
            user = db.get(User, user_id)
            return ((user.state or {}).get("profile") if user else None) or None

    data = ServiceCareerData(career_session, Posting, profile_of)
    from ..career.embeddings import configured_embeddings
    from ..career.opportunity_search import OpportunitySearch

    def postings_seen():
        from ..career_db import postings_version
        from ..startup_db import DEFAULT_DB
        with career_session() as db:
            startup = Path(DEFAULT_DB)
            return postings_version(db), startup.stat().st_mtime_ns if startup.is_file() else 0

    data.search = OpportunitySearch(career_session, data.public_postings, configured_embeddings(), postings_seen)
    store = RoutingStore(accounts, demo_store)
    service = AssistantService(data, store, model or default_model())

    # async: 여기서 정한 FOCUS가 같은 요청의 엔드포인트(스레드풀)까지 이어지도록 이벤트 루프의 컨텍스트에서 실행한다
    async def owner(request: Request, response: Response, user=Depends(session_user)):
        focus = [x for x in request.headers.get("x-assistant-focus", "").split(",") if ID.match(x)]
        FOCUS.set(tuple(focus) if "x-assistant-focus" in request.headers else None)
        if user:
            return user
        demo_id = request.headers.get("x-demo-id", "")
        if not DEMO_ID.match(demo_id):
            raise HTTPException(401, "로그인이 필요해요.")
        with lock:
            now = time.monotonic()
            while _recent and now - _recent[0] > 60:
                _recent.popleft()
            if len(_recent) >= DEMO_LIMIT:
                raise HTTPException(429, "시연 질문이 많아요. 잠시 뒤 다시 시도해 주세요.", headers={"Retry-After": "30"})
            _recent.append(now)
        token = request.cookies.get(DEMO_COOKIE, "")
        if not DEMO_TOKEN.match(token):
            token = secrets.token_urlsafe(24)
            response.set_cookie(DEMO_COOKIE, token, max_age=24 * 3600, httponly=True, samesite="lax",
                                secure=COOKIE_SECURE, path="/")
        uid = f"demo:{demo_id}:{token}"
        raw = request.headers.get("x-demo-profile", "")
        if raw:
            try:
                text = base64.b64decode(raw, validate=True)
                profile = json.loads(text) if len(text) <= MAX_PROFILE_BYTES else None
            except (binascii.Error, ValueError):
                profile = None
            if not isinstance(profile, dict):
                raise HTTPException(422, "시연 프로필을 읽을 수 없어요.")
            with lock:
                demo_profiles[uid] = profile
                demo_profiles.move_to_end(uid)
                while len(demo_profiles) > demo_store.max_users:
                    demo_profiles.popitem(last=False)
        return SimpleNamespace(id=uid)

    router = make_router(owner, service)

    @router.delete("/conversations/{conversation_id}", status_code=204)
    def clear_conversation(conversation_id: Identifier, user=Depends(owner)):
        store.clear_conversation(user.id, conversation_id)
        return Response(status_code=204)

    return router, accounts, service
