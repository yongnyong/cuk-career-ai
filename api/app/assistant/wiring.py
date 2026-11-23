"""main.py에 개인 진로 비서를 붙인다.

- 로그인 계정: 세션 쿠키의 사용자. 기억·대화·문서를 Postgres에 저장한다.
- 공고: 브라우저가 X-Assistant-Focus로 웹 규칙 엔진의 추천 공고 ID를 보내면 그 안에서 고른다.
- 시연 계정: 서버 계정이 없으므로 브라우저가 X-Demo-Id(무작위 ID)와 X-Demo-Profile(시연 프로필, base64 JSON)을 보낸다.
  대화와 기억은 서버 메모리에만 잠시 두고, 시연 요청 전체에 분당 상한을 둔다(ID는 누구나 새로 만들 수 있으므로).
"""
import base64
import binascii
import json
import os
import re
import time
from collections import OrderedDict, deque
from threading import Lock
from types import SimpleNamespace

from fastapi import Depends, HTTPException, Request, Response

from .contracts import Identifier
from .errors import ModelUnavailable
from .model import GeminiModel
from .router import make_router
from .service import AssistantService
from .service_data import FOCUS, ID, MemoryAssistantStore, RoutingStore, ServiceCareerData, make_pg_store

DEMO_ID = re.compile(r"^[a-z0-9-]{8,64}$")
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
    return GeminiModel(key, name, timeout=8) if key else _NoModel()


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
    store = RoutingStore(accounts, demo_store)
    service = AssistantService(data, store, model or default_model())

    # async: 여기서 정한 FOCUS가 같은 요청의 엔드포인트(스레드풀)까지 이어지도록 이벤트 루프의 컨텍스트에서 실행한다
    async def owner(request: Request, user=Depends(session_user)):
        focus = [x for x in request.headers.get("x-assistant-focus", "").split(",") if ID.match(x)][:12]
        FOCUS.set(tuple(focus))
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
        uid = f"demo:{demo_id}"
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
