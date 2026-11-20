"""Compare student records with scoped DB evidence and propose next actions."""
import argparse
import json
import math
import sqlite3
from functools import lru_cache
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .evidence import DEFAULT_CATALOG, load_catalog

KST = timezone(timedelta(hours=9))
GRADES = {
    'TOEIC Speaking': ['NL','NM','NH','IL','IM1','IM2','IM3','IH','AL','AM','AH'],
    'OPIc': ['NL','NM','NH','IL','IM1','IM2','IM3','IH','AL'],
}


def parse_time(value=None):
    if value is None:
        return datetime.now(KST)
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        result = result.replace(tzinfo=KST)
    return result.astimezone(KST)


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError('학생 이력은 JSON 객체여야 합니다.')
    if not isinstance(profile.get('department'), str):
        raise ValueError('department에 학과명을 입력하세요.')
    year = profile.get('year')
    if type(year) is not int or not 1 <= year <= 6:
        raise ValueError('year는 1~6 정수여야 합니다.')
    if type(profile.get('credential_inventory_complete', False)) is not bool:
        raise ValueError('credential_inventory_complete는 true 또는 false여야 합니다.')
    for name in ['credentials','pathways','secondary_departments','completed_activities',
                 'confirmed_opportunities','courses','target_conditions']:
        if not isinstance(profile.get(name, []), list):
            raise ValueError(f'{name}은 배열이어야 합니다.')
    for name in ['pathways','secondary_departments','completed_activities','confirmed_opportunities','courses','target_conditions']:
        if any(not isinstance(value,str) for value in profile.get(name,[])):
            raise ValueError(f'{name} 항목은 문자열이어야 합니다.')
    for credential in profile.get('credentials', []):
        if not isinstance(credential,dict) or not isinstance(credential.get('name'),str):
            raise ValueError('각 자격·어학 기록에 name이 필요합니다.')
        value = credential.get('numeric_value')
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or value < 0):
            raise ValueError('numeric_value는 유한한 0 이상의 숫자여야 합니다.')
        for field in ['earned_on','valid_until']:
            if credential.get(field):
                if not isinstance(credential[field],str):
                    raise ValueError(f'{field}는 YYYY-MM-DD 문자열이어야 합니다.')
                date.fromisoformat(credential[field])
        if credential.get('earned_on') and credential.get('valid_until'):
            if date.fromisoformat(credential['earned_on']) > date.fromisoformat(credential['valid_until']):
                raise ValueError('자격·어학 취득일은 유효기간 종료일보다 늦을 수 없습니다.')
        if credential.get('text_value') is not None and not isinstance(credential['text_value'],str):
            raise ValueError('text_value는 문자열이어야 합니다.')
    if profile.get('team_size') is not None and (type(profile['team_size']) is not int or profile['team_size']<1):
        raise ValueError('team_size는 1 이상의 정수여야 합니다.')
    confirmations = profile.get('alternative_confirmations',{})
    if not isinstance(confirmations,dict) or any(value not in ('not_applicable','check_with_employer') for value in confirmations.values()):
        raise ValueError('alternative_confirmations 값은 not_applicable 또는 check_with_employer입니다.')


def record_assessment(record, option, today):
    """Return only the observed credential condition, never whole-job eligibility."""
    if record.get('earned_on') and date.fromisoformat(record['earned_on']) > today:
        return {'state':'unknown','record_status':'planned','reason':'취득예정 기록은 취득 여부 확인 필요'}
    if record.get('valid_until') and date.fromisoformat(record['valid_until']) < today:
        return {'state':'gap','record_status':'expired','reason':'기록된 유효기간 만료'}
    operator = option['comparator']
    observed = record.get('numeric_value')
    text = record.get('text_value')
    if isinstance(text,str):
        text = text.strip().upper()
    gap = None
    if operator == 'gte':
        if observed is None:
            return {'state':'unknown','record_status':'missing_value','reason':'점수 기록 확인 필요'}
        gap = max(option['numeric_value']-observed,0)
        satisfied = gap == 0
    elif operator == 'grade_gte':
        levels = GRADES.get(option['credential'], [])
        if text not in levels or option['text_value'] not in levels:
            return {'state':'unknown','reason':'시험 등급 확인 필요. 점수와 등급의 자동 환산은 제공하지 않음'}
        satisfied = levels.index(text) >= levels.index(option['text_value'])
    elif operator == 'eq':
        if text is None:
            return {'state':'unknown','reason':'급수 기록 확인 필요'}
        satisfied = text.casefold() == option['text_value'].casefold()
    else:
        satisfied = True
    if not satisfied:
        return {'state':'gap','record_status':'scored','reason':'명시된 기준과 차이 있음','numeric_gap':gap}
    if option['kind'] == 'test' and not record.get('valid_until'):
        return {'state':'unknown','record_status':'missing_validity','reason':'점수·등급 기준에 해당하나 유효기간 확인 필요'}
    return {'state':'matched','record_status':'current','reason':'현재 기록이 이 자격·시험 항목의 기준에 해당'}


def assess_group(group, profile, aliases, now):
    options = []
    for option in group['options']:
        records = [record for record in profile.get('credentials', [])
                   if aliases.get(record['name'].strip().casefold(),record['name'].strip().casefold()) == option['credential'].casefold()]
        if records:
            results = [record_assessment(record, option, now.date()) for record in records]
            best_gap = min(results,key=lambda r:(r.get('record_status')=='expired',r.get('numeric_gap') or float('inf')))
            result = next((r for r in results if r['state']=='matched'),
                          next((r for r in results if r['state']=='unknown'),best_gap))
        else:
            result = {'state':'gap' if profile.get('credential_inventory_complete',False) else 'unknown',
                      'reason':'미보유로 확인' if profile.get('credential_inventory_complete',False) else '보유 여부 미확인'}
        options.append({**option,**result})
    states = [option['state'] for option in options]
    if group['logic']=='review':
        state = 'needs_review'
    elif group['logic']=='any':
        state = 'matched' if 'matched' in states else 'unknown' if 'unknown' in states else 'gap'
    else:
        state = 'gap' if 'gap' in states else 'unknown' if 'unknown' in states else 'matched'
    if state == 'gap' and group['human_alternative']:
        if profile.get('alternative_confirmations',{}).get(group['id']) != 'not_applicable':
            state = 'unknown'
    return {**group,'state':state,'options':options,
            'interpretation':'현재 기록과 공고의 일부 조건 비교. 학력·경력 등 전체 지원자격은 원문 확인.'}


def opportunity_state(item, now):
    today = now.date().isoformat()
    if item['ends_on'] and item['ends_on'] < today:
        return 'ended'
    if item['closes_at'] and parse_time(item['closes_at']) <= now:
        return 'closed'
    if item['closes_on'] and item['closes_on'] < today:
        return 'closed'
    if item['opens_on'] and item['opens_on'] > today:
        return 'upcoming'
    if not item['closes_on']:
        return 'check_dates'
    if item['closes_on'] == today and not item['closes_at']:
        return 'check_cutoff'
    return 'within_announced_window'


def activity_candidate(item, profile, department_names, now):
    if item['id'] in profile.get('completed_activities',[]):
        return None
    timing = opportunity_state(item, now)
    if timing in ('ended','closed','upcoming') or item['eligibility_status']!='reviewed':
        return None
    if item['min_year'] is not None and profile['year'] < item['min_year']:
        return None
    if item['max_year'] is not None and profile['year'] > item['max_year']:
        return None
    if item['departments'] and not department_names.intersection(item['departments']):
        return None
    checks = []
    enrollment = profile.get('enrollment_status','unknown')
    audience = item['audience'] or ''
    accepted = enrollment=='enrolled' and ('재학생' in audience or '학생' in audience)
    accepted = accepted or enrollment=='graduated' and '졸업생' in audience
    accepted = accepted or enrollment=='on_leave' and '휴학생' in audience
    if enrollment in ('graduated','on_leave') and '재학생' in audience and not accepted:
        return None
    if not accepted:
        checks.append('현재 재학·참여 대상 여부 확인')
    if timing in ('check_dates','check_cutoff'):
        checks.append('정확한 모집 기한과 접수 상태 확인')
    size = profile.get('team_size')
    if item['min_team'] and (size is None or size < item['min_team']):
        checks.append(f"{item['min_team']}명 이상 팀 구성 필요")
    if item['max_team'] and size is not None and size > item['max_team']:
        checks.append(f"{item['max_team']}명 이하 팀 구성 필요")
    if item['prereq_text'] and item['id'] not in profile.get('confirmed_opportunities',[]):
        checks.append(item['prereq_text'])
    action = 'check_activity' if checks else 'consider_activity'
    score = 90 if profile['year']<=2 else 65
    if checks:
        score -= 15
    if item['closes_on'] and 0 <= (date.fromisoformat(item['closes_on'])-now.date()).days <= 7:
        score += 10
    return {'id':'activity:'+item['id'],'action_key':'activity:'+item['id'],'type':action,'title':item['title'],
            'priority':score,'reason':'; '.join(checks) if checks else '공개된 대상·기간과 기록을 대조한 참여 후보',
            'allowed_reasons':['semester_experience','timing'],
            'evidence':{'source_url':item['source_url'],'audience':item['audience'],
                        'deadline':item['closes_at'] or item['closes_on'],'outcome':item['outcome'],
                        'date_status':timing,'checks':checks,'pathways':list(item['pathways']),
                        'scope':'프로그램 참가 후보. 실제 접수 가능 여부와 상세 자격은 신청 전 확인.'}}


def condition_candidate(group, profile, now):
    """Choose an observed next action while preserving all OR alternatives."""
    if group['state']=='matched' or group['status']=='mentioned':
        return None
    preparing = group['state']=='gap'
    options = group['options']
    names = '|'.join(sorted(option['credential'] for option in options))
    action_key = ('choose:' if preparing else 'confirm:')+names
    action_type = 'prepare' if preparing else 'confirm_record'
    title = f"{group['company']} {group['role']}의 {group['category']} " + ('준비 경로 확인' if preparing else '기록·인정 조건 확인')
    missing = [f"{option['credential']}: {option['reason']}" for option in options if option['state']=='unknown']
    reason = '; '.join(missing) or group['human_alternative'] or group['note'] or '원문 조건 확인 필요'
    gaps = [option for option in options if option.get('numeric_gap')]
    expired = [option for option in options if option.get('record_status')=='expired']
    if preparing and len(gaps)==1:
        next_option = gaps[0]
        action_key = 'prepare:'+next_option['credential']
        reason = f"{next_option['credential']} 기준까지 {next_option['numeric_gap']:g}점"
    elif preparing and len(gaps)>1:
        reason = ' 또는 '.join(f"{option['credential']} 기준까지 {option['numeric_gap']:g}점" for option in gaps)
        reason += '. 인정되는 준비 경로 중 하나를 선택할 수 있습니다.' if group['logic']=='any' else '. 각 조건을 함께 확인하세요.'
    elif preparing and expired:
        next_option = expired[0]
        action_key = 'renew:'+next_option['credential']
        action_type = 'renew_score'
        title = next_option['credential']+' 만료 성적·자격 갱신 검토'
        reason = '기록된 유효기간이 만료되어 현재 인정 여부를 다시 확인해야 합니다. 새 성적은 각 모집팀의 기준과 비교하세요.'
    priority = (80 if group['status']=='required' else 60) if preparing else (75 if group['status']=='required' else 40)
    if profile['year']<=2:
        priority -= 15
    if group['source_kind'] in ('institutional_repost','platform_repost'):
        priority -= 15
    deadline = group['role_deadline_date'] or group['posting_deadline_date']
    return {'id':'condition:'+group['id'],'action_key':action_key,'type':action_type,
        'title':title,'priority':priority,'reason':reason,
        'allowed_reasons':['goal_gap'] if preparing else ['confirm_record'],
        'evidence':{'condition_id':group['id'],'status':group['status'],'logic':group['logic'],
            'options':options,'source_url':group['source_url'],'source_kind':group['source_kind'],
            'human_alternative':group['human_alternative'],'condition_note':group['note'],
            'historical_reference': bool(deadline and deadline<now.date().isoformat()),
            'deadline_date':deadline,'scope':group['interpretation']}}


def merge_actions(candidates):
    """One action card can cite several companies without duplicating the action."""
    merged = {}
    for candidate in sorted(candidates,key=lambda c:(-c['priority'],c['id'])):
        key = candidate['action_key']
        if not candidate['id'].startswith('condition:'):
            merged[key] = candidate
            continue
        evidence = candidate['evidence']
        related = {field:evidence[field] for field in ['condition_id','status','logic','options','source_url',
                                                      'source_kind','human_alternative','condition_note',
                                                      'historical_reference','deadline_date']}
        related['title'] = candidate['title']
        if key not in merged:
            merged[key] = {**candidate,'evidence':{**evidence,'related_conditions':[related]}}
        else:
            merged[key]['evidence']['related_conditions'].append(related)
    result = list(merged.values())
    for candidate in result:
        related = candidate['evidence'].get('related_conditions',[])
        if len(related)>1:
            if candidate['type']!='renew_score':
                candidate['title'] = candidate['action_key'].split(':',1)[1].replace('|',' / ')+' 관련 조건 확인'
            candidate['reason'] += f"; 같은 행동과 관련된 모집팀 조건 {len(related)}개를 함께 확인할 수 있습니다."
    return sorted(result,key=lambda c:(-c['priority'],c['id']))


def _catalog_snapshot(catalog_path, signature):
    return load_catalog(catalog_path, signature)


def recommend(profile, catalog_path=DEFAULT_CATALOG, now=None, limit=3):
    validate_profile(profile)
    if not 1<=limit<=10:
        raise ValueError('limit는 1~10이어야 합니다.')
    now = now or datetime.now(KST)
    if now.tzinfo is None:
        raise ValueError('now에는 시간대가 필요합니다.')
    now = now.astimezone(KST)
    catalog_path = Path(catalog_path).resolve()
    stat = catalog_path.stat()
    catalog = _catalog_snapshot(str(catalog_path),(stat.st_ino,stat.st_size,stat.st_mtime_ns))
    if profile['department'] not in catalog['departments']:
        raise ValueError('DB에 없는 학과입니다.')
    selected = list(profile.get('pathways') or catalog['departments'][profile['department']])
    if any(name not in catalog['pathways'] for name in selected):
        raise ValueError('DB에 없는 진로 유형입니다.')
    aliases = catalog['aliases']
    for record in profile.get('credentials',[]):
        canonical = aliases.get(record['name'].strip().casefold(),record['name'].strip().casefold())
        score = record.get('numeric_value')
        if score is None:
            continue
        if canonical=='toeic' and (not 10<=score<=990 or score%5):
            raise ValueError('TOEIC은 10~990점, 5점 단위로 입력하세요.')
        if canonical=='toeic speaking' and (not 0<=score<=200 or score%10):
            raise ValueError('TOEIC Speaking은 0~200점, 10점 단위로 입력하세요.')
    groups = [group for group in catalog['groups'] if set(selected).intersection(catalog['role_paths'].get(group['role_id'],set()))]
    targets = profile.get('target_conditions',[])
    if targets:
        if set(targets)-{group['id'] for group in groups}:
            raise ValueError('선택한 진로에 없는 target_conditions가 있습니다.')
        groups = [group for group in groups if group['id'] in targets]
    assessments = [assess_group(group,profile,aliases,now) for group in groups]
    activities = catalog['activities']
    candidates = []
    for group in assessments:
        candidate = condition_candidate(group,profile,now)
        if candidate:
            candidates.append(candidate)
    department_names = {profile['department'],*profile.get('secondary_departments',[])}
    linked_activity_count = 0
    for item in activities:
        if item['pathways'] and not set(selected).intersection(item['pathways']):
            continue
        candidate = activity_candidate(item,profile,department_names,now)
        if candidate:
            candidate['evidence']['match_type'] = 'pathway' if item['pathways'] else 'general_career'
            linked_activity_count += bool(item['pathways'])
            candidates.append(candidate)
    candidates = merge_actions(candidates)
    data_gaps = []
    if not assessments:
        data_gaps.append('선택 진로의 검수된 자격·어학 조건이 부족합니다.')
    if not linked_activity_count:
        data_gaps.append('참여 가능한 직무 연계 활동이 부족해 공통 진로 프로그램을 함께 확인합니다.')
    return {'as_of':now.isoformat(),'mode':'rules','student_context':{
                'department':profile['department'],'year':profile['year'],'pathways':selected},
            'recommendations':candidates[:limit],'candidates':candidates,'assessments':assessments,
            'data_gaps':data_gaps,
            'coverage':{'condition_groups':len(assessments),'matched':sum(g['state']=='matched' for g in assessments),
                        'activity_candidates':sum(c['id'].startswith('activity:') for c in candidates)},
            'scope_note':'일부 공고 조건과 활동에 근거한 준비 후보. 전체 지원자격과 합격 가능성은 평가하지 않음.'}

