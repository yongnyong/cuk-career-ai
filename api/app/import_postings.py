"""Import the collected public career database into the local web database."""
import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .collect import with_history
from .career.posting_skills import attach_preparation_evidence, extract_skill_evidence, has_multiple_roles
from .career.major_conditions import extract_major_conditions
from .career.supplemental import build_supplemental_postings

ROOT = Path(__file__).resolve().parents[2]
KST = timezone(timedelta(hours=9))
PATH_JOBS = {
    '소프트웨어 개발': ['sw-developer'], '인공지능·데이터': ['ai-engineer', 'data-analyst'],
    '수학·통계': ['data-analyst'], '정보보안·인프라': ['ice-security'],
    '전자·반도체': ['electronics'], '제어·설비': ['electronics'],
    '바이오·제약': ['bio-researcher', 'bio-qa'], '화학·소재': ['bio-researcher'],
    '에너지·환경': ['env-engineer'], '경영·기획': ['finance'], '회계·세무': ['finance', 'acc-corp'],
    '금융': ['finance'], '물류·구매': ['overseas-sales'], '국제무역': ['overseas-sales'],
    '영업': ['overseas-sales'], '마케팅': ['marketer'], '미디어·콘텐츠': ['content-planner'],
    '인사·조직': ['psy-org'], '사회조사·연구': ['psy-research'],
    '사회복지': ['welfare'], '심리상담': ['psy-counsel', 'psy-clinical'],
    '특수교육': ['sp-teacher'], '아동·보육': ['educator'],
    '학예·기록': ['his-curator', 'his-archive'], '패션·의류': ['clo-design', 'clo-tech'],
    '공간디자인': ['designer'], '식품·영양': ['food'], '간호': ['clinical'],
    '의학': ['clinical'], '약학': ['pharma'], '법률': ['legal'], '행정': ['public-sector'],
    '음악·공연': ['arts-planner'], '신학·사목': ['npo'],
}

# When a specific occupation is named, do not let an employer name or an industry
# tag override it. General titles still use the collected department classification.
TITLE_ROLES = [
    (r'(?:S/?W|소프트웨어|백엔드|프론트엔드)\s*개발', ('sw-developer', 'cs-dev'), ('cs',)),
    (r'영상\s*(?:제작|촬영|편집|연출)|영상\s*PD', ('mtc-video',), ('media-tech',)),
    (r'데이터\s*(?:분석가|애널리스트)|data\s+analyst', ('data-analyst', 'ds-analyst'), ('data-science',)),
    (r'데이터\s*엔지니어|data\s+engineer', ('ds-engineer',), ('data-science', 'cs')),
    (r'(?:AI|인공지능|머신러닝)\s*(?:연구원|연구직)', ('ai-research',), ('ai',)),
    (r'(?:AI|머신러닝)\s*(?:개발|엔지니어)', ('ai-engineer',), ('ai',)),
    (r'\bmarketing\s+(?:assistant|intern)\b|(?:주니어|브랜드|콘텐츠|퍼포먼스)\s*마케터',
     ('marketer', 'biz-marketing'), ('business', 'media-tech')),
    (r'기장\s*관리\s*업무', ('acc-tax', 'acc-corp'), ('accounting',)),
]


def parse_deadline(date_text, content):
    """Keep announced times. Date-only deadlines use end of that calendar day."""
    match = re.search(r'마감일\s*(20\d{2})[.-](\d{1,2})[.-](\d{1,2})(?:\([^)]*\))?\s*(?:(\d{1,2})시\s*(\d{1,2})분)?', content)
    try:
        if match:
            year, month, day, hour, minute = match.groups()
            return datetime(int(year), int(month), int(day), int(hour or 23),
                            int(minute or 59), tzinfo=KST).isoformat(), 'announced' if hour else 'date_only'
        if date_text:
            parsed = datetime.fromisoformat(date_text)
            return parsed.replace(hour=23, minute=59, tzinfo=KST).isoformat(), 'date_only'
    except ValueError:
        pass
    return '1970-01-01T00:00:00+09:00', 'unknown'


def build_postings(database, catalog):
    db = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    jobs = {job['id']: job for job in catalog['jobs']}
    departments = {d['name']: d['id'] for d in catalog['departments']}
    if '의예과·의학과' in departments:
        departments.update(dict.fromkeys(('의학과', '의예과'), departments['의예과·의학과']))
    known_skills = {skill['id'] for skill in catalog['skills']}
    stamp = datetime.now(KST).isoformat(timespec='seconds')
    rows = []
    try:
        for post in db.execute('SELECT p.*,s.url,s.publisher,s.verified_on FROM postings p JOIN sources s ON s.id=p.source_id ORDER BY p.id'):
            paths = {row[0] for row in db.execute('''SELECT w.name FROM roles r JOIN role_pathways rp ON rp.role_id=r.id
                JOIN pathways w ON w.id=rp.pathway_id WHERE r.posting_id=?''', (post['id'],))}
            reviewed_jobs = {job for path in paths for job in PATH_JOBS.get(path, ()) if job in jobs}
            matches = list(db.execute('''SELECT d.name,m.evidence FROM department_job_matches m
                JOIN departments d ON d.id=m.department_id WHERE m.posting_id=? ORDER BY m.score DESC,d.name''', (post['id'],)))
            department_ids = list(dict.fromkeys(departments[m['name']] for m in matches if m['name'] in departments))
            for match in matches:
                for path in PATH_JOBS:
                    if path + '(' in match['evidence']:
                        paths.add(path)
            linked_jobs = {job for path in paths for job in PATH_JOBS.get(path, ()) if job in jobs}
            for job in list(jobs.values()):
                if job.get('base') in linked_jobs:
                    linked_jobs.add(job['id'])
            evidence = list(db.execute('''SELECT e.* FROM evidence e JOIN roles r ON r.id=e.role_id
                WHERE r.posting_id=? AND e.review_status='reviewed' ORDER BY e.id''', (post['id'],)))
            required = [{'key': 'other', 'label': '최신 모집 여부와 상세 지원자격은 원문 확인', 'src': '§2'}]
            preferred = []
            quotes = []
            for item in evidence:
                quotes.append(item['original_text'][:500])
            role_count = db.execute('SELECT COUNT(DISTINCT name) FROM roles WHERE posting_id=?',
                                    (post['id'],)).fetchone()[0]
            multi_role = role_count > 1 or has_multiple_roles(post['title'], post['content_text'])
            title = post['title'].removeprefix(post['company']).strip()
            named_jobs = set()
            named_departments = set()
            for pattern, role_ids, dept_ids in TITLE_ROLES:
                if re.search(pattern, title, re.I):
                    named_jobs.update(role_id for role_id in role_ids if role_id in jobs)
                    named_departments.update(dept_ids)
            if named_jobs:
                if multi_role:
                    department_ids = list(dict.fromkeys([*department_ids, *sorted(named_departments)]))
                else:
                    department_ids = sorted(named_departments)
            # Some broad department clusters mapped named marketing roles only to overseas sales or design.
            # For a single-role posting the advertised occupation takes precedence.
            if not multi_role and 'marketer' in jobs and re.search(
                    r'\bmarketing\s+(?:assistant|intern)\b|(?:주니어|브랜드|콘텐츠|퍼포먼스)\s*마케터', post['title'], re.I):
                paths = {'마케팅'}
                linked_jobs = {'marketer'} | {j['id'] for j in jobs.values() if j.get('base') == 'marketer'}
            if not multi_role and re.search(r'기장\s*관리\s*업무', post['title']):
                paths = {'회계·세무'}
                linked_jobs = {'acc-tax', 'acc-corp'} & jobs.keys()
            if named_jobs:
                linked_jobs = named_jobs | reviewed_jobs if multi_role else named_jobs
            raw_text = '' if post['completeness'] == 'reviewed_excerpt' else post['content_text']
            major_conditions = extract_major_conditions(raw_text, catalog, multi_role=multi_role)
            skill_evidence = [entry for entry in extract_skill_evidence(raw_text, evidence, multi_role=multi_role)
                              if entry['skill'] in known_skills]
            for index, entry in enumerate(skill_evidence):
                entry['src'] = f'역량{index + 1}'
            for entry in skill_evidence:
                if entry['basis'] == 'preferred' and not entry.get('minimum') and entry['scope'] == 'role':
                    preferred.append(entry['skill'])
            deadline, date_status = parse_deadline(post['deadline_date'], post['content_text'])
            snapshot_date = post['verified_on'] or '원본 수집 기록에서 확인'
            sections = [
                {'id': '§1', 'title': '공고', 'text': post['company'] + ' · ' + post['title']},
                {'id': '§2', 'title': '지원 조건', 'text': '\n'.join(dict.fromkeys(quotes)) or '지원 조건은 원문 링크에서 확인해 주세요.'},
                {'id': '§3', 'title': '직무 연결', 'text': '직무 분류 참고 · ' + (' · '.join(sorted(paths)) or '직무 분류 확인 필요')},
                {'id': '§4', 'title': '지원 방법', 'text': '원문에서 제출서류·접수 방법·모집 부문을 확인해 주세요.'},
                {'id': '§5', 'title': '모집 기한', 'text': deadline if date_status != 'unknown' else '마감일 확인 필요'},
            ]
            sections.extend({'id': entry['src'], 'title': '역량 근거 · ' + (
                '우대' if entry['basis'] == 'preferred' else '요구 역량'),
                'text': entry['quote']} for entry in skill_evidence)
            for index, condition in enumerate(major_conditions):
                condition['src'] = f'전공{index + 1}'
                sections.append({'id': condition['src'], 'title': '전공 조건 원문', 'text': condition['quote']})
                if condition['basis'] == 'required' and not condition['unrestricted']:
                    required.append({'key': 'department', 'label': condition['quote'], 'src': condition['src'],
                                     'departmentIds': condition['departmentIds'], 'majors': condition['fields'],
                                     'related': condition['related'], 'scope': condition['scope']})
            facts = [{'label': '자료 확인일', 'value': snapshot_date},
                     {'label': '학과 연결 참고', 'value': ' · '.join(
                         d['name'] for d in catalog['departments'] if d['id'] in department_ids) or '매칭 정보 없음'}]
            data = {
                'id': 'hist-' + post['id'].split(':')[-1], 'type': '채용',
                'title': post['title'], 'org': post['company'],
                'source': {'name': post['publisher'], 'url': post['url']}, 'applyUrl': post['url'],
                'isVirtual': False, 'jobs': sorted(linked_jobs), 'required': required,
                'employmentMatch': {'namedJobs': sorted(named_jobs), 'reviewedJobs': sorted(reviewed_jobs),
                                    'departmentIds': department_ids, 'majorConditions': major_conditions},
                'preferred': sorted(set(preferred)), 'documents': [], 'sections': sections,
                'conditionsBy': 'rule', 'facts': facts, 'confidence': 1.0, 'reviewed': True,
                'skillEvidence': skill_evidence,
                'deadlineStatus': date_status,
                'versions': [{'version': 1, 'checkedAt': stamp, 'deadline': deadline}],
            }
            # The curated excerpts include editorial summaries, not employer quotations.
            rows.append(attach_preparation_evidence(data, raw_text, evidence, multi_role=multi_role))
    finally:
        db.close()
    existing_urls = {row['source']['url'] for row in rows}
    rows.extend(row for row in build_supplemental_postings(catalog) if row['source']['url'] not in existing_urls)
    return rows


def import_postings(source, target):
    catalog = json.loads((ROOT / 'api/app/career/web_catalog.json').read_text(encoding='utf-8'))
    postings = build_postings(source, catalog)
    with sqlite3.connect(target) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS postings (
            id VARCHAR(40) PRIMARY KEY,raw_hash VARCHAR(64) NOT NULL,
            data JSON,checked_at BIGINT NOT NULL)''')
        # Import only our stable hist-* IDs. A rerun preserves other collectors and accounts.
        count = 0
        for posting in postings:
            payload = {key: value for key, value in posting.items() if key != 'versions'}
            payload['deadline'] = posting['versions'][0]['deadline']
            digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            old = db.execute('SELECT raw_hash,data FROM postings WHERE id=?', (posting['id'],)).fetchone()
            if old and old[0] == digest:
                continue
            data = with_history(json.loads(old[1]) if old and old[1] else None, posting)
            db.execute('''INSERT INTO postings(id,raw_hash,data,checked_at) VALUES(?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET raw_hash=excluded.raw_hash,data=excluded.data,checked_at=excluded.checked_at''',
                (posting['id'], digest, json.dumps(data, ensure_ascii=False), int(datetime.now(timezone.utc).timestamp())))
            count += 1
    return {'total': len(postings), 'written': count,
            'with_deadline': sum(p['deadlineStatus'] != 'unknown' for p in postings),
            'with_jobs': sum(bool(p['jobs']) for p in postings),
            'with_skill_evidence': sum(bool(p.get('skillEvidence')) for p in postings),
            'with_preparation_evidence': sum(bool(p.get('preparationEvidence')) for p in postings),
            'with_discovery_evidence': sum(bool(p.get('discoveryEvidence')) for p in postings)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, default=ROOT / 'api/career.db')
    args = parser.parse_args()
    print(json.dumps(import_postings(args.source, args.target)))
