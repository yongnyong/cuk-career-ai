from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.assistant.router import make_router
from app.assistant.service_data import MemoryAssistantStore
from app.assistant.startup_plan import StartupPlan, update_plan


def test_two_teams_draft_feedback_manual_edit_goal_change_and_isolation():
    store = MemoryAssistantStore()
    identity = SimpleNamespace(id="alice")
    for user, idea, customer in (
        ("alice", "대학생 AI 진로·창업 추천 서비스", "가톨릭대 재학생"),
        ("bob", "동아리 굿즈", "동아리 학생"),
    ):
        state = store.get_state(user)
        state.startup_plan = update_plan(StartupPlan(), dict(
            idea=idea, customer=customer, artifacts="시제품", goal="창업경진대회 지원"))
        store.save_state(user, state)
    app = FastAPI()
    app.include_router(make_router(lambda: identity, SimpleNamespace(store=store)))
    with TestClient(app) as client:
        def snapshot():
            return client.get("/api/assistant/startup-plan").json()

        def change(**body):
            return client.post("/api/assistant/startup-application", json={
                "revision": snapshot()["revision"], **body})

        first = change(action="generate").json()["plan"]["application"]
        assert "진로" in first["fields"]["overview"]["value"]
        assert first["fields"]["problem"]["status"] == "missing"
        assert first["fields"]["overview"]["sources"]
        assert any(n["action"] == "application_draft" for n in snapshot()["plan"]["nodes"])
        saved = change(action="save", values={"name": "팀이 직접 정한 이름"},
                       feedback="학생 한 명이 전공 수업을 들은 뒤 무엇을 준비할지 어렵다고 말했다.")
        assert saved.status_code == 200, saved.text
        regenerated = change(action="generate", field_ids=["problem"]).json()["plan"]["application"]
        assert regenerated["fields"]["name"]["value"] == "팀이 직접 정한 이름"
        assert "학생 한 명" in regenerated["fields"]["problem"]["value"]
        assert regenerated["fields"]["name"]["status"] == "edited"
        # Bulk regeneration also preserves the student's edits.
        assert change(action="generate").json()["plan"]["application"]["fields"]["name"]["value"] == "팀이 직접 정한 이름"
        assert client.post("/api/assistant/startup-application", json={
            "revision": 0, "action": "generate"}).status_code == 409
        revision = snapshot()["revision"]
        assert client.patch("/api/assistant/startup-plan", json={
            "revision": revision, "fields": {"goal": "고객 시연"}}).status_code == 200
        assert snapshot()["plan"]["application"]["fields"]["name"]["value"] == "팀이 직접 정한 이름"
        assert not any(n["active"] and n["action"] == "application_draft" for n in snapshot()["plan"]["nodes"])
        identity.id = "bob"
        assert snapshot()["plan"]["application"] is None
        other = change(action="generate").json()["plan"]["application"]
        assert "굿즈" in other["fields"]["overview"]["value"]
        assert "진로" not in other["fields"]["overview"]["value"]
        assert other["feedback"] == ""
        assert change(action="save", values={"invented": "x"}).status_code == 422
        revision = snapshot()["revision"]
        client.patch("/api/assistant/startup-plan", json={
            "revision": revision, "fields": {"idea": "새 프로젝트"}, "new_project": True})
        assert snapshot()["plan"]["application"] is None
