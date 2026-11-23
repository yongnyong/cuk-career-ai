"""Build the reviewed public posting supplement using the existing evidence extractors."""
import json
import re
from pathlib import Path

from .major_conditions import extract_major_conditions
from .posting_skills import attach_preparation_evidence, extract_skill_evidence


def build_supplemental_postings(catalog):
    snapshot = json.loads(Path(__file__).with_name('supplemental_postings.json').read_text(encoding='utf-8'))
    known_jobs = {j['id'] for j in catalog['jobs']}
    known_skills = {s['id'] for s in catalog['skills']}
    rows = []
    for entry in snapshot['postings']:
        jobs = entry['jobs']
        if not set(jobs) <= known_jobs:
            raise ValueError(f"Unknown job in supplemental posting {entry['id']}")
        sections = [
            {'id': 'overview', 'title': '공고 검수 요약', 'text': entry['summary']},
            {'id': 'review', 'title': '확인 범위·주의사항', 'text': entry['notes']},
        ]
        required = [{'key': 'other', 'label': entry['notes'], 'src': 'review'}]
        if entry.get('degree'):
            required.append({'key': 'degree', 'degree': entry['degree'], 'label': '학위·졸업예정 조건 확인', 'src': 'overview'})
        majors = extract_major_conditions(entry['text'], catalog)
        for index, major in enumerate(majors):
            major['src'] = f'major-{index}'
            sections.append({'id': major['src'], 'title': '전공 조건 원문', 'text': major['quote']})
            if major['basis'] == 'required' and not major['unrestricted']:
                required.append({'key': 'department', 'label': major['quote'], 'src': major['src'],
                                 'departmentIds': major['departmentIds'], 'majors': major['fields'],
                                 'related': major['related'], 'scope': major['scope']})
        evidence = [e for e in extract_skill_evidence(entry['text']) if e['skill'] in known_skills]
        for index, item in enumerate(evidence):
            item['src'] = f'skill-{index}'
            sections.append({'id': item['src'], 'title': '역량 조건 원문', 'text': item['quote']})
        deadline = entry['deadline'] or '1970-01-01T00:00:00+09:00'
        posting = {
            'id': entry['id'], 'type': '채용', 'title': entry['title'], 'org': entry['org'],
            'source': {'name': entry['publisher'], 'url': entry['url']},
            'applyUrl': entry.get('applyUrl', entry['url']), 'isVirtual': False,
            'jobs': jobs, 'employmentMatch': {'namedJobs': jobs, 'reviewedJobs': [],
                                            'departmentIds': entry['departments'], 'majorConditions': majors},
            'required': required, 'preferred': [], 'documents': entry['documents'], 'sections': sections,
            'skillEvidence': evidence, 'conditionsBy': 'rule', 'reviewed': True, 'confidence': 1.0,
            'deadlineStatus': 'unknown' if not entry['deadline'] else 'date_only' if entry.get('dateOnly') else 'announced',
            'versions': [{'version': 1, 'checkedAt': snapshot['checkedOn'] + 'T12:00:00+09:00', 'deadline': deadline}],
            'facts': [{'label': '자료 확인일', 'value': snapshot['checkedOn']},
                      {'label': '확인 범위', 'value': entry['notes']}],
        }
        if entry.get('opensAt'):
            posting['opensAt'] = entry['opensAt']
        attach_preparation_evidence(posting, entry['text'])
        # A preferred work-sample alternative may support an optional preparation
        # path while the common extractor conservatively skips OR conditions.
        for index, option in enumerate(entry.get('suggestedAlternatives', [])):
            pattern = catalog['postingProjectPatterns'].get(option['key'])
            if (option['basis'] != 'preferred' or not pattern or option['quote'] not in entry['text']
                    or not re.search(pattern, option['quote'], re.I)):
                raise ValueError(f"Unverified preparation alternative in {entry['id']}")
            src = f'alternative-{index}'
            sections.append({'id': src, 'title': '선택 경험 우대 원문', 'text': option['quote']})
            posting['preparationEvidence'].append({**option, 'src': src, 'scope': 'role'})
        rows.append(posting)
    return rows
