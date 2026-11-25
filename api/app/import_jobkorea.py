"""Sync resumable public JobKorea JSON into the application's career database."""
import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from .collect import scrub
from .import_postings import ROOT, KST, TITLE_ROLES, write_postings
from .career.major_conditions import extract_major_conditions
from .career.posting_skills import attach_preparation_evidence, extract_skill_evidence, has_multiple_roles

DETAIL_LABELS = {
    'pending': '상세 요건 수집 중', 'legacy_unverified': '상세 요건 재확인 중',
    'requirements_found': '텍스트 요건 확보', 'image_review_needed': '이미지 요강 확인 필요',
    'table_review_needed': '표의 모집 부문별 요건 확인 필요',
    'requirements_not_found': '상세 요건 미확보', 'fetch_error': '상세 페이지 재확인 필요',
}


def is_entry(post):
    label = re.sub(r'\s+', '', post.get('career_label', ''))
    return label == '경력무관' or bool(re.match(r'^신입(?:$|[·/,+])', label))


def deadline_of(post):
    observed = datetime.fromisoformat(post['last_seen_at']).astimezone(KST)
    text = post.get('list_text', '')
    match = re.search(r'~\s*(\d{1,2})/(\d{1,2})', text)
    try:
        if match:
            month, day = map(int, match.groups())
            year = observed.year + int(observed.month >= 10 and month <= 3)
            value = datetime(year, month, day, 23, 59, tzinfo=KST)
        elif '오늘마감' in text.replace(' ', ''):
            value = observed.replace(hour=23, minute=59, second=0, microsecond=0)
        else:
            days = re.search(r'\bD\s*-\s*(\d+)\b', text)
            if not days:
                return '1970-01-01T00:00:00+09:00', 'unknown'
            value = (observed + timedelta(days=int(days[1]))).replace(hour=23, minute=59, second=0, microsecond=0)
        return value.isoformat(), 'date_only'
    except ValueError:
        return '1970-01-01T00:00:00+09:00', 'unknown'


def build_posting(post, catalog, previous=None):
    url = post['original_url']
    if not re.fullmatch(r'https://www\.jobkorea\.co\.kr/Recruit/GI_Read/\d+', url):
        raise ValueError('Unexpected JobKorea public posting URL')
    pid = previous['id'] if previous else 'hist-' + hashlib.sha256(
        json.dumps([url], ensure_ascii=False).encode()).hexdigest()[:20]
    state = post.get('detail_status', 'legacy_unverified' if post.get('detail_text') else 'pending')
    label = DETAIL_LABELS.get(state, '상세 요건 확인 필요')
    sections = [
        {'id': 'jk-title', 'title': '공고', 'text': scrub(post['company'] + ' · ' + post['title'])},
        {'id': 'jk-list', 'title': '목록 분류 참고', 'text': scrub(' · '.join(post.get('list_tags', [])))},
        {'id': 'jk-review', 'title': '확인 범위·주의사항', 'text': label + ' · 학력·졸업 시점·모집 부문별 지원 조건은 원문에서 확인하세요.'},
    ]
    raw = ''
    if state == 'requirements_found':
        blocks = [block for block in post.get('requirement_blocks', []) if block.get('kind') in ('required', 'preferred')]
        for index, block in enumerate(blocks):
            # Normalize the section name while retaining each original condition verbatim.
            heading = '우대사항' if block['kind'] == 'preferred' else '자격요건'
            text = re.split(
                r'이런\s*기술이\s*필요해요|이런\s*조건에서\s*근무할\s*예정이에요|함께하면\s*이런\s*점들이\s*좋아요|합류\s*여정은\s*이렇게\s*진행돼요|지원\s*시\s*유의해주세요|복지\s*사항|복리\s*후생',
                scrub(block['text']), maxsplit=1)[0].strip()
            sections.append({'id': f'jk-requirement-{index}', 'title': heading, 'text': heading + '\n' + text})
        raw = '\n'.join(section['text'] for section in sections[3:])
    multi = state == 'table_review_needed' or has_multiple_roles(post['title'], raw)
    known_jobs = {job['id'] for job in catalog['jobs']}
    known_skills = {skill['id'] for skill in catalog['skills']}
    named = {job for pattern, job_ids, _ in TITLE_ROLES if re.search(pattern, post['title'], re.I)
             for job in job_ids if job in known_jobs}
    old_match = previous.get('employmentMatch', {}) if previous and previous['title'] == post['title'] else {}
    jobs = sorted(named)
    if not named and old_match:
        jobs = previous.get('jobs', [])
    match = {'namedJobs': sorted(named or old_match.get('namedJobs', [])),
             'reviewedJobs': old_match.get('reviewedJobs', []),
             'departmentIds': old_match.get('departmentIds', []), 'majorConditions': []}
    required = [{'key': 'other', 'label': sections[2]['text'], 'src': 'jk-review'}]
    for index, condition in enumerate(extract_major_conditions(raw, catalog, multi_role=multi)):
        condition['src'] = f'jk-major-{index}'
        sections.append({'id': condition['src'], 'title': '전공 조건 원문', 'text': condition['quote']})
        match['majorConditions'].append(condition)
        if condition['basis'] == 'required' and not condition['unrestricted']:
            required.append({'key': 'department', 'label': condition['quote'], 'src': condition['src'],
                             'departmentIds': condition['departmentIds'], 'majors': condition['fields'],
                             'related': condition['related'], 'scope': condition['scope']})
    skills = [row for row in extract_skill_evidence(raw, multi_role=multi) if row['skill'] in known_skills]
    for index, row in enumerate(skills):
        row['src'] = f'jk-skill-{index}'
        sections.append({'id': row['src'], 'title': '역량 조건 원문', 'text': row['quote']})
    deadline, deadline_status = deadline_of(post)
    posting = {
        'id': pid, 'type': '채용', 'title': scrub(post['title']), 'org': scrub(post['company']),
        'source': {'name': '잡코리아', 'url': url}, 'applyUrl': url, 'isVirtual': False,
        'jobs': jobs, 'employmentMatch': match, 'required': required,
        'preferred': sorted({row['skill'] for row in skills if row['basis'] == 'preferred' and row['scope'] == 'role'}),
        'documents': [], 'sections': sections, 'skillEvidence': skills,
        'conditionsBy': 'rule', 'confidence': 0.9 if raw else 0.5, 'reviewed': bool(raw),
        'deadlineStatus': deadline_status,
        'facts': [{'label': '모집 경력', 'value': post['career_label']}, {'label': '상세 확보 상태', 'value': label}],
        'versions': [{'version': 1, 'checkedAt': post.get('detail_checked_at') or post['last_seen_at'], 'deadline': deadline}],
    }
    return attach_preparation_evidence(posting, raw, multi_role=multi)


def sync(source, target, dry_run=False):
    snapshot = json.loads(source.read_text(encoding='utf-8'))
    current_ids = set(snapshot.get('run', {}).get('seen_ids', []))
    existing = {}
    if target.exists():
        with sqlite3.connect(target.resolve().as_uri() + '?mode=ro', uri=True) as db:
            for (value,) in db.execute('SELECT data FROM postings WHERE data IS NOT NULL'):
                data = json.loads(value)
                existing[data.get('applyUrl', '')] = data
    catalog = json.loads((ROOT / 'api/app/career/web_catalog.json').read_text(encoding='utf-8'))
    candidates = [post for post in snapshot['posts'] if is_entry(post)
                  and (not current_ids or post['job_id'] in current_ids)
                  and post.get('status') != 'closed']
    postings = [build_posting(post, catalog, existing.get(post['original_url'])) for post in candidates]
    result = {'total': len(postings), 'detail_states': dict(Counter(
        post.get('detail_status', 'pending') for post in candidates)), 'dry_run': dry_run}
    if not dry_run:
        retired_ids = [existing[post['original_url']]['id'] for post in snapshot['posts']
                       if post.get('status') == 'closed' and post['original_url'] in existing]
        result.update(write_postings(postings, target, retired_ids))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--target', type=Path, default=ROOT / 'api/career.db')
    parser.add_argument('--dry-run', action='store_true')
    arguments = parser.parse_args()
    print(json.dumps(sync(arguments.input, arguments.target, arguments.dry_run), ensure_ascii=False))
