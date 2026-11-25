import json
import sqlite3

from app.import_jobkorea import deadline_of, is_entry, sync


def test_entry_labels_and_calendar_rollover():
    for label in ('신입', '경력무관', '신입·경력3년↑'):
        assert is_entry({'career_label': label})
    assert not is_entry({'career_label': '경력3년↑'})
    assert not is_entry({'career_label': ''})
    assert deadline_of({'last_seen_at': '2026-11-25T11:00:00+00:00', 'list_text': '~01/05 (화)'})[0].startswith('2027-01-05')
    assert deadline_of({'last_seen_at': '2026-11-25T11:00:00+00:00', 'list_text': '상시채용'})[1] == 'unknown'


def test_sync_keeps_ids_and_versions_and_imports_pending_without_invented_requirements(tmp_path):
    source, target = tmp_path / 'posts.json', tmp_path / 'career.db'
    with sqlite3.connect(target) as db:
        db.execute('CREATE TABLE postings(id TEXT PRIMARY KEY,raw_hash TEXT,data TEXT,checked_at INTEGER)')
        db.execute('CREATE TABLE users(id TEXT)')
        db.execute('INSERT INTO users VALUES ("keep")')
    def record(i, label='신입', state='pending'):
        return dict(job_id=str(i), title='AI 연구원 신입 채용', company='예시 회사',
                    original_url=f'https://www.jobkorea.co.kr/Recruit/GI_Read/{i}',
                    career_label=label, list_tags=[label, '학력무관'], list_text='~12/15 (화)',
                    last_seen_at='2026-11-25T11:00:00+00:00', detail_status=state)
    records = [record(1), record(2, '경력무관', 'requirements_found'), record(3, '경력5년↑')]
    records[1]['requirement_blocks'] = [dict(kind='preferred', heading='우대사항', text='SQLD 자격증 보유자')]
    def write():
        source.write_text(json.dumps({'run': {'seen_ids': ['1','2','3']}, 'posts': records}), encoding='utf-8')
    write()
    assert sync(source, target)['written'] == 2
    assert sync(source, target)['written'] == 0
    def load():
        with sqlite3.connect(target) as db:
            return [json.loads(r[0]) for r in db.execute('SELECT data FROM postings WHERE data IS NOT NULL')]
    rows = load()
    pending = next(row for row in rows if row['applyUrl'].endswith('/1'))
    assert not pending['reviewed'] and not pending['skillEvidence']
    assert not any('SQLD' in section['text'] for section in pending['sections'])
    saved_id = pending['id']
    records[0].update(detail_status='requirements_found', requirement_blocks=[
        dict(kind='required', heading='자격요건', text='Python으로 모델을 개발한 경험')])
    write()
    assert sync(source, target)['written'] == 1
    changed = next(row for row in load() if row['id'] == saved_id)
    assert len(changed['versions']) == 2 and changed['versions'][-1]['version'] == 2
    records[0]['status'] = 'closed'
    write()
    sync(source, target)
    assert all(row['id'] != saved_id for row in load())
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT id FROM users').fetchall() == [('keep',)]
