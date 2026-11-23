"""Storage for public collected postings, independent of account data."""
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, BigInteger, Integer, String, Text, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DEFAULT_CAREER_DB = Path(__file__).resolve().parent.parent / 'career.db'
CAREER_DATABASE_URL = os.environ.get('CAREER_DATABASE_URL') or f'sqlite:///{DEFAULT_CAREER_DB.as_posix()}'
career_engine = create_engine(
    CAREER_DATABASE_URL,
    connect_args={'check_same_thread': False} if CAREER_DATABASE_URL.startswith('sqlite') else {},
)
CareerSessionLocal = sessionmaker(career_engine, expire_on_commit=False)


class CareerBase(DeclarativeBase):
    pass


class Posting(CareerBase):
    """Public posting in the web Opportunity format."""
    __tablename__ = 'postings'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    raw_hash: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    checked_at: Mapped[int] = mapped_column(BigInteger)


class SearchSection(CareerBase):
    __tablename__ = "opportunity_search_sections"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    posting_id: Mapped[str] = mapped_column(String(80), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    version: Mapped[int] = mapped_column(Integer)
    section_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)


CareerBase.metadata.create_all(career_engine)


def migrate_legacy_postings(account_url, career_url=CAREER_DATABASE_URL):
    """Move the former SQLite postings table in one attached-DB transaction."""
    source, target = make_url(account_url), make_url(career_url)
    if source.get_backend_name() != 'sqlite' or target.get_backend_name() != 'sqlite':
        return 0
    if not source.database or source.database == ':memory:' or not target.database or target.database == ':memory:':
        return 0
    source_path, target_path = Path(source.database).resolve(), Path(target.database).resolve()
    if source_path == target_path:
        raise ValueError('계정 DB와 공고 DB는 서로 다른 파일이어야 합니다.')
    if not source_path.exists():
        return 0
    with closing(sqlite3.connect(source_path, timeout=30)) as db, db:
        db.execute('ATTACH DATABASE ? AS career', (str(target_path),))
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='postings'").fetchone():
            return 0
        count = db.execute('SELECT COUNT(*) FROM main.postings').fetchone()[0]
        db.execute('''INSERT INTO career.postings(id,raw_hash,data,checked_at)
            SELECT id,raw_hash,data,checked_at FROM main.postings WHERE 1
            ON CONFLICT(id) DO UPDATE SET raw_hash=excluded.raw_hash,data=excluded.data,checked_at=excluded.checked_at
            WHERE excluded.checked_at > postings.checked_at''')
        missing = db.execute('''SELECT COUNT(*) FROM main.postings p
            LEFT JOIN career.postings c ON c.id=p.id WHERE c.id IS NULL OR c.checked_at<p.checked_at''').fetchone()[0]
        if missing:
            raise RuntimeError('공고 이동 검증에 실패했습니다.')
        db.execute('DROP TABLE main.postings')
        return count
