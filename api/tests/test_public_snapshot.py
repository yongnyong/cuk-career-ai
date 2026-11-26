import json
import sqlite3

import pytest

from app.public_snapshot import CAREER_SCHEMA, export, restore
from app.startup_db import initialize


def fixture(tmp_path):
    career, startup = tmp_path / 'career.db', tmp_path / 'startup.db'
    with sqlite3.connect(career) as db:
        db.execute(CAREER_SCHEMA)
        for pid, virtual in [('hist-1', False), ('man-1', False), ('demo-1', True)]:
            db.execute('INSERT INTO postings VALUES(?,?,?,?)', (pid, 'hash', json.dumps({'id': pid, 'isVirtual': virtual}), 123))
        db.execute('CREATE TABLE accounts(secret TEXT)')
        db.execute("INSERT INTO accounts VALUES('private-account-record')")
        db.execute('CREATE TABLE opportunity_search_sections(embedding TEXT)')
        db.execute("INSERT INTO opportunity_search_sections VALUES('private-cache-marker')")
    initialize(startup)
    folder = tmp_path / 'public'
    export(career, startup, folder)
    return folder


def test_exports_only_public_tables_and_roundtrips(tmp_path):
    folder = fixture(tmp_path)
    content = (folder / 'career.jsonl').read_text(encoding='utf-8')
    assert 'private-account-record' not in content and 'private-cache-marker' not in content
    assert 'man-1' not in content and 'demo-1' not in content
    career, startup = tmp_path / 'restored-career.db', tmp_path / 'restored-startup.db'
    restore(folder, career, startup)
    with sqlite3.connect(career) as db:
        assert db.execute('select id from postings').fetchall() == [('hist-1',)]
        assert db.execute("select name from sqlite_master where type='table'").fetchall() == [('postings',)]
    export(career, startup, tmp_path / 'again')
    for name in ('manifest.json', 'career.jsonl', 'startup.jsonl'):
        assert (folder / name).read_bytes() == (tmp_path / 'again' / name).read_bytes()


def test_checksum_failure_writes_no_targets(tmp_path):
    folder = fixture(tmp_path)
    with (folder / 'startup.jsonl').open('a') as out:
        out.write('{}\n')
    career, startup = tmp_path / 'new-career.db', tmp_path / 'new-startup.db'
    with pytest.raises(ValueError, match='checksum'):
        restore(folder, career, startup)
    assert not career.exists() and not startup.exists()


def test_existing_or_account_targets_are_preserved(tmp_path):
    folder = fixture(tmp_path)
    career, startup = tmp_path / 'existing.db', tmp_path / 'new.db'
    career.write_text('existing-data')
    with pytest.raises(ValueError, match='already exists'):
        restore(folder, career, startup)
    assert career.read_text() == 'existing-data' and not startup.exists()
    with pytest.raises(ValueError, match='never dev.db'):
        restore(folder, tmp_path / 'dev.db', startup)
