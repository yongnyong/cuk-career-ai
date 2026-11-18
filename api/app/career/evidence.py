"""Load a versioned public evidence snapshot, never personal records."""
import json
from functools import lru_cache
from pathlib import Path

DEFAULT_CATALOG = Path(__file__).with_name('evidence.json')


@lru_cache(maxsize=4)
def load_catalog(path, signature):
    catalog = json.loads(Path(path).read_text(encoding='utf-8'))
    catalog['pathways'] = frozenset(catalog['pathways'])
    catalog['role_paths'] = {key: frozenset(value) for key, value in catalog['role_paths'].items()}
    for item in catalog['activities']:
        item['departments'] = frozenset(item['departments'])
    return catalog
