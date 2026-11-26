import json
import os
import sqlite3
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient  # noqa: E402

from app import main, push_postings  # noqa: E402
from app.career_db import CareerSessionLocal, Posting  # noqa: E402


def posting(pid, title="데이터 분석 인턴"):
    return {"id": pid, "type": "채용", "title": title, "org": "가상기업", "jobs": [], "required": [], "preferred": [],
            "versions": [{"version": 1, "deadline": "2026-12-31T23:59:00+09:00"}]}


def test_local_postings_reach_the_server_only_through_an_admin(tmp_path, monkeypatch):
    tag = uuid.uuid4().hex[:8]
    ids = [f"jk-{tag}-{n}" for n in range(3)]
    source = tmp_path / "career.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE postings (id VARCHAR(40) PRIMARY KEY, raw_hash VARCHAR(64) NOT NULL, data JSON, checked_at BIGINT NOT NULL)")
        db.execute("INSERT INTO postings VALUES (?,?,?,0)", (ids[0], "h1", json.dumps(posting(ids[0]), ensure_ascii=False)))
        db.execute("INSERT INTO postings VALUES (?,?,?,0)", (ids[1], "h2", None))  # 내린 공고
        db.execute("INSERT INTO postings VALUES (?,?,?,0)", (ids[2], "h3", json.dumps({"id": "other", "title": "x"})))  # 모양이 틀린 행
        db.execute("INSERT INTO postings VALUES (?,?,?,0)", (f"zz-{tag}", "h4", json.dumps(posting(f"zz-{tag}"))))
    rows = push_postings.read_rows(source, ["jk-"])
    assert [row["id"] for row in rows] == ids

    c = TestClient(main.app)
    user = f"push{tag}"

    def post(path, body):
        response = c.post(path, json=body)
        assert response.status_code == 200, response.text
        return response.json()

    assert c.post("/api/admin/postings/import", json={"rows": rows}).status_code == 401
    c.post("/api/auth/signup", json={"id": user, "password": "secret12"})
    assert c.post("/api/admin/postings/import", json={"rows": rows}).status_code == 403
    monkeypatch.setattr(main, "ADMIN_IDS", {user})
    try:
        assert push_postings.push(rows, post) == {"added": 2, "updated": 0, "unchanged": 0, "rejected": [ids[2]]}
        assert push_postings.push(rows, post) == {"added": 0, "updated": 0, "unchanged": 2, "rejected": [ids[2]]}
        rows[0]["raw_hash"], rows[0]["data"]["title"] = "h1b", "데이터 분석 인턴(정정)"
        assert push_postings.push(rows[:1], post)["updated"] == 1
        with CareerSessionLocal() as db:
            assert db.get(Posting, ids[0]).data["title"] == "데이터 분석 인턴(정정)"
            assert db.get(Posting, ids[1]).data is None
            assert db.get(Posting, ids[2]) is None
        assert any(o["id"] == ids[0] for o in c.get("/api/opportunities").json())
    finally:
        with CareerSessionLocal() as db:
            for pid in ids:
                row = db.get(Posting, pid)
                if row:
                    db.delete(row)
            db.commit()
