import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main
from app.career_db import Posting, CareerSessionLocal, migrate_legacy_postings


def legacy_pair(tmp_path):
    account, career = tmp_path / 'accounts.db', tmp_path / 'career.db'
    schema = 'CREATE TABLE postings(id TEXT PRIMARY KEY,raw_hash TEXT,data TEXT,checked_at INTEGER)'
    with sqlite3.connect(account) as db:
        db.execute('CREATE TABLE users(id TEXT PRIMARY KEY,password_hash TEXT)')
        db.execute('INSERT INTO users VALUES ("private-user","private-hash")')
        db.execute(schema)
        db.execute('INSERT INTO postings VALUES ("hist-one","digest",?,2)', ('{"title":"Public posting"}',))
    with sqlite3.connect(career) as db:
        db.execute(schema)
    return account, career


def test_move_is_idempotent_and_only_public_postings_enter_career_db(tmp_path):
    account, career = legacy_pair(tmp_path)
    assert migrate_legacy_postings(f'sqlite:///{account}', f'sqlite:///{career}') == 1
    assert migrate_legacy_postings(f'sqlite:///{account}', f'sqlite:///{career}') == 0
    with sqlite3.connect(account) as db:
        assert db.execute('SELECT * FROM users').fetchall() == [('private-user', 'private-hash')]
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='postings'").fetchone()
    with sqlite3.connect(career) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [('postings',)]
        assert db.execute('SELECT id FROM postings').fetchall() == [('hist-one',)]


def test_failed_move_rolls_back_before_removing_source_table(tmp_path):
    account, career = legacy_pair(tmp_path)
    with sqlite3.connect(career) as db:
        db.execute("CREATE TRIGGER fail BEFORE INSERT ON postings BEGIN SELECT RAISE(ABORT,'fail'); END")
    with pytest.raises(sqlite3.IntegrityError):
        migrate_legacy_postings(f'sqlite:///{account}', f'sqlite:///{career}')
    with sqlite3.connect(account) as db:
        assert db.execute('SELECT COUNT(*) FROM postings').fetchone()[0] == 1


def test_opportunities_use_public_database_not_account_session():
    data = {'id': 'hist-isolated', 'title': 'Public fixture'}
    with CareerSessionLocal() as db:
        db.add(Posting(id=data['id'], raw_hash='fixture', data=data, checked_at=1))
        db.commit()
    try:
        assert data in TestClient(main.app).get('/api/opportunities').json()
    finally:
        with CareerSessionLocal() as db:
            db.delete(db.get(Posting, data['id']))
            db.commit()
