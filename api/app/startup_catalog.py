"""Public web contract for the startup catalog and its source-backed nodes."""
import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .startup_db import DEFAULT_DB, connect
from .startup_nodes import load_graph


def catalog(db):
    graph = load_graph(db)
    opportunities = []
    for row in db.execute("SELECT * FROM postings ORDER BY id"):
        source = db.execute("SELECT content FROM sources WHERE posting_id=? AND kind='html' AND current=1", (row["id"],)).fetchone()
        text = source[0] if source else row["eligibility_text"]
        requirements = [dict(r) for r in db.execute(
            "SELECT r.*, s.url AS evidence_url FROM submission_requirements r JOIN sources s ON s.id=r.source_id "
            "WHERE r.posting_id=? AND s.current=1 ORDER BY r.document_type,r.id", (row["id"],))]
        sections = [{"id": "startup-body", "title": "공고 본문", "text": text}]
        sections.extend({"id": r["id"], "title": r["document_type"], "text": r["evidence_quote"]} for r in requirements)
        opportunities.append({
            "id": "startup-" + row["id"], "type": "창업지원", "title": row["title"], "org": row["source_site"],
            "source": {"name": row["source_site"], "url": row["source_url"]}, "isVirtual": False,
            "jobs": ["founder"], "required": [{"key": "other", "label": "소속·지역·창업 단계 등 원문 지원 자격 확인", "src": "startup-body"}],
            "preferred": [], "documents": sorted({r["document_type"] for r in requirements if r["necessity"] == "required" and r["stage"] == "application"}),
            "applyUrl": row["source_url"], "sections": sections,
            "versions": [{"version": 1, "checkedAt": row["fetched_at"], "deadline": row["application_end"] or ""}],
            "confidence": 1, "reviewed": False, "deadlineStatus": "date_only" if row["application_end"] else "unknown",
            "facts": [{"label": "지원 유형", "value": row["category"]}],
            "startup": {"postingId": row["id"], "category": row["category"], "status": row["application_status"],
                        "eligibility": row["eligibility_text"], "support": row["support_text"],
                        "reviewNotes": json.loads(row["review_notes"]), "requirements": requirements},
        })
    return {**graph, "opportunities": opportunities}


router = APIRouter()


@router.get("/api/startup/catalog")
def startup_catalog():
    if not Path(DEFAULT_DB).is_file():
        raise HTTPException(503, "창업 공고 자료를 준비 중이에요.")
    try:
        with connect(DEFAULT_DB) as db:
            return catalog(db)
    except sqlite3.DatabaseError:
        raise HTTPException(503, "창업 공고 자료를 준비 중이에요.") from None
