import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db").replace("\\", "/")
os.environ["CAREER_DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "career.db").replace("\\", "/")

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402

PW = "test-password-1"


def client():
    return TestClient(main.app)


def test_signup_sets_httponly_cookie_and_me_works():
    c = client()
    r = c.post("/api/auth/signup", json={"id": "alice01", "password": PW})
    assert r.status_code == 200 and r.json() == {"id": "alice01", "state": None, "admin": False}
    assert "httponly" in r.headers["set-cookie"].lower()
    assert c.get("/api/me").json()["id"] == "alice01"


def test_password_is_stored_hashed():
    with main.SessionLocal() as db:
        u = db.get(main.User, "alice01")
        assert u.password_hash.startswith("$argon2") and PW not in u.password_hash


def test_signup_validation_and_duplicate():
    c = client()
    assert c.post("/api/auth/signup", json={"id": "Ab", "password": PW}).status_code == 422
    assert c.post("/api/auth/signup", json={"id": "short01", "password": "123"}).status_code == 422
    assert c.post("/api/auth/signup", json={"id": "alice01", "password": PW}).status_code == 409


def test_login_wrong_password_and_unknown_user_look_the_same():
    c = client()
    a = c.post("/api/auth/login", json={"id": "alice01", "password": "wrong-pass"})
    b = c.post("/api/auth/login", json={"id": "nobody99", "password": "wrong-pass"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()
    assert c.get("/api/me").status_code == 401


def test_state_roundtrip_across_logins():
    c = client()
    assert c.post("/api/auth/login", json={"id": "alice01", "password": PW}).status_code == 200
    state = {"profile": {"departmentId": "ai", "grade": 3}, "followed": ["opp-1"]}
    assert c.put("/api/me/state", json={"state": state}).status_code == 200
    c.post("/api/auth/logout")
    assert c.get("/api/me").status_code == 401
    other = client()  # 다른 기기
    assert other.post("/api/auth/login", json={"id": "alice01", "password": PW}).json()["state"] == state


def test_state_requires_login_and_is_per_user():
    assert client().put("/api/me/state", json={"state": {}}).status_code == 401
    c = client()
    c.post("/api/auth/signup", json={"id": "bob0001", "password": PW})
    assert c.get("/api/me").json()["state"] is None


def test_state_size_limit():
    c = client()
    c.post("/api/auth/login", json={"id": "bob0001", "password": PW})
    assert c.put("/api/me/state", json={"state": {"x": "a" * 250_000}}).status_code == 413


def test_login_rate_limit():
    c = client()
    for _ in range(5):
        assert c.post("/api/auth/login", json={"id": "bob0001", "password": "nope-nope"}).status_code == 401
    assert c.post("/api/auth/login", json={"id": "bob0001", "password": PW}).status_code == 429
    main._failures.clear()


def test_delete_account_removes_user_and_sessions():
    c = client()
    c.post("/api/auth/login", json={"id": "bob0001", "password": PW})
    assert c.delete("/api/me").status_code == 200
    assert c.get("/api/me").status_code == 401
    assert c.post("/api/auth/login", json={"id": "bob0001", "password": PW}).status_code == 401


def test_admin_overview_requires_admin(monkeypatch):
    import app.main as m

    c = client()
    c.post("/api/auth/signup", json={"id": "boss01", "password": "secret12"})
    assert c.get("/api/admin/overview").status_code == 403
    monkeypatch.setattr(m, "ADMIN_IDS", {"boss01"})
    assert c.get("/api/me").json()["admin"] is True
    body = c.get("/api/admin/overview").json()
    assert body["users"] >= 1 and set(body["postings"]) == {"total", "open", "pendingReview", "bySource", "byType"}
    assert "boss01" not in str(body)


def test_catalog_is_public_to_read_and_admin_only_to_write(monkeypatch):
    import app.main as m

    c = client()
    assert c.get("/api/catalog").json() == {"skills": {}, "jobs": {}}
    c.post("/api/auth/signup", json={"id": "editor01", "password": "secret12"})
    body = {"skills": {"ADM-1": {"id": "ADM-1", "name": "새 노드"}}, "jobs": {}}
    assert c.put("/api/admin/catalog", json=body).status_code == 403
    monkeypatch.setattr(m, "ADMIN_IDS", {"editor01"})
    assert c.put("/api/admin/catalog", json=body).status_code == 200
    assert client().get("/api/catalog").json()["skills"]["ADM-1"]["name"] == "새 노드"
