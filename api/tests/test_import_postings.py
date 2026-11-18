import json
import sqlite3

from app import import_postings


def test_deadline_uses_announced_time_and_keeps_unknown_explicit():
    assert import_postings.parse_deadline('', '마감일 2026.11.30(월) 11시 00분') == (
        '2026-11-30T11:00:00+09:00', 'announced')
    assert import_postings.parse_deadline('2026-11-30', '') == (
        '2026-11-30T23:59:00+09:00', 'date_only')
    assert import_postings.parse_deadline('', '')[1] == 'unknown'
    assert import_postings.parse_deadline('2026-02-30', '')[1] == 'unknown'


def test_import_rerun_preserves_accounts_and_version_history(tmp_path, monkeypatch):
    target = tmp_path / 'web.db'
    with sqlite3.connect(target) as db:
        db.execute('CREATE TABLE users(id TEXT PRIMARY KEY)')
        db.execute('INSERT INTO users VALUES ("existing-user")')
        db.execute('CREATE TABLE postings(id TEXT PRIMARY KEY,raw_hash TEXT,data TEXT,checked_at INTEGER)')
        db.execute('INSERT INTO postings VALUES ("cuk-existing","keep","{}",1)')
    sample = {'id': 'hist-sample', 'title': '공고', 'jobs': [], 'deadlineStatus': 'date_only',
              'versions': [{'version': 1, 'checkedAt': '2026-11-18', 'deadline': '2026-11-30'}]}
    monkeypatch.setattr(import_postings, 'build_postings', lambda *_: [sample])
    assert import_postings.import_postings(tmp_path, target)['written'] == 1
    assert import_postings.import_postings(tmp_path, target)['written'] == 0
    sample['versions'][0]['deadline'] = '2026-12-01'
    assert import_postings.import_postings(tmp_path, target)['written'] == 1
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT id FROM users').fetchall() == [('existing-user',)]
        assert db.execute('SELECT raw_hash FROM postings WHERE id="cuk-existing"').fetchone() == ('keep',)
        posting = json.loads(db.execute('SELECT data FROM postings WHERE id="hist-sample"').fetchone()[0])
    assert len(posting['versions']) == 2
    assert posting['versions'][-1]['version'] == 2
