"""Exercise the existing account endpoints and assistant together without Gemini."""

from secrets import token_urlsafe

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, update
from sqlalchemy.orm import sessionmaker

from . import model
from .repository import JsonAssistantStore, MockCareerData
from .router import make_router
from .service import AssistantService
from .test_chat import NOW, FakeModel

ASSISTANT = "/api/assistant"
ALICE, BOB = "http_alice", "http_bob"
CONVERSATION = "career-demo-1"
CONTEXT = {"page": "tree", "jobId": "mock-ai-engineer", "skillId": "mock-data-analysis"}
SKILL_CHAT = {
    "conversationId": CONVERSATION,
    "requestId": "turn-1",
    "message": "이 노드의 선수학습은 뭔가요?",
    "context": CONTEXT,
}
SKILL_ANSWER = "선택한 데이터 분석 노드의 선수학습은 Python 기초예요."


@pytest.fixture
def http_app(tmp_path, monkeypatch):
    # main creates its engine and tables at import time. A focused test run must
    # therefore set a throwaway URL before importing an uninitialized module.
    with monkeypatch.context() as importing:
        importing.setenv("DATABASE_URL", "sqlite://")
        importing.setenv("COOKIE_SECURE", "0")
        importing.setenv("ADMIN_IDS", "")
        from app import main

    engine = create_engine(URL.create("sqlite", database=str(tmp_path / "accounts.sqlite3")))
    main.Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)

    def temporary_db():
        with sessions() as db:
            yield db

    def unexpected_gemini(*args, **kwargs):
        pytest.fail("The local HTTP suite attempted a Gemini request")

    monkeypatch.setattr(model, "urlopen", unexpected_gemini)
    monkeypatch.setattr(main, "COOKIE_SECURE", True)
    test_model = FakeModel()
    service = AssistantService(
        MockCareerData({ALICE: "demo001", BOB: "demo002"}),
        JsonAssistantStore(tmp_path / "assistant"),
        test_model,
        lambda: NOW,
    )
    app = FastAPI()
    # Re-register routes so dependency overrides belong to this app.
    # main에는 실제 서비스용 비서 라우트가 이미 있으므로 빼고, 아래의 테스트용 비서만 등록한다
    existing = APIRouter()
    existing.routes.extend(
        route for route in main.app.router.routes if not getattr(route, "path", "").startswith("/api/assistant")
    )
    app.include_router(existing)
    app.dependency_overrides[main.get_db] = temporary_db
    app.include_router(make_router(main.current_user, service))
    try:
        yield app, test_model, sessions, main.SessionRow
    finally:
        engine.dispose()


def client(app):
    return TestClient(app, base_url="https://assistant.test")


def sign_in(http, user_id):
    credentials = {"id": user_id, "password": token_urlsafe(12)}
    assert http.post("/api/auth/signup", json=credentials).status_code == 200
    assert http.post("/api/auth/logout").status_code == 200
    assert http.get("/api/me").status_code == 401

    signed_in = http.post("/api/auth/login", json=credentials)
    assert signed_in.status_code == 200
    assert signed_in.json()["id"] == user_id
    session_header = signed_in.headers["set-cookie"].lower()
    assert all(flag in session_header for flag in ("cuk_session=", "httponly", "samesite=lax", "secure", "path=/"))
    assert http.get("/api/me").json()["id"] == user_id


def test_session_cookie_is_required_and_logout_revokes_it(http_app):
    app, fake_model, _, _ = http_app
    with client(app) as http:
        assert http.post(
            f"{ASSISTANT}/chat?userId={ALICE}", json=SKILL_CHAT, headers={"X-User-Id": ALICE},
        ).status_code == 401
        for path in (f"/conversations/{CONVERSATION}", "/memory"):
            denied = http.get(f"{ASSISTANT}{path}")
            assert denied.status_code == 401
            assert denied.json() == {"detail": "로그인이 필요해요."}
        sign_in(http, ALICE)
        old_cookie = http.cookies.get("cuk_session")
        assert old_cookie
        assert http.post("/api/auth/logout").status_code == 200
        assert http.cookies.get("cuk_session") is None

    with client(app) as replay:
        replay.cookies.set("cuk_session", old_cookie)
        assert replay.post(f"{ASSISTANT}/chat", json=SKILL_CHAT).status_code == 401
    assert not fake_model.calls


def test_expired_session_is_rejected_with_cookie_still_present(http_app):
    app, fake_model, sessions, session_row = http_app
    with client(app) as http:
        sign_in(http, ALICE)
        with sessions.begin() as db:
            expired = db.execute(update(session_row).where(session_row.user_id == ALICE).values(expires_at=0))
            assert expired.rowcount == 1
        assert http.cookies.get("cuk_session")
        assert http.post(f"{ASSISTANT}/chat", json=SKILL_CHAT).status_code == 401
    assert not fake_model.calls


def test_chat_context_history_and_retry_stay_in_one_conversation(http_app):
    app, fake_model, _, _ = http_app
    with client(app) as http:
        sign_in(http, ALICE)
        fake_model.answer = {"answer": SKILL_ANSWER}
        first = http.post(f"{ASSISTANT}/chat", json=SKILL_CHAT)
        assert first.status_code == 200 and first.headers["cache-control"] == "no-store"
        assert first.json() == {
            "answer": SKILL_ANSWER,
            "conversationId": CONVERSATION,
            "mockData": True,
            "memoryUpdated": False,
            "needsConfirmation": [],
            "contextIssues": [],
            "opportunities": [],
            "document": None,
        }
        _, tree_payload, _ = fake_model.calls[-1]
        assert tree_payload["page"] == "tree"
        assert (tree_payload["selectedSkill"]["jobId"], tree_payload["selectedSkill"]["skillId"]) == (
            CONTEXT["jobId"], CONTEXT["skillId"],
        )

        subsequent = {
            "conversationId": CONVERSATION, "requestId": "turn-2",
            "message": "그 기술을 어떻게 연습할까요?", "context": {"page": "profile"},
        }
        fake_model.answer = {"answer": "간단한 파이썬 연습 문제부터 풀어 보세요."}
        second = http.post(f"{ASSISTANT}/chat", json=subsequent)
        assert second.status_code == 200 and second.json()["conversationId"] == first.json()["conversationId"]
        _, profile_payload, _ = fake_model.calls[-1]
        assert profile_payload["page"] == "profile" and "selectedSkill" not in profile_payload
        assert profile_payload["conversation"]["recent"] == [{
            "page": "tree", "user": SKILL_CHAT["message"], "assistant": SKILL_ANSWER,
        }]

        retry = http.post(f"{ASSISTANT}/chat", json=subsequent)
        assert retry.status_code == 200 and retry.json() == second.json()
        conflict = http.post(f"{ASSISTANT}/chat", json={**subsequent, "message": "다른 질문이 있어요?"})
        assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "conflict"
        assert len(fake_model.calls) == 2

        history = http.get(f"{ASSISTANT}/conversations/{CONVERSATION}")
        assert history.status_code == 200 and history.headers["cache-control"] == "no-store"
        assert set(history.json()) == {"conversationId", "summary", "messages"}
        turns = history.json()["messages"]
        assert len(turns) == 2 and set(turns[0]) == {"timestamp", "message", "result", "context"}
        assert turns[0]["timestamp"] == "2026-11-22T01:00:00Z"
        assert turns[0]["context"] == {**CONTEXT, "opportunityId": None, "documentId": None}
        assert turns[1]["context"] == {
            "page": "profile", "jobId": None, "skillId": None, "opportunityId": None, "documentId": None,
        }
        assert [turn["result"] for turn in turns] == [first.json(), second.json()]


def test_signed_in_users_cannot_share_history_or_memory_via_id_or_header(http_app):
    app, fake_model, _, _ = http_app
    with client(app) as alice, client(app) as bob:
        sign_in(alice, ALICE)
        sign_in(bob, BOB)
        fake_model.answer = {"answer": "첫 번째 가상 계정의 답변입니다."}
        first = alice.post(f"{ASSISTANT}/chat", json=SKILL_CHAT)
        assert first.status_code == 200
        recorded = alice.post(f"{ASSISTANT}/memory", json={"kind": "interest", "value": "가상 로보틱스"})
        assert recorded.status_code == 201
        memory_id = recorded.json()["id"]

        forged = {"X-User-Id": ALICE}
        history_path = f"{ASSISTANT}/conversations/{CONVERSATION}"
        assert bob.get(f"{history_path}?userId={ALICE}", headers=forged).status_code == 404
        assert bob.get(f"{ASSISTANT}/memory", headers=forged).json() == []
        assert bob.delete(f"{ASSISTANT}/memory/{memory_id}", headers=forged).status_code == 404

        fake_model.answer = {"answer": "두 번째 가상 계정의 답변입니다."}
        second = bob.post(f"{ASSISTANT}/chat?userId={ALICE}", json=SKILL_CHAT, headers=forged)
        assert second.status_code == 200 and second.json()["answer"] != first.json()["answer"]
        assert len(fake_model.calls) == 2
        assert fake_model.calls[-1][1]["conversation"]["recent"] == []
        assert [t["result"] for t in alice.get(history_path).json()["messages"]] == [first.json()]
        assert [t["result"] for t in bob.get(history_path).json()["messages"]] == [second.json()]
        assert [item["id"] for item in alice.get(f"{ASSISTANT}/memory").json()] == [memory_id]


@pytest.mark.parametrize("changes", [
    {"message": "   "},
    {"message": "x" * 2001},
    {"message": 19},
    {"conversationId": "invalid id"},
    {"context": {"page": "tree", "skillId": ["mock-data-analysis"]}},
    {"context": {"page": "tree", "extraField": "unknown"}},
    {"userId": ALICE},
])
def test_invalid_chat_body_is_rejected_before_model_and_storage(http_app, changes):
    app, fake_model, _, _ = http_app
    with client(app) as http:
        sign_in(http, ALICE)
        response = http.post(f"{ASSISTANT}/chat", json={**SKILL_CHAT, **changes})
        assert response.status_code == 422
        assert response.json() == {"detail": {"code": "invalid_input", "message": "요청 입력값을 확인해 주세요."}}
        assert http.get(f"{ASSISTANT}/conversations/{CONVERSATION}").status_code == 404
    assert not fake_model.calls


def test_malformed_json_bad_history_id_and_unresolved_node(http_app):
    app, fake_model, _, _ = http_app
    with client(app) as http:
        sign_in(http, ALICE)
        invalid_json = http.post(f"{ASSISTANT}/chat", content=b"{", headers={"Content-Type": "application/json"})
        assert invalid_json.status_code == 422 and invalid_json.json()["detail"]["code"] == "invalid_input"
        invalid_id = http.get(f"{ASSISTANT}/conversations/invalid%20id")
        assert invalid_id.status_code == 422 and invalid_id.json()["detail"]["code"] == "invalid_input"

        unknown = http.post(f"{ASSISTANT}/chat", json={
            **SKILL_CHAT, "context": {**CONTEXT, "skillId": "unknown-node"},
        })
        assert unknown.status_code == 200
        assert unknown.json()["contextIssues"] == ["unknown_skill"]
    assert not fake_model.calls


def test_openapi_and_existing_posting_chat_coexist(http_app):
    app, fake_model, _, _ = http_app
    with client(app) as http:
        schema = http.get("/openapi.json")
        assert schema.status_code == 200
        paths = schema.json()["paths"]
        assert "post" in paths["/api/chat"] and "post" in paths[f"{ASSISTANT}/chat"]
        components = schema.json()["components"]["schemas"]
        assert set(components["ChatRequest"]["properties"]) == {"message", "context", "conversationId", "requestId"}
        assert {"opportunityId", "jobId", "skillId"} <= set(components["Screen"]["properties"])

        legacy = http.post("/api/chat", json={"oppId": "missing-fixture", "question": "언제가 마감인가요?"})
        assert legacy.status_code == 404 and isinstance(legacy.json()["detail"], str)
    assert not fake_model.calls
