import json
import os
import sqlite3
import tempfile
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db").replace("\\", "/"))
os.environ.setdefault("CAREER_DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "career.db").replace("\\", "/"))

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
        # 서버 안에서는 Git의 공유 파일을 같은 규칙으로 바로 넣는다
        lines = [json.dumps({"table": "postings", "row": {"id": pid, "raw_hash": "s1", "data": posting(pid), "checked_at": 0}})
                 for pid in (ids[0], ids[2])] + [""]
        assert push_postings.load_jsonl(lines, CareerSessionLocal, Posting) == {"added": 1, "updated": 1, "unchanged": 0, "rejected": []}
        assert push_postings.load_jsonl(lines, CareerSessionLocal, Posting)["unchanged"] == 2
    finally:
        with CareerSessionLocal() as db:
            for pid in ids:
                row = db.get(Posting, pid)
                if row:
                    db.delete(row)
            db.commit()


def test_posting_list_is_cached_until_postings_change_and_answers_304():
    c = TestClient(main.app)
    first = c.get("/api/opportunities")
    etag = first.headers["etag"]
    assert first.status_code == 200 and first.headers["cache-control"] == "no-cache"
    assert c.get("/api/opportunities", headers={"If-None-Match": etag}).status_code == 304
    plain = c.get("/api/opportunities", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers and plain.json() == first.json()
    pid = f"jk-{uuid.uuid4().hex[:8]}"
    with CareerSessionLocal() as db:
        db.add(Posting(id=pid, raw_hash="h", data=posting(pid), checked_at=2_000_000_000))
        db.commit()
    try:
        changed = c.get("/api/opportunities", headers={"If-None-Match": etag})
        assert changed.status_code == 200 and changed.headers["etag"] != etag
        assert any(o["id"] == pid for o in changed.json())
    finally:
        with CareerSessionLocal() as db:
            db.delete(db.get(Posting, pid))
            db.commit()
    assert all(o["id"] != pid for o in c.get("/api/opportunities").json())


def test_search_rereads_postings_only_when_the_version_changes():
    from app.career.opportunity_search import OpportunitySearch
    from app.career_db import CareerBase
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    CareerBase.metadata.create_all(engine)
    reads, version = [], [1]
    source_of = lambda pid: {"name": "가상", "url": f"https://example.com/{pid}"}  # noqa: E731
    rows = [{**posting("jk-a"), "source": source_of("jk-a"), "sections": [{"id": "s1", "title": "업무", "text": "SQL 데이터 분석 업무"}]}]

    def source():
        reads.append(1)
        return list(rows)

    search = OpportunitySearch(sessionmaker(engine), source, None, lambda: version[0])
    assert search.search("SQL 분석", "employment")["total"] == 1
    search.search("SQL 분석", "employment")
    assert len(reads) == 1
    rows.append({**posting("jk-b"), "source": source_of("jk-b"), "sections": [{"id": "s1", "title": "업무", "text": "SQL 쿼리 작성"}]})
    version[0] = 2
    assert search.search("SQL", "employment")["total"] == 2 and len(reads) == 2
