import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import startup_catalog
from app.startup_db import initialize


def test_public_catalog_matches_the_web_contract_and_handles_missing_db(tmp_path, monkeypatch):
    path = tmp_path / 'startup.db'
    monkeypatch.setattr(startup_catalog, 'DEFAULT_DB', path)
    app = FastAPI()
    app.include_router(startup_catalog.router)
    client = TestClient(app)
    assert client.get('/api/startup/catalog').status_code == 503
    initialize(path)
    data = client.get('/api/startup/catalog').json()
    assert data['nodes'] == [] and data['opportunities'] == []


def test_web_snapshot_keeps_conditional_requirements_and_raw_dates():
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[2] / 'web/src/lib/data/startupCatalog.json').read_text(encoding='utf-8'))
    assert len(data['opportunities']) == 16
    ai = next(o for o in data['opportunities'] if o['id'] == 'startup-cuk-277825')
    assert ai['deadlineStatus'] == 'date_only'
    assert ai['versions'][-1]['deadline'] == '2026-11-23'
    assert ai['documents'] == ['발표자료']
    assert any(r['document_type'] == '시제품' and r['necessity'] == 'optional' for r in ai['startup']['requirements'])
    assert ai['required'][0]['key'] == 'other'
