import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import ai_provider
from app.preparation import SKILLS, StudentInput, adapt_profile, prepare, require_local_ai, router
from app.career.tree_signals import build_tree_signals
from app.career.recommender import recommend, parse_time

NOW = parse_time('2026-11-18T10:00:00+09:00')


@pytest.fixture
def preparation_client():
    app = FastAPI()
    app.include_router(router)
    async def loopback(scope, receive, send):
        if scope['type'] == 'http':
            scope = {**scope, 'client': ('127.0.0.1', 12345)}
        await app(scope, receive, send)
    with TestClient(loopback) as client:
        yield client


def student(**overrides):
    return StudentInput(**{'departmentId': 'psychology', 'grade': 3, 'status': '재학',
                           'jobId': 'psy-counsel', 'skills': {'PSY-STAT': 'self'}, **overrides})


def choose_first(prompt, schema):
    data = json.loads(prompt[prompt.index('{'):])
    item = data['candidates'][0]
    return {'recommendations': [{'candidate_id': item['id'], 'reason_code': item['allowed_reasons'][0]}]}


def test_real_profile_maps_to_specific_pathway_and_grounded_plan():
    report = prepare(student(), use_ai=False, now=NOW)
    assert report['student_context']['pathways'] == ['심리상담']
    assert report['plan']
    assert all(item['source_urls'] and item['steps'] for item in report['plan'])
    assert all('사회복지사' not in item['title'] for item in report['plan'])


def test_successful_model_selects_existing_candidate_without_private_scores():
    seen = []
    value = student(departmentId='business', jobId='finance',
                    skills={'SK-TOEIC': 'self'}, scores={'SK-TOEIC': '820'})

    def ask(prompt, schema):
        seen.append(prompt)
        return choose_first(prompt, schema)

    report = prepare(value, now=NOW, ask=ask)
    assert report['ai']['status'] == 'completed'
    assert len(report['plan']) == 1
    assert '820' not in seen[0] and 'scores' not in seen[0] and 'pseudoId' not in seen[0]
    assert report['plan'][0]['source_urls']


@pytest.mark.parametrize('out', [
    {'recommendations': [{'candidate_id': 'invented', 'reason_code': 'goal_gap'}]},
    {'recommendations': []}, [],
])
def test_bad_model_outputs_explicitly_fall_back(out):
    report = prepare(student(), now=NOW, ask=lambda *_: out)
    assert report['ai']['status'] == 'fallback' and report['mode'] == 'rules_fallback'
    assert report['plan']


def test_model_failure_preserves_rule_output():
    def fail(*_):
        raise ai_provider.ModelUnavailable('not signed in')
    before = prepare(student(), use_ai=False, now=NOW)
    after = prepare(student(), now=NOW, ask=fail)
    assert before['plan'] == after['plan']
    assert after['ai']['status'] == 'fallback'


def test_missing_validity_does_not_claim_exam_requirement_met():
    value = student(departmentId='business', jobId='finance',
                    skills={'SK-TOEIC': 'self'}, scores={'SK-TOEIC': '900'})
    profile, _ = adapt_profile(value)
    profile['pathways'] = ['물류·구매']
    profile['target_conditions'] = ['standard:구매1팀']
    result = recommend(profile, now=NOW)
    tests = [option for group in result['assessments'] for option in group['options']
             if option['credential'] == 'TOEIC']
    assert tests and all(option['state'] == 'unknown' for option in tests)


def test_ported_engine_retains_alternative_and_valid_score_behavior():
    profile = {'department': '경영학과', 'year': 4, 'pathways': ['물류·구매'],
        'target_conditions': ['standard:구매1팀'], 'credential_inventory_complete': True,
        'alternative_confirmations': {'standard:구매1팀': 'not_applicable'},
        'credentials': [{'name': 'TOEIC', 'numeric_value': 820, 'valid_until': '2028-03-31'}]}
    assert recommend(profile, now=NOW)['assessments'][0]['state'] == 'gap'
    profile['credentials'].append({'name': 'TOEIC Speaking', 'numeric_value': 150, 'valid_until': '2028-03-31'})
    assert recommend(profile, now=NOW)['assessments'][0]['state'] == 'matched'


def test_school_experience_prerequisite_blocks_advanced_task():
    beginner = prepare(student(skills={}), use_ai=False, now=NOW)
    for item in beginner['plan']:
        if item['action_key'].startswith('track:'):
            assert 'PSY-COUNSEL-CASE' not in item['action_key']
    assert all('학교의' in item['reason'] for item in beginner['plan'] if item['action_key'].startswith('track:'))


def test_input_validation_and_department_track_boundary():
    with pytest.raises(ValueError):
        adapt_profile(student(departmentId='business'))
    with pytest.raises(ValueError):
        adapt_profile(student(departmentId='business', jobId='finance',
                              skills={'SK-TOEIC': 'self'}, scores={'SK-TOEIC': '10000'}))


def test_local_guard_rejects_remote_origin_and_remote_peer(monkeypatch):
    monkeypatch.setenv('CAREER_LOCAL_AI', '1')
    def request(host, origin):
        return Request({'type': 'http', 'client': (host, 1),
                        'headers': [(b'origin', origin.encode())]})
    require_local_ai(request('127.0.0.1', 'http://localhost:3000'))
    for peer, origin in [('192.0.2.1', 'http://localhost:3000'), ('127.0.0.1', 'https://outside.example')]:
        with pytest.raises(HTTPException) as failure:
            require_local_ai(request(peer, origin))
        assert failure.value.status_code == 403


def test_codex_transport_uses_existing_login_and_no_shell_tools(monkeypatch):
    monkeypatch.setattr(ai_provider, 'codex_binary', lambda: 'codex.exe')
    monkeypatch.setenv('OPENAI_API_KEY', 'do-not-send-key')

    def run(args, **kwargs):
        assert '--ignore-user-config' in args and '--ephemeral' in args
        assert args[args.index('--sandbox') + 1] == 'read-only'
        assert '--dangerously-bypass-approvals-and-sandbox' not in args
        assert 'shell_tool' in args and 'plugins' in args
        assert 'OPENAI_API_KEY' not in kwargs['env']
        assert not kwargs.get('shell')
        Path(args[args.index('--output-last-message') + 1]).write_text('{"ok":true}', encoding='utf-8')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(ai_provider.subprocess, 'run', run)
    assert ai_provider.codex_json('synthetic', {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}}) == {'ok': True}


def test_codex_timeout_releases_slot_and_does_not_return_logs(monkeypatch):
    monkeypatch.setattr(ai_provider, 'codex_binary', lambda: 'codex.exe')
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('secret-input', 90)
    monkeypatch.setattr(ai_provider.subprocess, 'run', timeout)
    for _ in range(2):
        with pytest.raises(ai_provider.ModelUnavailable, match='초과'):
            ai_provider.codex_json('synthetic', {'type': 'object'})


def test_catalog_cache_cannot_be_poisoned_by_returned_report():
    first = prepare(student(), use_ai=False, now=NOW)
    first['plan'][0]['source_urls'].clear()
    assert prepare(student(), use_ai=False, now=NOW)['plan'][0]['source_urls']


def test_tree_signals_http_returns_catalog_ids_without_student_records(preparation_client):
    value = student(departmentId='business', jobId='overseas-sales', grade=2,
                    skills={'SK-TOEIC': 'self'}, scores={'SK-TOEIC': '430'})
    response = preparation_client.post('/api/preparation/tree-signals', json={
        'profile': value.model_dump(), 'asOf': NOW.isoformat(),
    })
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == '2026-11-18'
    assert any(signal['basis'] in ('required', 'preferred') for signal in body['signals'])
    assert {signal['skillId'] for signal in body['signals']} <= SKILLS.keys()
    assert all(signal['reference']['url'].startswith('https://') for signal in body['signals'])
    assert '430' not in response.text


def test_condition_signal_respects_valid_alternative_and_ignores_unmapped_names():
    profile = {'department': '경영학과', 'year': 2, 'pathways': ['물류·구매'],
               'credential_inventory_complete': True,
               'credentials': [{'name': 'TOEIC Speaking', 'text_value': 'IH', 'valid_until': '2028-03-31'}]}
    job = {'nodes': [{'skill': 'SK-TOEIC'}]}
    skills = {'SK-TOEIC': {'id': 'SK-TOEIC', 'name': 'TOEIC', 'kind': '어학'}}
    reference = 'amkor-2026h2:condition:0:0'
    assert not any(s['reference']['id'] == reference for s in build_tree_signals(profile, job, skills, NOW)['signals'])
    profile['credentials'].clear()
    signal = next(s for s in build_tree_signals(profile, job, skills, NOW)['signals'] if s['reference']['id'] == reference)
    assert signal['skillId'] == 'SK-TOEIC' and signal['reference']['historical'] is True
    assert not build_tree_signals(profile, {'nodes': []}, skills, NOW)['signals']


def test_dietitian_evidence_survives_display_alias_and_preserves_planned_license():
    profile, job = adapt_profile(student(departmentId='food-nutrition', jobId='food', skills={}))
    signals = build_tree_signals(profile, job, SKILLS, NOW)['signals']
    dietitian = [s for s in signals if s['skillId'] == 'SK-DIET']
    assert any(s['reference']['organization'] == '부천시 어린이·사회복지급식관리지원센터' for s in dietitian)
    planned = next(s for s in dietitian if s['reference']['organization'] == '현대그린푸드')
    assert planned['status'] == 'unknown'
    assert '취득예정' in planned['reference']['summary']
    assert 'quote' not in planned['reference']
    assert '대체 인정' in planned['preparation']['action']
    assert 'SK-HYGIENIST' not in {node['skill'] for node in job['nodes']}
    optional = next(s for s in signals if s['skillId'] == 'SK-HYGIENIST')
    assert optional['reference']['scope'] == 'role' and optional['reference']['summary']
    assert optional['basis'] == 'preferred'


def test_startup_activity_does_not_expand_employment_tracks_even_for_ai_department():
    for department in ('ai', 'psychology'):
        profile, job = adapt_profile(student(departmentId=department, jobId='ai-engineer'))
        assert 'SK-BMC' not in {node['skill'] for node in job['nodes']}
        signals = build_tree_signals(profile, job, SKILLS, NOW)['signals']
        activities = [s for s in signals if s['skillId'] == 'SK-BMC' and s['basis'] == 'activity']
        assert not activities


def test_employment_events_preserve_bootcamp_and_exclude_startup_competitions():
    event = 'ACT-cuk-ai-startup-277825'
    for department in ('ai', 'psychology'):
        profile, job = adapt_profile(student(departmentId=department, jobId='ai-engineer'))
        signals = build_tree_signals(profile, job, SKILLS, NOW)['signals']
        matches = [s for s in signals if s['skillId'] == event]
        assert not matches
        assert not any('창업' in s['reference']['title'] for s in signals if s['basis'] == 'activity')
        assert any(s['skillId'] == 'ACT-cuk-bootcamp-277842' for s in signals)
        later = build_tree_signals(profile, job, SKILLS, parse_time('2026-12-10T10:00:00+09:00'))
        assert not any(s['skillId'] == event for s in later['signals'])


def test_new_credentials_are_resolved_from_actual_occupation_conditions():
    for department, job_id, expected in [('business', 'finance', 'SK-FINANCE-MANAGER'),
                                         ('nursing', 'clinical', 'SK-NURSING-LICENSE'),
                                         ('psychology', 'educator', 'SK-CHILDCARE-2'),
                                         ('psychology', 'educator', 'SK-KOREAN-TEACHER-2')]:
        profile, job = adapt_profile(student(departmentId=department, jobId=job_id))
        signals = build_tree_signals(profile, job, SKILLS, NOW)['signals']
        assert any(s['skillId'] == expected and s['reference']['scope'] == 'role' for s in signals)


def test_quest_action_http_uses_local_model_and_falls_back(preparation_client, monkeypatch):
    monkeypatch.setenv('CAREER_LOCAL_AI', '1')
    body = {'skillId': 'SK-SQL', 'actionKind': 'start', 'basis': 'preferred',
            'stage': 'prepare', 'timeBudget': 'short', 'scores': {'SK-TOEIC': '930'}}
    monkeypatch.setattr(ai_provider, 'generate_json', lambda *_: {'actionId': 'outline'})
    path = '/api/preparation/quest-action'
    assert preparation_client.post(path, json=body).json() == {'actionId': 'outline', 'status': 'completed'}
    assert preparation_client.post(path, json=body, headers={'Origin': 'https://elsewhere.example'}).status_code == 403

    def invalid(prompt, schema):
        assert '930' not in prompt and 'scores' not in prompt
        assert schema['properties']['actionId']['enum'] == ['first_exercise', 'outline']
        return {'actionId': 'invented_action'}

    monkeypatch.setattr(ai_provider, 'generate_json', invalid)
    assert preparation_client.post(path, json=body).json() == {'actionId': 'first_exercise', 'status': 'fallback'}
