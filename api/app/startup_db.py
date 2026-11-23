"""Public startup notices and traceable submission requirements, in a separate SQLite DB."""
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


# 서버에서는 STARTUP_DB_PATH로 영구 볼륨 안의 파일을 쓴다(컨테이너를 다시 만들어도 남는다)
DEFAULT_DB = Path(os.environ.get("STARTUP_DB_PATH") or Path(__file__).resolve().parent.parent / "startup.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    source_site TEXT NOT NULL,
    category TEXT NOT NULL,
    published_date TEXT,
    application_period TEXT,
    application_start TEXT,
    application_end TEXT,
    application_end_precision TEXT,
    application_status TEXT NOT NULL,
    eligibility_text TEXT NOT NULL,
    support_text TEXT NOT NULL,
    review_notes TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    extractor_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    posting_id TEXT NOT NULL REFERENCES postings(id),
    url TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    current INTEGER NOT NULL DEFAULT 1 CHECK(current IN (0, 1))
);
CREATE TABLE IF NOT EXISTS attachments (
    posting_id TEXT NOT NULL REFERENCES postings(id),
    url TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    extraction_status TEXT NOT NULL,
    PRIMARY KEY (posting_id, url)
);
CREATE TABLE IF NOT EXISTS submission_requirements (
    id TEXT PRIMARY KEY,
    posting_id TEXT NOT NULL REFERENCES postings(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    document_type TEXT NOT NULL,
    original_name TEXT NOT NULL,
    necessity TEXT NOT NULL CHECK(necessity IN ('required', 'optional', 'conditional', 'needs_review')),
    stage TEXT NOT NULL CHECK(stage IN ('application', 'finalist', 'agreement', 'unknown')),
    condition_text TEXT NOT NULL,
    deadline_text TEXT,
    deadline_date TEXT,
    deadline_precision TEXT,
    evidence_quote TEXT NOT NULL,
    evidence_line INTEGER NOT NULL,
    template_url TEXT,
    extraction_method TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'unreviewed'
);
CREATE INDEX IF NOT EXISTS startup_requirements_posting ON submission_requirements(posting_id);
CREATE INDEX IF NOT EXISTS startup_requirements_type ON submission_requirements(document_type, necessity);
CREATE INDEX IF NOT EXISTS startup_sources_posting ON sources(posting_id, current);
CREATE TABLE IF NOT EXISTS startup_nodes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('artifact','application','certificate','preparation')),
    completion TEXT NOT NULL,
    related_skill_id TEXT,
    extractor_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS startup_node_evidence (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES startup_nodes(id) ON DELETE CASCADE,
    posting_id TEXT NOT NULL REFERENCES postings(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    requirement_id TEXT REFERENCES submission_requirements(id) ON DELETE CASCADE,
    basis TEXT NOT NULL CHECK(basis IN ('submission','form_section','evaluation')),
    necessity TEXT NOT NULL CHECK(necessity IN ('required','optional','conditional','needs_review','unspecified')),
    stage TEXT NOT NULL,
    condition_text TEXT NOT NULL,
    deadline_date TEXT,
    quote TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    source_page INTEGER,
    review_status TEXT NOT NULL DEFAULT 'unreviewed'
);
CREATE TABLE IF NOT EXISTS startup_node_edges (
    parent_id TEXT NOT NULL REFERENCES startup_nodes(id) ON DELETE CASCADE,
    child_id TEXT NOT NULL REFERENCES startup_nodes(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES startup_node_evidence(id) ON DELETE CASCADE,
    relation TEXT NOT NULL CHECK(relation IN ('form_section','evaluation_preparation')),
    PRIMARY KEY(parent_id, child_id, evidence_id)
);
CREATE INDEX IF NOT EXISTS startup_node_evidence_posting ON startup_node_evidence(posting_id, node_id);
"""


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@contextmanager
def connect(path=DEFAULT_DB):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        db.close()


def initialize(path=DEFAULT_DB):
    with connect(path) as db:
        db.executescript(SCHEMA)


def save_posting(db, posting, sources, attachments, requirements):
    """One transaction per notice. A failed refresh retains the previous complete notice."""
    with db:
        columns = list(posting)
        updates = ", ".join(f"{key}=excluded.{key}" for key in columns if key != "id")
        db.execute(
            f"INSERT INTO postings ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}", list(posting.values()),
        )
        db.execute("UPDATE sources SET current=0 WHERE posting_id=?", (posting["id"],))
        for source in sources:
            db.execute(
                "INSERT INTO sources(id,posting_id,url,kind,content,content_hash,fetched_at,current) "
                "VALUES(:id,:posting_id,:url,:kind,:content,:content_hash,:fetched_at,1) "
                "ON CONFLICT(id) DO UPDATE SET current=1, fetched_at=excluded.fetched_at", source,
            )
        db.execute("DELETE FROM attachments WHERE posting_id=?", (posting["id"],))
        db.executemany(
            "INSERT INTO attachments(posting_id,url,name,role,extraction_status) "
            "VALUES(:posting_id,:url,:name,:role,:extraction_status)", attachments,
        )
        db.execute("DELETE FROM submission_requirements WHERE posting_id=?", (posting["id"],))
        for requirement in requirements:
            keys = list(requirement)
            db.execute(
                f"INSERT INTO submission_requirements({', '.join(keys)}) "
                f"VALUES({', '.join('?' for _ in keys)})", list(requirement.values()),
            )


def summary(db):
    def grouped(table, column):
        return dict(db.execute(f"SELECT {column}, COUNT(*) FROM {table} GROUP BY {column}").fetchall())
    return {
        "postings": db.execute("SELECT COUNT(*) FROM postings").fetchone()[0],
        "startup_nodes": db.execute("SELECT COUNT(*) FROM startup_nodes").fetchone()[0],
        "startup_node_evidence": db.execute("SELECT COUNT(*) FROM startup_node_evidence").fetchone()[0],
        "sources": db.execute("SELECT COUNT(*) FROM sources WHERE current=1").fetchone()[0],
        "requirements": db.execute("SELECT COUNT(*) FROM submission_requirements").fetchone()[0],
        "unique_requirement_groups": db.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT posting_id,document_type,necessity,stage FROM submission_requirements)"
        ).fetchone()[0],
        "postings_with_submission_evidence": db.execute(
            "SELECT COUNT(DISTINCT posting_id) FROM submission_requirements WHERE necessity!='needs_review'"
        ).fetchone()[0],
        "categories": grouped("postings", "category"),
        "application_status": grouped("postings", "application_status"),
        "necessity": grouped("submission_requirements", "necessity"),
        "attachment_status": grouped("attachments", "extraction_status"),
    }


def export_json(db, path):
    """Optional portable snapshot. Account data never participates in this export."""
    tables = ("postings", "sources", "attachments", "submission_requirements",
              "startup_nodes", "startup_node_evidence", "startup_node_edges")
    data = {table: [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY 1, 2")] for table in tables}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
