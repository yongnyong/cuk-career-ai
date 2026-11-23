from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import startup_publish
from app.career_db import CareerBase, Posting
from app.startup_db import initialize


def test_publish_adds_updates_and_removes_startup_rows_only(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'career.db').as_posix()}")
    CareerBase.metadata.create_all(engine)
    Session = sessionmaker(engine)
    with Session() as s:
        s.add(Posting(id="kst-1", raw_hash="x", data={"id": "kst-1"}, checked_at=1))
        s.add(Posting(id="startup-old", raw_hash="x", data={"id": "startup-old"}, checked_at=1))
        s.commit()
    initialize(tmp_path / "startup.db")
    opps = [{"id": "startup-cuk-1", "title": "A"}]
    monkeypatch.setattr(startup_publish, "catalog", lambda db: {"opportunities": opps})
    run = lambda: startup_publish.publish(tmp_path / "startup.db", Session)
    assert run() == {"startup": 1, "added": 1, "changed": 0, "removed": 1}
    assert run() == {"startup": 1, "added": 0, "changed": 0, "removed": 0}
    opps[0]["title"] = "B"
    assert run()["changed"] == 1
    with Session() as s:
        assert {r.id for r in s.query(Posting)} == {"kst-1", "startup-cuk-1"}
        assert s.get(Posting, "startup-cuk-1").data["title"] == "B"
