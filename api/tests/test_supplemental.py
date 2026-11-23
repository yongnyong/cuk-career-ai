import json
from pathlib import Path

from app.career.supplemental import build_supplemental_postings


def test_supplement_preserves_sources_uncertain_deadlines_and_exact_citations():
    catalog = json.loads((Path(__file__).parents[1] / 'app/career/web_catalog.json').read_text(encoding='utf-8'))
    posts = build_supplemental_postings(catalog)
    assert len(posts) == 13
    assert len({p['id'] for p in posts}) == 13
    assert all(p['source']['url'].startswith('https://') and not p['isVirtual'] for p in posts)
    for posting in posts:
        sections = {s['id']: s['text'] for s in posting['sections']}
        for e in posting['preparationEvidence']:
            assert e['quote'] in sections[e['src']]
        assert all(c['src'] in sections for c in posting['required'])
    by_id = {p['id']: p for p in posts}
    for name in ('gangnamunni-eval', 'wins-eval', 'seoul-companion'):
        assert by_id['hist-supp-' + name + '-202611']['deadlineStatus'] == 'unknown'
    assert by_id['hist-supp-seoul-1388-202611']['opensAt'] == '2026-12-03T09:00:00+09:00'
    assert any(e['key'] == 'PR-PSY-PROGRAM' for e in by_id['hist-supp-pbcg-202611']['preparationEvidence'])
    alternatives = by_id['hist-supp-gangnamunni-eval-202611']['preparationEvidence']
    assert any(e['key'] == 'PR-EVAL-DATASET' and e['basis'] == 'preferred' and '또는' in e['quote'] for e in alternatives)
