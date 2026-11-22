"""Connect reviewed occupational evidence to catalog skills, including new branches."""
from .evidence import DEFAULT_CATALOG, load_catalog
from .recommender import activity_candidate, assess_group


# Each activity has a published outcome corresponding to these catalog skills.
ACTIVITY_SKILLS = {
    'cuk-ai-camp-273142': ('SK-RESUME',),
    'cuk-ai-startup-277825': ('SK-BMC',),
    'cuk-live-toeic-277840': ('SK-TOEIC',),
    'cuk-mocktoeic-277841': ('SK-TOEIC',),
    'cuk-python-273043': ('SK-DA',),
    'cuk-r-267403': ('SK-STAT',),
    'cuk-tax-277410': ('ACC-C-CTA',),
}


def build_tree_signals(profile, job, skills, now, *, path=DEFAULT_CATALOG):
    stat = path.stat()
    catalog = load_catalog(str(path), (stat.st_ino, stat.st_size, stat.st_mtime_ns))
    snapshot = catalog['provenance']['snapshot_on']
    aliases = catalog['aliases']
    pathways = set(profile.get('pathways', []))
    node_ids = {node['skill'] for node in job['nodes']}
    if not node_ids:
        return {'version': snapshot, 'signals': []}
    by_name = {}
    # Prefer the student's track, then stable shared IDs before other departments' aliases.
    track_skills = [skills[node['skill']] for node in job['nodes'] if node['skill'] in skills]
    shared_skills = [skill for key, skill in skills.items() if key.startswith('SK-')]
    for skill in [*track_skills, *shared_skills, *skills.values()]:
        if skill and skill['kind'] in ('어학', '자격증'):
            name = skill['name'].strip().casefold()
            by_name.setdefault(aliases.get(name, name), skill['id'])

    signals = []
    for group in catalog['groups']:
        if (group['status'] not in ('required', 'preferred') or group['logic'] == 'review'
                or not pathways.intersection(catalog['role_paths'].get(group['role_id'], ()))):
            continue
        assessment = assess_group(group, profile, aliases, now)
        if group['logic'] == 'any' and assessment['state'] == 'matched':
            continue
        options = [option for option in assessment['options']
                   if option['credential'].casefold() in by_name and option['state'] != 'matched']
        if group['logic'] == 'any':
            # An existing record that may satisfy the group takes priority over another exam.
            pending = [option for option in assessment['options']
                       if option.get('record_status') == 'missing_validity']
            if pending:
                options = [option for option in options if option in pending]
            options = sorted(options, key=lambda option: (
                option['state'] != 'gap', by_name[option['credential'].casefold()] not in node_ids))[:1]
        for option in options:
            deadline = group['role_deadline_date'] or group['posting_deadline_date']
            signal = {
                'skillId': by_name[option['credential'].casefold()],
                'basis': group['status'],
                'status': 'gap' if option['state'] == 'gap' and not group['human_alternative'] else 'unknown',
                'reference': {
                    'id': group['id'], 'title': f"{group['company']} · {group['role']}",
                    'organization': group['company'], 'scope': 'role',
                    'url': group['source_url'], 'sourceKind': group['source_kind'],
                    'historical': bool(deadline and deadline < now.date().isoformat()),
                },
            }
            if group.get('text_type') == 'summary':
                signal['reference']['summary'] = group['original_text']
            elif group.get('text_type') == 'extracted':
                signal['reference']['quote'] = group['original_text']
            if group['category'] == '자격증':
                name = option['credential']
                if group['logic'] == 'any' and len(group['options']) > 1:
                    names = ' · '.join(o['credential'] for o in group['options'])
                    action = f'원문에 제시된 대안({names}) 중 내 기록으로 인정받을 수 있는 항목을 확인하세요.'
                elif group.get('human_alternative'):
                    action = f'{name} 보유 여부와 원문의 대체 인정 조건을 함께 확인하세요.'
                else:
                    action = f'{name}의 명칭·등급을 공고와 대조하고 보유 여부를 기록하세요.'
                signal['preparation'] = {'kind': 'direct', 'action': action,
                    'completion': '인정되는 자격, 현재 보유 여부, 다음에 확인할 조건을 기록하면 이번 확인을 마칩니다.'}
            if not group['human_alternative'] and option.get('record_status') == 'scored':
                if option['comparator'] == 'gte':
                    signal['minimum'] = format(option['numeric_value'], 'g')
                elif option['comparator'] == 'grade_gte':
                    signal['minimum'] = option['text_value']
            signals.append(signal)

    for item in catalog['activities']:
        role_match = bool(pathways.intersection(item['pathways']))
        matches = [skill_id for skill_id in ACTIVITY_SKILLS.get(item['id'], ())
                   if skill_id in skills and (skill_id in node_ids or role_match)]
        activity_id = 'ACT-' + item['id']
        if activity_id in skills:
            matches.append(activity_id)
        if not matches or (item['pathways'] and not role_match):
            continue
        activity = activity_candidate(item, profile, {profile['department']}, now)
        if activity is None:
            continue
        for skill_id in matches:
            signals.append({
                'skillId': skill_id, 'basis': 'activity',
                'status': 'gap' if activity['type'] == 'consider_activity' else 'unknown',
                'reference': {
                    'id': item['id'], 'title': item['title'], 'url': item['source_url'],
                    'historical': False,
                    'summary': ' '.join(filter(None, (item.get('outcome'), activity['reason']))),
                    **({'scope': 'campus'} if skill_id == activity_id else {'scope': 'role'} if role_match else {}),
                },
            })
    return {'version': snapshot, 'signals': signals}
