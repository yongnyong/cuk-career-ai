"""창업 공고를 공고 DB(서버에서는 Postgres)에 올린다. 챗봇·공고 목록·AI 처리 과정이 같은 공고를 쓰게 한다.

수집(app.startup_collect)이 끝난 뒤 실행한다: python -m app.startup_publish
원문 내용이 바뀐 공고만 덮어쓴다. 창업 DB에서 빠진 공고는 공고 DB에서도 지운다.
"""
import json
import time

from sqlalchemy import select

from .career_db import CareerSessionLocal, Posting
from .startup_catalog import catalog
from .startup_db import DEFAULT_DB, connect, digest


def publish(startup_db=DEFAULT_DB, session_factory=CareerSessionLocal) -> dict:
    with connect(startup_db) as db:
        opps = catalog(db)["opportunities"]
    now = int(time.time())
    added = changed = removed = 0
    with session_factory() as s:
        ids = set()
        for o in opps:
            ids.add(o["id"])
            h = digest(json.dumps(o, ensure_ascii=False, sort_keys=True))
            row = s.get(Posting, o["id"])
            if row and row.raw_hash == h:
                continue
            added += row is None
            changed += row is not None
            s.merge(Posting(id=o["id"], raw_hash=h, data=o, checked_at=now))
        for row in s.scalars(select(Posting).where(Posting.id.like("startup-%"))).all():
            if row.id not in ids:
                s.delete(row)
                removed += 1
        s.commit()
    return {"startup": len(opps), "added": added, "changed": changed, "removed": removed}


if __name__ == "__main__":
    print(json.dumps(publish(), ensure_ascii=False))
