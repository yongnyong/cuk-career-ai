"""Web profile adapter and grounded preparation planning API."""
import json
import math
import os
import time
from datetime import timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from pydantic import AwareDatetime, BaseModel, Field

from . import ai_provider
from .career.report import build_report
from .career.recommender import KST, parse_time
from .career.tree_signals import build_tree_signals

router = APIRouter()
CATALOG = json.loads((Path(__file__).parent / 'career/web_catalog.json').read_text(encoding='utf-8'))
DEPARTMENTS = {item['id']: item for item in CATALOG['departments']}
JOBS = {item['id']: item for item in CATALOG['jobs']}
SKILLS = {item['id']: item for item in CATALOG['skills']}
PATHWAYS = {
    'psy-counsel': ['심리상담'], 'psy-clinical': ['심리상담'], 'psy-develop': ['심리상담', '아동·보육'],
    'psy-org': ['인사·조직'], 'psy-research': ['사회조사·연구', '수학·통계'],
    'sw-youth': ['사회복지'], 'sw-facility': ['사회복지'], 'sw-medical': ['사회복지'],
    'sp-teacher': ['특수교육'], 'sp-rehab': ['특수교육'], 'sp-eval': ['특수교육'],
    'his-curator': ['학예·기록'], 'his-archive': ['학예·기록'],
    'ice-security': ['정보보안·인프라'], 'clo-design': ['패션·의류'], 'clo-tech': ['패션·의류'],
    'acc-cpa': ['회계·세무'], 'acc-tax': ['회계·세무'], 'acc-corp': ['회계·세무'],
    'ai-engineer': ['인공지능·데이터'], 'data-analyst': ['인공지능·데이터', '수학·통계'],
    'sw-developer': ['소프트웨어 개발'], 'electronics': ['전자·반도체'],
    'bio-researcher': ['바이오·제약'], 'bio-qa': ['바이오·제약'], 'pharma': ['약학', '바이오·제약'],
    'clinical': ['간호', '의학'], 'content-planner': ['미디어·콘텐츠'],
    'overseas-sales': ['국제무역', '영업'], 'finance': ['경영·기획', '회계·세무', '금융'],
    'marketer': ['마케팅'], 'public-sector': ['행정'], 'legal': ['법률'],
    'welfare': ['사회복지', '심리상담'], 'educator': ['특수교육', '아동·보육'],
    'designer': ['공간디자인', '패션·의류'], 'food': ['식품·영양'],
    'env-engineer': ['에너지·환경'], 'arts-planner': ['음악·공연', '미디어·콘텐츠'],
    'npo': ['신학·사목', '사회복지'],
}
REASONS = {
    'goal_gap': '선택한 진로의 명시 조건을 준비하는 후보예요.',
    'confirm_record': '추가 준비에 앞서 보유 이력과 인정 조건을 확인하는 후보예요.',
    'semester_experience': '현재 학년에 준비할 경험을 먼저 검토하는 후보예요.',
    'timing': '모집 일정과 참여 조건을 먼저 확인하는 후보예요.',
}


def require_local_ai(request):
    host = request.client.host if request.client else ''
    origin = request.headers.get('origin')
    if (os.environ.get('CAREER_LOCAL_AI') != '1' or host not in ('127.0.0.1', '::1', 'localhost')
            or (origin and urlparse(origin).hostname not in ('127.0.0.1', 'localhost', '::1'))):
        raise HTTPException(403, '개인 PC의 로컬 개발 환경에서만 사용할 수 있어요.')


class StudentInput(BaseModel):
    departmentId: str = Field(max_length=60)
    grade: int = Field(ge=1, le=6)
    status: str = Field(pattern='^(재학|휴학|졸업예정)$')
    jobId: str = Field(max_length=80)
    skills: dict[str, str] = Field(default_factory=dict, max_length=500)
    scores: dict[str, str] = Field(default_factory=dict, max_length=500)
    weeklyHours: int = Field(default=5, ge=1, le=80)


class PreparationBody(BaseModel):
    profile: StudentInput
    useAi: bool = True


class TreeSignalsBody(BaseModel):
    profile: StudentInput
    asOf: AwareDatetime


class QuestActionBody(BaseModel):
    skillId: str = Field(max_length=80)
    actionKind: Literal['start', 'improve', 'verify']
    basis: Literal['required', 'preferred', 'school', 'activity'] | None = None
    stage: Literal['explore', 'prepare', 'practice', 'apply']
    timeBudget: Literal['short', 'medium', 'long']


def choose_quest_action(body, ask=None):
    skill = SKILLS.get(body.skillId)
    choices = {
        'verify': ['review_record', 'review_source'],
        'improve': ['practice_gap', 'diagnose'],
        'start': ['first_exercise', 'outline'],
    }[body.actionKind]
    if body.actionKind == 'start' and skill and skill['kind'] in ('어학', '자격증'):
        choices = ['review_scope', 'diagnose']
    if body.actionKind == 'start' and body.basis == 'activity':
        choices = [*choices, 'review_activity']
    if body.actionKind == 'verify' and body.basis == 'activity':
        choices = ['review_activity']
    fallback = {'actionId': choices[0], 'status': 'fallback'}
    if skill is None or len(choices) == 1:
        return fallback
    schema = {'type': 'object', 'properties': {'actionId': {'type': 'string', 'enum': choices}},
              'required': ['actionId'], 'additionalProperties': False}
    facts = {'skill': skill['name'], 'category': skill['kind'], 'stage': body.stage,
             'time_budget': body.timeBudget, 'basis': body.basis, 'choices': choices}
    prompt = ('한국 대학생이 이 역량을 준비할 때 바로 실행할 수 있는 첫 행동을 하나 고르세요. '
              '주어진 행동 ID만 반환하세요. 학년별 준비 단계와 시간 범위를 고려하세요.\n'
              + json.dumps(facts, ensure_ascii=False))
    try:
        value = (ask or ai_provider.generate_json)(prompt, schema)
        if isinstance(value, dict) and set(value) == {'actionId'} and value['actionId'] in choices:
            return {'actionId': value['actionId'], 'status': 'completed'}
    except (ai_provider.ModelUnavailable, OSError, ValueError, TypeError):
        pass
    return fallback


def adapt_profile(student):
    department = DEPARTMENTS.get(student.departmentId)
    job = JOBS.get(student.jobId)
    if not department or not job:
        raise ValueError('등록된 학과와 목표 진로를 선택해 주세요.')
    if job.get('departments') and student.departmentId not in job['departments']:
        raise ValueError('선택한 학과에 연결되지 않은 학과 전용 진로예요.')
    name = '의학과' if department['id'] == 'medicine' else department['name']
    profile = {'department': name, 'year': student.grade,
        'enrollment_status': 'on_leave' if student.status == '휴학' else 'enrolled',
        'credential_inventory_complete': False, 'credentials': []}
    paths = PATHWAYS.get(job['id']) or PATHWAYS.get(job.get('base'))
    if paths:
        profile['pathways'] = paths
    for skill_id, state in student.skills.items():
        if state not in ('none', 'self', 'verified'):
            raise ValueError('보유 역량 상태를 확인해 주세요.')
        skill = SKILLS.get(skill_id)
        if not skill or state == 'none' or skill['kind'] not in ('어학', '자격증'):
            continue
        value = student.scores.get(skill_id, '').strip()
        record = {'name': skill['name']}
        scale = CATALOG['scales'].get(skill_id)
        if scale and value:
            if 'grades' in scale:
                if value not in scale['grades']:
                    raise ValueError('시험·자격 등급을 확인해 주세요.')
                record['text_value'] = value
            else:
                try:
                    number = float(value)
                except ValueError:
                    raise ValueError('시험 점수는 숫자로 입력해 주세요.') from None
                if not math.isfinite(number) or not scale['min'] <= number <= scale['max']:
                    raise ValueError('시험 점수 범위를 확인해 주세요.')
                record['numeric_value'] = number
        # This web profile currently has no exam validity fields. Keep them unknown.
        profile['credentials'].append(record)
    return profile, job


def add_track_candidates(result, student, job):
    source = job.get('srcUrl')
    if not source:
        return result
    candidates = list(result['candidates'])
    for node in job['nodes']:
        skill_id = node['skill']
        skill = SKILLS.get(skill_id)
        if not skill or student.skills.get(skill_id, 'none') != 'none':
            continue
        if any(student.skills.get(key, 'none') == 'none' for key in node.get('prereq', [])):
            continue
        credential = skill['kind'] in ('어학', '자격증')
        action_type = 'confirm_record' if credential else 'practice'
        candidates.append({'id': 'track:' + skill_id, 'action_key': 'track:' + skill_id,
            'type': action_type, 'title': skill['name'] + (' 보유·준비 상태 확인' if credential else ' 경험 준비'),
            'priority': (70 if student.grade <= 2 else 60) + (10 if node['required'] else 0),
            'reason': f"학교의 {job['name']} 진로표에 제시된 준비 항목이에요. 기업의 필수 지원조건과 구분해 확인해요.",
            'allowed_reasons': ['confirm_record'] if credential else ['semester_experience'],
            'evidence': {'source_url': source, 'basis': 'school_roadmap',
                'target': node.get('target'), 'skill': skill_id, 'kind': skill['kind']}})
    candidates.sort(key=lambda candidate: (-candidate['priority'], candidate['id']))
    return {**result, 'candidates': candidates}


def rank_result(result, *, weekly_hours, ask=ai_provider.generate_json, limit=3):
    candidates = result['candidates'][:20]
    if not candidates:
        return result
    schema = {'type': 'object', 'properties': {'recommendations': {'type': 'array', 'maxItems': limit,
        'items': {'type': 'object', 'properties': {'candidate_id': {'type': 'string', 'enum': [c['id'] for c in candidates]},
                  'reason_code': {'type': 'string', 'enum': list(REASONS)}},
                  'required': ['candidate_id', 'reason_code'], 'additionalProperties': False}}},
        'required': ['recommendations'], 'additionalProperties': False}
    # No pseudoId, admission year, raw scores, grades, private files or full profile.
    compact = [{'id': c['id'], 'type': c['type'], 'title': c['title'], 'priority': c['priority'],
                'allowed_reasons': c['allowed_reasons'],
                'facts': {key: c['evidence'][key] for key in
                          ('status', 'logic', 'historical_reference', 'deadline', 'date_status', 'match_type', 'basis')
                          if key in c['evidence']}} for c in candidates]
    prompt = ('한국 대학생의 준비 후보 중 이번 학기 우선순위 최대 3개를 선택하세요. '
              '서버가 계산한 판정을 수정하거나 새 시험·점수·자격을 만들지 마세요. '
              '각 후보의 allowed_reasons에 있는 이유만 선택하세요. 저학년은 경험 탐색, '
              '고학년은 명시 조건 확인과 기한을 함께 고려하세요. 과거 공고는 현재 모집으로 취급하지 마세요.\n'
              + json.dumps({'year': result['student_context']['year'], 'weekly_hours': weekly_hours,
                            'candidates': compact}, ensure_ascii=False))
    out = ask(prompt, schema)
    if not isinstance(out, dict):
        raise ai_provider.ModelUnavailable('AI 추천 형식을 확인하지 못했어요.')
    selected = out.get('recommendations')
    if not isinstance(selected, list) or not 1 <= len(selected) <= limit:
        raise ai_provider.ModelUnavailable('AI가 올바른 개수의 추천을 반환하지 못했어요.')
    lookup, seen, ordered = {c['id']: c for c in candidates}, set(), []
    for entry in selected:
        if not isinstance(entry, dict) or set(entry) != {'candidate_id', 'reason_code'}:
            raise ai_provider.ModelUnavailable('AI 추천 형식을 확인하지 못했어요.')
        key, reason = entry['candidate_id'], entry['reason_code']
        if not isinstance(key, str) or key not in lookup or key in seen or reason not in lookup[key]['allowed_reasons']:
            raise ai_provider.ModelUnavailable('AI 추천이 제공된 근거와 맞지 않아 기본 순서를 표시해요.')
        seen.add(key)
        ordered.append({**lookup[key], 'ai_reason': REASONS[reason]})
    return {**result, 'mode': ai_provider.provider_name() + '_ranked', 'recommendations': ordered}


def prepare(student, *, use_ai=True, now=None, ask=None):
    profile, job = adapt_profile(student)
    ai = {'provider': ai_provider.provider_name(), 'status': 'disabled'}

    def ranker(result):
        nonlocal ai
        if (job.get('base') or job['id']) == 'founder':
            # The imported employment-condition catalog has no entrepreneurship pathway.
            result = {**result, 'assessments': [],
                'candidates': [c for c in result['candidates'] if not c['id'].startswith('condition:')],
                'coverage': {**result['coverage'], 'condition_groups': 0, 'matched': 0},
                'data_gaps': [*result['data_gaps'], '창업 지원 조건은 기존 공고 화면에서 확인해 주세요. 이 준비 모델의 조건 DB에는 아직 연결하지 않았어요.']}
        result = add_track_candidates(result, student, job)
        result['recommendations'] = result['candidates'][:3]
        if not use_ai or not result['candidates']:
            ai['status'] = 'disabled' if not use_ai else 'not_needed'
            return result
        start = time.perf_counter()
        try:
            ranked = rank_result(result, weekly_hours=student.weeklyHours, ask=ask or ai_provider.generate_json)
            ai.update(status='completed', latency_ms=round((time.perf_counter() - start) * 1000))
            return ranked
        except (ai_provider.ModelUnavailable, ValueError, TypeError, KeyError, OSError):
            ai.update(status='fallback', message='AI 연결·응답 확인에 실패해 근거 기반 기본 순서를 표시해요.')
            return {**result, 'mode': 'rules_fallback'}

    report = build_report(profile, student_key='local-profile', now=now, ranker=ranker)
    report.pop('subject_key_hash', None)
    report['ai'] = ai
    report['evidence_snapshot_on'] = '2026-11-18'
    report['selected_job'] = job['name']
    current = parse_time(report['as_of'])
    for item in report['plan']:
        if item['type'] == 'practice':
            item['steps'] = [
                {'checkpoint_on': (current.date() + timedelta(days=3)).isoformat(),
                 'action': '학교 진로표와 강의·활동 내용을 확인해 실습할 주제를 정하세요.',
                 'deliverable': '선택한 주제와 참고한 학교 근거'},
                {'checkpoint_on': (current.date() + timedelta(days=7)).isoformat(),
                 'action': f'주 {student.weeklyHours}시간 안에서 첫 과제·활동 결과물을 준비하고 진행을 점검하세요.',
                 'deliverable': '작업물 초안과 다음 주 계획'}]
            item['completion_rule'] = '실제 수행한 경험과 결과물을 확인해 상태를 갱신하세요.'
    return report


@router.get('/api/ai/status')
def ai_status():
    return ai_provider.status()


@router.post('/api/preparation/tree-signals')
def preparation_tree_signals(body: TreeSignalsBody):
    try:
        profile, job = adapt_profile(body.profile)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return build_tree_signals(profile, job, SKILLS, body.asOf.astimezone(KST))


@router.post('/api/preparation/quest-action')
def preparation_quest_action(body: QuestActionBody, request: Request):
    require_local_ai(request)
    return choose_quest_action(body)


@router.post('/api/preparation/plan')
def preparation_plan(body: PreparationBody, request: Request):
    require_local_ai(request)
    try:
        return prepare(body.profile, use_ai=body.useAi)
    except ValueError as exc:
        if str(exc) == 'DB에 없는 학과입니다.':
            return {'plan': [], 'ai': {'provider': ai_provider.provider_name(), 'status': 'not_needed'},
                    'data_gaps': ['이 학과의 검수된 준비 근거를 아직 연결하지 못했어요.'],
                    'evidence_snapshot_on': '2026-11-18', 'gap_matrix': []}
        raise HTTPException(422, str(exc)) from None
