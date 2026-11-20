"""Import the previously built engine and its public evidence into this repository.

Run once from the repo root: python scripts/import-career-model.py --source ..
No student tables or raw legacy postings are exported.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path


def import_model(source, destination):
    source = source.resolve()
    sys.path.insert(0, str(source))
    from career_recommender import _catalog_snapshot
    from career_db import connect, fetch

    database = source / 'data/career.db'
    stat = database.stat()
    catalog = _catalog_snapshot(str(database), (stat.st_ino, stat.st_size, stat.st_mtime_ns))
    with connect(database) as db:
        catalog['roadmaps'] = fetch(db, '''SELECT r.id,r.direction,r.courses_raw,d.name AS department,s.url AS source_url
            FROM roadmaps r JOIN departments d ON d.id=r.department_id JOIN sources s ON s.id=r.source_id
            WHERE r.status='parsed' AND r.courses_raw IS NOT NULL ORDER BY r.id''')
    catalog['provenance'] = {'snapshot_on': '2026-11-18', 'source': 'reviewed career.db',
        'scope': '검수된 조건·활동·학과 진로표. 학생 테이블·합격수기·원문 전체는 제외.'}
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'evidence.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2,
        default=lambda value: sorted(value) if isinstance(value, (set, frozenset)) else str(value)), encoding='utf-8')
    (destination / '__init__.py').write_text('"""Grounded career preparation engine."""\n', encoding='utf-8')

    code = (source / 'career_recommender.py').read_text(encoding='utf-8')
    code = code[:code.index('\ndef main():')]
    code = code.replace('from career_db import DEFAULT_DB, connect, fetch',
                        'from .evidence import DEFAULT_CATALOG, load_catalog')
    start, end = code.index('@lru_cache(maxsize=4)'), code.index('\ndef recommend(')
    code = code[:start] + 'def _catalog_snapshot(catalog_path, signature):\n    return load_catalog(catalog_path, signature)\n\n' + code[end:]
    code = code.replace('DEFAULT_DB', 'DEFAULT_CATALOG').replace('db_path', 'catalog_path')
    (destination / 'recommender.py').write_text(code, encoding='utf-8')

    code = (source / 'career_agent.py').read_text(encoding='utf-8')
    code = code[:code.index('\ndef main():')]
    code = code.replace('from career_db import DEFAULT_DB, connect, fetch',
                        'from .evidence import DEFAULT_CATALOG, load_catalog')
    code = code.replace('from career_recommender import parse_time, recommend',
                        'from .recommender import parse_time, recommend')
    start, end = code.index('@lru_cache(maxsize=4)'), code.index('\ndef course_context(')
    code = code[:start] + 'def _roadmaps(catalog_path, signature):\n    return load_catalog(catalog_path, signature)["roadmaps"]\n\n' + code[end:]
    code = code.replace('DEFAULT_DB', 'DEFAULT_CATALOG').replace('db_path', 'catalog_path')
    code = code.replace('limit=3, use_gpt=False, require_gpt=False, model=None):', 'limit=3, ranker=None):')
    code = code.replace('    if use_gpt or require_gpt:\n        from career_gpt import rank_candidates\n        result = rank_candidates(result, model=model, limit=limit, required=require_gpt)',
                        '    if ranker is not None:\n        result = ranker(result)')
    (destination / 'report.py').write_text(code, encoding='utf-8')
    print(json.dumps({'condition_groups': len(catalog['groups']), 'activities': len(catalog['activities']),
                      'departments': len(catalog['departments'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    arguments = parser.parse_args()
    import_model(arguments.source, Path(__file__).resolve().parent.parent / 'api/app/career')
