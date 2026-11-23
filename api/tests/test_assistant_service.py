"""개인 진로 비서를 실제 서비스 자료(계정 프로필·공고 DB·Postgres 저장)에 연결한 부분."""
import base64
import json
import os
import tempfile

# 파일 DB를 써야 연결이 바뀌어도 테이블이 남는다(다른 테스트 파일과 같은 방식)
for key, name in (("DATABASE_URL", "test.db"), ("CAREER_DATABASE_URL", "career.db")):
    os.environ.setdefault(key, "sqlite:///" + os.path.join(tempfile.mkdtemp(), name).replace("\\", "/"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.assistant import model as model_module, wiring  # noqa: E402
from app.assistant.contracts import UserState  # noqa: E402
from app.assistant.errors import Conflict  # noqa: E402
from app.assistant.service_data import profile_facts, to_opportunity  # noqa: E402
from app.assistant.test_chat import CERT_MESSAGE, FakeModel  # noqa: E402
from app.career_db import CareerSessionLocal, Posting  # noqa: E402

PROFILE = {"pseudoId": "secretid9", "admissionYear": 2024, "departmentId": "ai", "grade": 3, "status": "재학",
           "jobId": "ai-research", "careerInterest": "employment", "skills": {"SK-PY-01": "verified", "AI-ML": "self"},
           "startup": {"region": "부산", "birthYear": 2003}, "scores": {"SK-TOEIC": "905"}}
OPP = {
    "id": "w24-77", "title": "AI 데이터 인턴 모집", "org": "가상기관", "type": "현장실습", "isVirtual": False,
    "required": [{"key": "grade", "label": "3·4학년", "grades": [3, 4], "src": "§1"},
                 {"key": "region", "label": "서울 거주", "regions": ["서울"], "src": "§1"}],
    "documents": ["이력서"], "applyUrl": "https://example.org/apply",
    "sections": [{"id": "§1", "title": "지원 대상", "text": "3·4학년 재학생"}],
    "versions": [{"version": 2, "checkedAt": "2026-11-20T00:00:00Z", "deadline": "2099-12-10T18:00:00+09:00"}],
}


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(model_module, "urlopen", lambda *a, **k: pytest.fail("Gemini를 실제로 호출함"))
    m = FakeModel()
    monkeypatch.setattr(main.assistant_service, "model", m)
    monkeypatch.setattr(main.assistant_service.documents, "model", m)
    wiring._recent.clear()
    yield m
    wiring._recent.clear()


def demo_headers(demo_id, profile=PROFILE):
    raw = base64.b64encode(json.dumps(profile, ensure_ascii=False).encode()).decode()
    return {"x-demo-id": demo_id, "x-demo-profile": raw}


def test_profile_sends_only_study_fields():
    facts = profile_facts(PROFILE).facts
    text = json.dumps([f.model_dump() for f in facts], ensure_ascii=False)
    assert "3" in {f.value for f in facts if f.kind == "grade"}
    assert any(f.kind == "goal" and f.value.startswith("취업") for f in facts)
    sources = {f.value: f.source for f in facts if f.kind == "skill"}
    assert set(sources.values()) == {"system", "user_claim"}  # 인증한 노드와 스스로 표시한 노드를 구분
    for secret in ("secretid9", "2024", "부산", "2003", "905"):
        assert secret not in text


def test_posting_conversion_keeps_rule_conditions_and_skips_unknown_deadline():
    o = to_opportunity(OPP)
    assert o.type == "employment" and o.version == 2 and o.source_url == "https://example.org/apply"
    assert [(c.kind, c.values) for c in o.conditions] == [("grade", ["3", "4"]), ("other", [])]
    assert to_opportunity({**OPP, "deadlineStatus": "unknown"}) is None
    assert to_opportunity({**OPP, "id": "잘못된 id"}) is None


def test_store_rejects_stale_revision_and_account_delete_removes_state():
    store = main.assistant_store
    store.save_state("storeuser1", UserState())
    first = store.get_state("storeuser1")
    store.save_state("storeuser1", first)
    with pytest.raises(Conflict):
        store.save_state("storeuser1", first)  # 이미 다른 요청이 저장한 revision
    with main.SessionLocal() as db:
        store.delete_user(db, "storeuser1")
        db.commit()
    assert store.get_state("storeuser1").revision == 0


def test_demo_chat_uses_header_profile_and_is_isolated(fake):
    with CareerSessionLocal() as s:
        s.merge(Posting(id=OPP["id"], raw_hash="h", data=OPP, checked_at=1))
        s.commit()
    main.assistant_service.data._cache = (0.0, {})
    c = TestClient(main.app)
    assert c.post("/api/assistant/chat", json={"message": "안녕"}).status_code == 401

    r = c.post("/api/assistant/chat", json={"message": "나한테 맞는 공고 알려줘", "conversationId": "main"},
               headers=demo_headers("demo-aaaa1111"))
    assert r.status_code == 200, r.text
    opp = r.json()["opportunities"][0]
    assert opp["id"] == "w24-77"
    assert {x["label"]: x["verdict"] for x in opp["conditions"]} == {"3·4학년": "pass", "서울 거주": "check"}

    r = c.post("/api/assistant/chat", json={"message": CERT_MESSAGE, "conversationId": "main"},
               headers=demo_headers("demo-aaaa1111"))
    assert r.json()["memoryUpdated"] is True
    mine = c.get("/api/assistant/memory", headers={"x-demo-id": "demo-aaaa1111"}).json()
    assert [m["value"] for m in mine] == ["SQLD"]
    assert c.get("/api/assistant/memory", headers={"x-demo-id": "demo-bbbb2222"}).json() == []
    history = c.get("/api/assistant/conversations/main", headers={"x-demo-id": "demo-aaaa1111"}).json()
    assert len(history["messages"]) == 2
    assert c.delete("/api/assistant/conversations/main", headers={"x-demo-id": "demo-aaaa1111"}).status_code == 204
    assert c.get("/api/assistant/conversations/main", headers={"x-demo-id": "demo-aaaa1111"}).status_code == 404
    sent = json.dumps([call[1] for call in fake.calls], ensure_ascii=False)
    assert "secretid9" not in sent and "부산" not in sent


def test_account_memory_is_saved_in_db_and_deleted_with_account(fake):
    c = TestClient(main.app)
    c.post("/api/auth/signup", json={"id": "memuser1", "password": "secret12"})
    c.put("/api/me/state", json={"state": {"profile": PROFILE}})
    r = c.post("/api/assistant/chat", json={"message": CERT_MESSAGE, "conversationId": "main"})
    assert r.status_code == 200 and r.json()["memoryUpdated"] is True
    assert main.assistant_store.get_state("memuser1").memory[0].value == "SQLD"
    assert [m["value"] for m in c.get("/api/assistant/memory").json()] == ["SQLD"]
    c.delete("/api/me")
    assert main.assistant_store.get_state("memuser1").revision == 0


def test_demo_requests_have_a_global_cap(fake, monkeypatch):
    monkeypatch.setattr(wiring, "DEMO_LIMIT", 3)
    c = TestClient(main.app)
    codes = [c.get("/api/assistant/memory", headers={"x-demo-id": f"demo-cap-{i:04d}"}).status_code for i in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_rule_engine_focus_limits_which_postings_are_recommended(fake):
    other = {**OPP, "id": "w24-88", "title": "관련 없는 판매직 모집", "required": []}
    with CareerSessionLocal() as s:
        for o in (OPP, other):
            s.merge(Posting(id=o["id"], raw_hash="h", data=o, checked_at=1))
        s.commit()
    main.assistant_service.data._cache = (0.0, {})
    c = TestClient(main.app)
    ask = {"message": "나한테 맞는 공고 알려줘", "conversationId": "focus"}
    loose = c.post("/api/assistant/chat", json=ask, headers=demo_headers("demo-focus001")).json()
    assert "w24-88" in [o["id"] for o in loose["opportunities"]]
    focused = c.post("/api/assistant/chat", json=ask,
                     headers={**demo_headers("demo-focus002"), "x-assistant-focus": "w24-77,bad id!,missing-id"}).json()
    assert [o["id"] for o in focused["opportunities"]] == ["w24-77"]


def test_demo_identity_is_a_server_cookie_not_the_header(fake):
    a, b = TestClient(main.app), TestClient(main.app)
    for c in (a, b):  # 같은 시연 계정 이름이어도 쿠키(브라우저)가 다르면 대화·기억이 섞이지 않는다
        assert c.get("/api/assistant/memory", headers={"x-demo-id": "demo-minji"}).status_code == 200
        assert c.cookies.get("cuk_demo")
    assert a.cookies.get("cuk_demo") != b.cookies.get("cuk_demo")
    a.post("/api/assistant/chat", json={"message": CERT_MESSAGE}, headers=demo_headers("demo-minji"))
    assert [m["value"] for m in a.get("/api/assistant/memory", headers={"x-demo-id": "demo-minji"}).json()] == ["SQLD"]
    assert b.get("/api/assistant/memory", headers={"x-demo-id": "demo-minji"}).json() == []


def test_demo_store_caps_documents_and_total_bytes():
    from app.assistant.contracts import DocumentRecord, TemplateField
    from app.assistant.service_data import MemoryAssistantStore

    def record(i):
        return DocumentRecord(id=f"doc{i}", filename="a.json", format="json", fields=[TemplateField(id="f", label="이름")])

    store = MemoryAssistantStore(max_bytes=100)
    store.create_document("demo:a", record(1), b"x" * 60)
    with pytest.raises(Conflict):
        store.create_document("demo:a", record(2), b"x")  # 시연 계정은 1건까지
    store.create_document("demo:b", record(3), b"x" * 60)  # 합계 120 > 100 → 오래된 사용자(a)를 지운다
    assert store.total == 60 and store.get_state("demo:a").documents == {}
    with pytest.raises(Conflict):
        store.create_document("demo:c", record(4), b"x" * 101)


def test_account_delete_also_removes_legacy_chat_rows():
    from sqlalchemy import text
    with main.SessionLocal() as db:
        db.execute(text("CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY, user_id VARCHAR(16), text TEXT)"))
        db.execute(text("INSERT INTO chat_messages (user_id, text) VALUES ('olduser1', '예전 대화')"))
        db.commit()
    c = TestClient(main.app)
    c.post("/api/auth/signup", json={"id": "olduser1", "password": "secret12"})
    c.delete("/api/me")
    with main.SessionLocal() as db:
        assert db.execute(text("SELECT count(*) FROM chat_messages WHERE user_id='olduser1'")).scalar() == 0
