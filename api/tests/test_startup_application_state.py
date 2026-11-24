import pytest
from pydantic import ValidationError

from app.assistant.startup_application import ApplicationRequest, apply_request, application_view
from app.assistant.startup_plan import StartupPlan, update_plan
from app.assistant.service_data import MemoryAssistantStore


def test_different_teams_feedback_edits_and_persisted_goal_changes():
    store = MemoryAssistantStore()
    examples = [("alice", "대학생 AI 진로·창업 추천 서비스", "가톨릭대 재학생"),
                ("bob", "동아리 굿즈", "동아리 학생")]
    for user, idea, customer in examples:
        state = store.get_state(user)
        plan = update_plan(StartupPlan(), dict(idea=idea, customer=customer,
            artifacts="시제품", goal="창업경진대회 지원"))
        state.startup_plan = update_plan(apply_request(plan, ApplicationRequest(
            revision=0, action="generate")), {})
        store.save_state(user, state)
    alice = store.get_state("alice")
    bob = store.get_state("bob")
    assert "진로" in alice.startup_plan.application.fields["overview"].value
    assert "굿즈" in bob.startup_plan.application.fields["overview"].value
    plan = alice.startup_plan
    assert plan.application.fields["problem"].status == "missing"
    assert any(n.action == "application_feedback" for n in plan.nodes)
    plan = apply_request(plan, ApplicationRequest(revision=alice.revision, action="save",
        values={"name": "우리 팀의 이름"}, feedback="학생 한 명이 다음 준비를 고르기 어렵다고 말했다."))
    assert application_view(plan)["problem"]
    plan = update_plan(apply_request(plan, ApplicationRequest(
        revision=alice.revision, action="generate", field_ids=["problem"])), {})
    assert plan.application.fields["name"].value == "우리 팀의 이름"
    assert "학생 한 명" in plan.application.fields["problem"].value
    assert not application_view(plan)["problem"]
    assert not any(n.active and n.action == "application_feedback" for n in plan.nodes)
    plan = apply_request(plan, ApplicationRequest(revision=alice.revision, action="generate"))
    assert plan.application.fields["name"].status == "edited"
    assert plan.application.fields["name"].value == "우리 팀의 이름"
    alice.startup_plan = update_plan(plan, {"goal": "고객 시연"})
    store.save_state("alice", alice)
    reloaded = store.get_state("alice").startup_plan
    assert reloaded.application.fields["name"].value == "우리 팀의 이름"
    assert not any(n.active and n.action == "application_draft" for n in reloaded.nodes)
    assert store.get_state("bob").startup_plan.application.feedback == ""
    assert update_plan(reloaded, {"idea": "새 아이템"}, new_project=True).application is None


def test_changed_profile_and_missing_material_are_visible_without_invented_metrics():
    plan = update_plan(StartupPlan(), dict(idea="AI 추천 서비스", customer="재학생", goal="창업대회"))
    plan = apply_request(plan, ApplicationRequest(revision=0, action="generate"))
    assert "시제품" not in plan.application.fields["overview"].value
    assert plan.application.fields["problem"].value == ""
    changed = update_plan(plan, {"customer": "졸업생"})
    assert application_view(changed)["overview"]
    assert not application_view(changed)["name"]
    assert "졸업생" in apply_request(changed, ApplicationRequest(
        revision=0, action="generate", field_ids=["overview"])).application.fields["overview"].value
    for payload in ({"values": {"unknown": "x"}}, {"user_id": "other"}, {"field_ids": []}):
        with pytest.raises(ValidationError):
            ApplicationRequest(revision=0, action="save", **payload)


def test_route_revision_conflict_and_owner_state():
    from types import SimpleNamespace
    from app.assistant.router import make_router
    from app.assistant.errors import Conflict
    store = MemoryAssistantStore()
    state = store.get_state("alice")
    state.startup_plan = update_plan(StartupPlan(), dict(idea="AI 앱", customer="학생", goal="창업대회"))
    store.save_state("alice", state)
    router = make_router(lambda: None, SimpleNamespace(store=store))
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith("/startup-application"))
    with pytest.raises(Conflict):
        endpoint(ApplicationRequest(revision=0, action="generate"), "alice")
    result = endpoint(ApplicationRequest(revision=1, action="generate"), "alice")
    assert result["revision"] == 2
    assert store.get_state("alice").startup_plan.application
    assert store.get_state("bob").startup_plan is None
