"""Grounded preparation reports, course context and repeatable progress reviews.

Design references are recorded in data/career_reference_integration.md.
External agents are not installed or executed by this module.
"""
import argparse
import hashlib
import json
import re
import sqlite3
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from .evidence import DEFAULT_CATALOG, load_catalog
from .recommender import parse_time, recommend

REPORT_VERSION = 1
REFERENCES = [
    {'name': 'Career-Ops',
     'url': 'https://github.com/career-ops-hq/career-ops/blob/main/DATA_CONTRACT.md',
     'adaptation': '공개 근거·학생 원본·파생 보고서 분리'},
    {'name': 'Career-Ops source of truth',
     'url': 'https://github.com/career-ops-hq/career-ops/blob/main/AGENTS.md',
     'adaptation': '확인되지 않은 학생 역량을 사실로 승격하지 않음'},
    {'name': 'ai-job-search upskill',
     'url': 'https://github.com/ai-job-search-dev/ai-job-search/blob/master/.claude/skills/upskill/SKILL.md',
     'adaptation': '공고별 격차 집계 → 실행 순서 → 이전 보고서와 비교'},
    {'name': 'ai-job-search expand',
     'url': 'https://github.com/ai-job-search-dev/ai-job-search/blob/master/.claude/commands/expand.md',
     'adaptation': '수강과목의 학교 출처를 연결하고 역량 확인 과제를 분리'},
]


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _requirement(group):
    """Exclude the student's observed values when fingerprinting a requirement."""
    return {**{key: group[key] for key in ('role_id', 'category', 'logic', 'status', 'human_alternative')},
            'options': sorted([
                {key: option.get(key) for key in
                 ('credential', 'comparator', 'numeric_value', 'text_value')}
                for option in group['options']], key=lambda option: json.dumps(option, sort_keys=True))}


def gap_matrix(assessments, today):
    """Count observed groups; retain OR logic and employer-specific thresholds."""
    rows = {}
    for group in assessments:
        alternatives = sorted({option['credential'] for option in group['options']})
        key = (group['category'], group['logic'], tuple(alternatives))
        row = rows.setdefault(key, {'category': group['category'], 'logic': group['logic'],
            'alternatives': alternatives, 'states': {state: 0 for state in
                ('gap', 'unknown', 'matched', 'needs_review')}, 'conditions': []})
        row['states'][group['state']] += 1
        deadline = group['role_deadline_date'] or group['posting_deadline_date']
        row['conditions'].append({
            'condition_id': group['id'], 'role_id': group['role_id'],
            'company': group['company'], 'role': group['role'], 'state': group['state'],
            'status': group['status'], 'targets': _requirement(group)['options'],
            'source_url': group['source_url'], 'source_kind': group['source_kind'],
            'verified_on': group['verified_on'], 'original_text': group['original_text'],
            'text_type': group['text_type'], 'human_alternative': group['human_alternative'],
            'historical_reference': bool(deadline and deadline < today),
            'deadline_date': deadline})
    for row in rows.values():
        row['condition_count'] = len(row['conditions'])
        row['employer_count'] = len({c['company'] for c in row['conditions']})
        row['role_count'] = len({c['role_id'] for c in row['conditions']})
        row['required_count'] = sum(c['status'] == 'required' for c in row['conditions'])
        row['preferred_count'] = sum(c['status'] == 'preferred' for c in row['conditions'])
        row['historical_count'] = sum(c['historical_reference'] for c in row['conditions'])
    return sorted(rows.values(), key=lambda row: (
        -row['states']['gap'], -row['states']['unknown'], -row['employer_count'], row['alternatives']))


def _roadmaps(catalog_path, signature):
    return load_catalog(catalog_path, signature)["roadmaps"]


def course_context(profile, catalog_path):
    """Exact delimited course names only; curriculum mention is not a skill claim."""
    path = Path(catalog_path).resolve()
    stat = path.stat()
    rows = _roadmaps(str(path), (stat.st_ino, stat.st_size, stat.st_mtime_ns))
    departments = {profile['department'], *profile.get('secondary_departments', [])}
    rows = [row for row in rows if row['department'] in departments]
    linked, unresolved = [], []
    for course in dict.fromkeys(profile.get('courses', [])):
        normalized = ''.join(course.split()).casefold()
        matches = []
        for row in rows:
            # Do not substring-match e.g. 경제학 against 경제학원론, or infer skills
            # from vague entries such as '전공심화 추천'. Parenthetical labels only.
            tokens = [re.sub(r'\([^)]*\)', '', token).strip()
                      for token in re.split(r'[,/;\n]', row['courses_raw'])]
            if normalized and normalized in {''.join(token.split()).casefold() for token in tokens}:
                matches.append({'roadmap_id': row['id'], 'direction': row['direction'],
                                'source_url': row['source_url'], 'source_text': row['courses_raw']})
        if matches:
            linked.append({'course': course, 'status': 'curriculum_linked', 'matches': matches,
                'next_step': '강의계획서의 학습성과와 본인 과제·프로젝트를 확인해 역량 근거를 보완하세요.'})
        else:
            unresolved.append({'course': course, 'status': 'unmapped',
                               'reason': '현재 DB의 구조화된 학과 진로표에서 과목명을 정확히 연결하지 못함'})
    return {'linked': linked, 'unmapped': unresolved,
            'scope': '입력 수강과목과 학교 진로표의 연결. 이수 진위·숙련도·자격 보유 판정에 사용하지 않음.'}


def action_plan(candidates, now):
    """Short checkpoints, not invented learning times or score improvement promises."""
    plans = []
    for candidate in candidates:
        evidence = candidate['evidence']
        related = evidence.get('related_conditions', [])
        sources = sorted({item['source_url'] for item in related} or {evidence['source_url']})
        steps = []

        def step(offset, action, deliverable):
            steps.append({'checkpoint_on': (now.date() + timedelta(days=offset)).isoformat(),
                          'action': action, 'deliverable': deliverable})

        kind = candidate['type']
        if kind in ('check_activity', 'consider_activity'):
            deadline = evidence.get('deadline')
            offset = 0 if not deadline else min(2, max(0, (parse_time(deadline).date() - now.date()).days))
            step(offset, '원문에서 모집 상태·대상·마감과 참여 조건을 확인하세요.',
                 '참여 가능 여부, 신청 기한, 필요한 팀·선수요건 확인 기록')
            step(offset, '조건이 맞으면 신청 여부를 결정하고 준비할 경험 결과물을 정하세요.',
                 evidence.get('outcome') or '활동 목표와 결과물 계획')
            completion = '신청 확인 또는 실제 참여 결과. 신청만으로 활동 완료로 처리하지 않음.'
        elif kind == 'confirm_record':
            step(2, '보유 이력·유효기간과 기업의 대체 인정 조건을 먼저 확인하세요.',
                 '시험명·점수/등급·취득일·유효기간 또는 대체 경로 확인 결과')
            step(7, '확인한 원본 이력으로 다시 평가해 추가 준비 여부를 결정하세요.',
                 '갱신한 credentials와 재평가 보고서')
            completion = '이력 입력 후 조건별 재평가. 미확인 상태는 준비 부족으로 단정하지 않음.'
        else:
            if any(item['logic'] == 'review' for item in related):
                step(2, '복합 조건의 원문 해석을 먼저 확인하세요.', '비교 가능한 인정 기준 확인')
            step(3, '회사별 기준과 OR/AND 관계를 확인하고 준비할 경로를 정하세요.',
                 '선택한 시험·자격 경로와 해당 공고 조건 ID')
            step(7, '현재 수준과 사용 가능한 학습 시간을 점검해 학습·응시 일정을 정하세요.',
                 '진단 결과, 주간 일정, 공식 시험 일정 확인')
            step(14, '학습 진행을 재점검하고 새 성적·취득 기록이 있으면 프로필을 갱신하세요.',
                 '학습 기록 또는 실제 성적·자격 취득 기록과 재평가 보고서')
            completion = '실제 성적·취득 기록을 비교해야 조건 상태가 바뀜. 계획 완료만으로 보유 처리하지 않음.'
        plans.append({'action_key': candidate['action_key'], 'candidate_id': candidate['id'],
            'type': kind, 'title': candidate['title'], 'reason': candidate['reason'],
            'source_urls': sources, 'conditions': related,
            'checks': evidence.get('checks', []), 'deadline': evidence.get('deadline'),
            'historical_reference': any(item['historical_reference'] for item in related),
            'steps': steps, 'completion_rule': completion})
    return plans


def compare_reports(previous, current):
    if previous is None:
        return {'status': 'first_report', 'transitions': [], 'newly_matched': [],
                'no_longer_observed': [], 'evidence_changed': [], 'new_conditions': []}
    if not isinstance(previous, dict) or previous.get('report_version') != REPORT_VERSION:
        raise ValueError('이전 보고서 형식·버전을 확인하세요.')
    if previous.get('subject_key_hash') != current['subject_key_hash']:
        raise ValueError('다른 학생의 보고서는 변화 비교에 사용할 수 없습니다.')
    if parse_time(previous['as_of']) > parse_time(current['as_of']):
        raise ValueError('이전 보고서의 기준 시각이 현재보다 늦습니다.')
    if previous.get('comparison_scope') != current['comparison_scope']:
        return {'status': 'scope_changed', 'reason': '학과·선택 진로·대상 조건이 바뀌어 개선 여부 비교 생략',
                'transitions': [], 'newly_matched': [], 'no_longer_observed': [],
                'evidence_changed': [], 'new_conditions': []}
    before = {row['condition_id']: row for row in previous['condition_snapshot']}
    after = {row['condition_id']: row for row in current['condition_snapshot']}
    transitions, changed = [], []
    for key in sorted(before.keys() & after.keys()):
        if before[key]['requirement_hash'] != after[key]['requirement_hash']:
            changed.append(key)
        elif before[key]['state'] != after[key]['state']:
            transitions.append({'condition_id': key, 'from': before[key]['state'], 'to': after[key]['state']})
    return {'status': 'compared', 'previous_as_of': previous['as_of'], 'transitions': transitions,
            'newly_matched': [row['condition_id'] for row in transitions if row['to'] == 'matched'],
            'no_longer_observed': sorted(before.keys() - after.keys()),
            'new_conditions': sorted(after.keys() - before.keys()), 'evidence_changed': changed,
            'scope_note': '기록·시각 변화에 따른 일부 조건 비교. 사라진 조건과 기준 변경은 역량 향상으로 집계하지 않음.'}


def build_report(profile, *, student_key, catalog_path=DEFAULT_CATALOG, now=None, previous=None,
                 limit=3, ranker=None):
    if not isinstance(student_key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', student_key):
        raise ValueError('student_key는 영문·숫자·밑줄·하이픈 1~64자 로컬 식별값이어야 합니다.')
    result = recommend(profile, catalog_path=catalog_path, now=now, limit=limit)
    if ranker is not None:
        result = ranker(result)
    now = parse_time(result['as_of'])
    report = {'report_version': REPORT_VERSION, 'subject_key_hash': _digest(student_key),
        'as_of': result['as_of'], 'mode': result['mode'], 'student_context': result['student_context'],
        'comparison_scope': {'department': profile['department'],
            'pathways': sorted(result['student_context']['pathways']),
            'target_conditions': sorted(profile.get('target_conditions', []))},
        'condition_snapshot': [{'condition_id': group['id'], 'state': group['state'],
            'requirement_hash': _digest(_requirement(group))} for group in result['assessments']],
        'gap_matrix': gap_matrix(result['assessments'], now.date().isoformat()),
        'course_context': course_context(profile, catalog_path),
        'plan': action_plan(result['recommendations'], now), 'coverage': result['coverage'],
        'data_gaps': list(result['data_gaps']), 'references': [dict(ref) for ref in REFERENCES],
        'scope_note': result['scope_note'],
        'planning_note': '체크포인트는 재점검 일정이며 예상 취득 기간이나 점수 상승 보장이 아닙니다. '
                         '빈도는 현재 선택한 검수 자료 안의 관측 수이며 채용시장 전체 수요가 아닙니다.'}
    if report['course_context']['unmapped']:
        report['data_gaps'].append('일부 수강과목의 공식 진로 연결 근거가 부족합니다.')
    if 'gpt' in result:
        report['gpt'] = result['gpt']
    report['review'] = compare_reports(previous, report)
    return report


def render_markdown(report):
    def safe(value):
        return str(value).replace('|', '/').replace('\n', ' ')

    context = report['student_context']
    logic_labels = {'any': '중 하나', 'all': '모두', 'review': '원문 검토'}
    status_labels = {'required': '필수', 'preferred': '우대', 'mentioned': '언급'}
    state_labels = {'gap': '차이 있음', 'unknown': '미확인', 'matched': '현재 기록 해당', 'needs_review': '원문 검토'}
    review_labels = {'first_report': '첫 보고서', 'compared': '이전 보고서와 비교 완료', 'scope_changed': '비교 대상 변경'}

    def target_text(target):
        value = target.get('numeric_value')
        value = value if value is not None else target.get('text_value')
        if value is None:
            return target['credential'] + ' 보유'
        if isinstance(value, (int, float)):
            value = f'{value:g}점'
        suffix = ' 이상' if target['comparator'] in ('gte', 'grade_gte') else ''
        return f"{target['credential']} {value}{suffix}"

    lines = [f"# 취업 준비 계획 — {report['as_of'][:10]}",
             f"{context['department']} {context['year']}학년 · {', '.join(context['pathways'])}",
             '', report['scope_note'], '', '## 조건별 격차', '',
             '| 시험·자격 선택지 | 관계 | 차이 있음 | 미확인 | 해당 | 검토 필요 | 회사 수 |',
             '|---|---|---:|---:|---:|---:|---:|']
    for row in report['gap_matrix']:
        states = row['states']
        lines.append(f"| {safe(' / '.join(row['alternatives']))} | {logic_labels[row['logic']]} | "
                     f"{states['gap']} | {states['unknown']} | {states['matched']} | "
                     f"{states['needs_review']} | {row['employer_count']} |")
    lines += ['', report['planning_note'], '', '## 실행 순서', '']
    if not report['plan']:
        lines.append('현재 자료에서 새 준비·활동 후보가 없습니다.')
    for number, item in enumerate(report['plan'], 1):
        lines += [f"### {number}. {item['title']}", '', item['reason'], '']
        if item['historical_reference']:
            lines += ['과거 공고를 준비 기준으로 참고합니다.', '']
        for step in item['steps']:
            lines.append(f"- {step['checkpoint_on']}: {step['action']} 결과물: {step['deliverable']}")
        lines += ['', item['completion_rule'], '']
        for condition in item['conditions']:
            targets = [target_text(target) for target in condition['options']]
            lines.append(f"- {condition['title']} ({status_labels.get(condition['status'], condition['status'])}, "
                         f"{logic_labels[condition['logic']]}): " + '; '.join(targets))
        lines.extend(f"- [근거 원문]({url})" for url in item['source_urls'])
        lines.append('')
    lines += ['## 수강과목 연결', '']
    for item in report['course_context']['linked']:
        directions = sorted({match['direction'] for match in item['matches']})
        lines.append(f"- {item['course']}: 학교 진로표의 {', '.join(directions)}와 연결. {item['next_step']}")
        lines.extend(f"  - [학교 근거]({url})" for url in sorted({m['source_url'] for m in item['matches']}))
    lines.extend(f"- {item['course']}: {item['reason']}" for item in report['course_context']['unmapped'])
    lines += ['', report['course_context']['scope'], '', '## 이전 결과와 비교', '',
              f"비교 상태: {review_labels[report['review']['status']]}"]
    for transition in report['review']['transitions']:
        lines.append(f"- {transition['condition_id']}: {state_labels[transition['from']]} → {state_labels[transition['to']]}")
    for field, label in [('no_longer_observed', '관측 제외'), ('evidence_changed', '기준 변경'),
                         ('new_conditions', '새 관측 조건')]:
        if report['review'][field]:
            lines.append(f"- {label}: {', '.join(report['review'][field])}")
    if report['review'].get('reason'):
        lines.append(report['review']['reason'])
    lines += ['', '## 자료 보완 필요', '']
    lines.extend('- ' + gap for gap in report['data_gaps'])
    lines += ['', '## 설계 레퍼런스', '']
    lines.extend(f"- [{ref['name']}]({ref['url']}): {ref['adaptation']}" for ref in report['references'])
    return '\n'.join(lines) + '\n'

