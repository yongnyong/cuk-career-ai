"""Connect reviewed evidence to existing skill IDs in a student's track."""
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
    by_name = {}
    for node in job['nodes']:
        skill = skills.get(node['skill'])
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
            options = sorted(options, key=lambda option: option['state'] != 'gap')[:1]
        for option in options:
            deadline = group['role_deadline_date'] or group['posting_deadline_date']
            signal = {
                'skillId': by_name[option['credential'].casefold()],
                'basis': group['status'],
                'status': 'gap' if option['state'] == 'gap' and not group['human_alternative'] else 'unknown',
                'reference': {
                    'id': group['id'], 'title': f"{group['company']} · {group['role']}",
                    'url': group['source_url'], 'sourceKind': group['source_kind'],
                    'historical': bool(deadline and deadline < now.date().isoformat()),
                },
            }
            if not group['human_alternative'] and option.get('record_status') == 'scored':
                if option['comparator'] == 'gte':
                    signal['minimum'] = format(option['numeric_value'], 'g')
                elif option['comparator'] == 'grade_gte':
                    signal['minimum'] = option['text_value']
            signals.append(signal)

    node_ids = {node['skill'] for node in job['nodes']}
    for item in catalog['activities']:
        matches = [skill_id for skill_id in ACTIVITY_SKILLS.get(item['id'], ()) if skill_id in node_ids]
        if not matches or (item['pathways'] and not pathways.intersection(item['pathways'])):
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
                },
            })
    return {'version': snapshot, 'signals': signals}
