from app.assistant.startup_plan import StartupPlan, update_plan, extract_fields
from itertools import permutations


def test_fact_order_and_unchanged_form_preserve_recommendation():
    facts = [dict(idea="서점 재고 예측 소프트웨어"), dict(customer="독립 서점주"),
             dict(goal="고객 미팅"), dict(artifacts="작동하는 시제품")]
    for ordered in permutations(facts):
        plan = StartupPlan()
        for fields in ordered:
            plan = update_plan(plan, fields)
        active = next(n for n in plan.nodes if n.active)
        assert active.action == "demo"
        form = plan.model_dump(include={"idea", "customer", "goal", "artifacts"})
        assert update_plan(plan, form).model_dump() == plan.model_dump()

    plan = update_plan(StartupPlan(), dict(idea="학원 상담 요약 AI", customer="학원장",
        artifacts="시제품", goal="다음 주 원장님에게 보여드리기", action="demo"))
    form = plan.model_dump(include={"idea", "customer", "goal", "artifacts"})
    assert update_plan(plan, form).nodes[0].id == plan.nodes[0].id
    assert update_plan(plan, form).nodes[0].action == "demo"


def test_completed_task_identity_follows_project_and_goal():
    plan = update_plan(StartupPlan(), dict(idea="재고 예측 소프트웨어", customer="서점주",
        artifacts="시제품", goal="교내 창업대회 지원"))
    plan.nodes[0].completed = True
    renamed = update_plan(plan, dict(customer="독립서점 점주"))
    assert renamed.nodes[0].id == plan.nodes[0].id
    assert renamed.nodes[0].completed
    next_goal = update_plan(renamed, dict(goal="전국 창업 경진대회 지원"))
    active = next(n for n in next_goal.nodes if n.active)
    assert active.id != plan.nodes[0].id and not active.completed
    assert next(n for n in next_goal.nodes if n.id == plan.nodes[0].id).reason == plan.nodes[0].reason


def test_product_types_and_missing_inputs_change_real_deliverables():
    physical = update_plan(StartupPlan(), dict(idea="동아리 굿즈", customer="학생",
        artifacts="도안", goal="선주문"))
    software = update_plan(StartupPlan(), dict(idea="재고 예측 소프트웨어", customer="서점주",
        artifacts="예측 모듈", goal="선주문"))
    service = update_plan(StartupPlan(), dict(idea="러닝 코칭 서비스", customer="초보 러너",
        artifacts="코칭 커리큘럼", goal="선주문"))
    assert len({p.nodes[0].completion for p in (physical, software, service)}) == 3
    assert "수령" in physical.nodes[0].completion
    assert "도입" in software.nodes[0].completion
    assert "예약" in service.nodes[0].completion
    missing = update_plan(StartupPlan(), dict(idea="재고 예측 소프트웨어",
        customer="서점주", goal="고객 시연"))
    assert missing.nodes[0].action == "prototype"
    assert any(n.active and n.action == "demo" and missing.nodes[0].id in n.reuse for n in missing.nodes)
    interview = update_plan(StartupPlan(), dict(idea="재고 예측 소프트웨어",
        customer="서점주", goal="고객 인터뷰"))
    assert interview.nodes[0].output == "interview_guide"
    interview.nodes[0].completed = True
    launch = update_plan(interview, dict(goal="출시"))
    assert interview.nodes[0].id not in launch.nodes[0].reuse


def test_reuse_requires_matching_result_and_same_project():
    plan = update_plan(StartupPlan(), dict(idea="상담 요약 AI", customer="학원장",
        artifacts="시제품", goal="고객 시연"))
    demo = plan.nodes[0]
    demo.completed = True
    launched = update_plan(plan, dict(goal="제품 출시"))
    assert demo.id in launched.nodes[0].reuse
    changed = update_plan(launched, dict(idea="러닝 코칭", customer="러너", artifacts="", goal="출시"),
                          new_project=True)
    assert any(n.active for n in changed.nodes)
    assert all(demo.id not in n.reuse for n in changed.nodes if n.active)


def test_empty_model_result_and_negative_messages_do_not_trigger_fallback():
    class EmptyModel:
        def generate(self, *args):
            return {}
    plan = StartupPlan()
    assert extract_fields("창업대회에는 나갈 생각이 없어", plan) == {}
    assert extract_fields("창업대회에는 나갈 생각이 없어", plan, EmptyModel()) == {}
    assert extract_fields("창업대회가 괜찮대", plan, EmptyModel()) == {}
    assert extract_fields("시제품은 아직 없어요", plan)["artifacts"] == "없음"


def test_model_and_persisted_facts_use_existing_privacy_filter():
    class Model:
        def generate(self, instruction, data, schema):
            assert "010-1234-5678" not in str(data)
            assert "student@example.com" not in str(data)
            return dict(idea="AI 앱", customer="학생 student@example.com")
    fields = extract_fields("내 연락처는 010-1234-5678, 이메일 student@example.com, AI 앱을 만들고 있어",
                            StartupPlan(), Model())
    assert "student@example.com" not in fields["customer"]
    plan = update_plan(StartupPlan(), dict(idea="AI 앱", customer="student@example.com",
        artifacts="010-1234-5678", goal="출시"))
    assert "010-1234-5678" not in plan.model_dump_json()
    assert "student@example.com" not in plan.model_dump_json()


def test_legacy_completed_node_keeps_id_after_schema_upgrade():
    import hashlib
    old_id = "SUP-" + hashlib.sha256("상담 AI|학원장|demo".encode()).hexdigest()[:16]
    plan = StartupPlan.model_validate(dict(idea="상담 AI", customer="학원장", artifacts="시제품",
        goal="고객 시연", action="demo", nodes=[dict(id=old_id, action="demo", title="저장 당시 제목",
        completion="저장 당시 결과물", reason="저장 당시 이유", completed=True)]))
    upgraded = update_plan(plan, {})
    assert upgraded.nodes[0].id == old_id
    assert upgraded.nodes[0].completion == "저장 당시 결과물"


def test_selected_posting_uses_only_confirmed_unconditional_documents():
    from app.assistant.startup_plan import select_opportunity
    posting = dict(id="startup-demo", title="교내 창업대회", versions=[dict(version=2)],
        applyUrl="https://school.example/notice",
        sections=[dict(text="사업계획서 1부, 발표자료 제출. 수상 실적이 있으면 증빙 제출.")],
        startup=dict(requirements=[
            dict(document_type="사업계획서", necessity="required", evidence_quote="사업계획서 1부"),
            dict(document_type="발표자료", necessity="required", evidence_quote="발표자료 제출"),
            dict(document_type="수상 증빙", necessity="conditional", evidence_quote="수상 실적이 있으면 증빙 제출."),
            dict(document_type="임의 서류", necessity="required", evidence_quote="존재하지 않는 문구")]))
    plan = update_plan(StartupPlan(), dict(idea="재고 예측 AI", customer="서점주",
        artifacts="시제품", goal="고객 시연"))
    demo_id = plan.nodes[0].id
    plan.nodes[0].completed = True
    plan = update_plan(plan, dict(goal="교내 창업대회"))
    plan.nodes[0].completed = True
    plan.opportunity = select_opportunity(posting)
    plan = update_plan(plan, {})
    submissions = [node for node in plan.nodes if node.active]
    assert len(submissions) == 2
    assert all(demo_id in node.reuse for node in submissions)
    assert all(node.evidence[0].version == 2 for node in submissions)
    assert {node.evidence[0].title for node in submissions} == {"사업계획서", "발표자료"}
    assert "수상 증빙" not in str(submissions)


def test_selection_reads_separate_public_startup_catalog(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.assistant.service_data import ServiceCareerData
    from app.career_db import CareerBase, Posting
    from app import startup_catalog, startup_db

    engine = create_engine("sqlite://")
    CareerBase.metadata.create_all(engine)
    public_db = tmp_path / "startup.db"
    startup_db.initialize(public_db)
    posting = {"id": "startup-public", "startup": {"requirements": []}}
    monkeypatch.setattr(startup_db, "DEFAULT_DB", public_db)
    monkeypatch.setattr(startup_catalog, "catalog", lambda db: {"opportunities": [posting]})
    data = ServiceCareerData(sessionmaker(engine), Posting, lambda user: None)
    try:
        assert data.get_startup_posting(posting["id"]) == posting
        assert data.get_startup_posting("unknown") is None
    finally:
        engine.dispose()


def test_two_teams_receive_different_deliverables():
    goods = update_plan(StartupPlan(), dict(idea="동아리 굿즈", customer="동아리 학생",
        artifacts="디자인 도안", goal="첫 온라인 선주문", action="preorder"))
    ai = update_plan(StartupPlan(), dict(idea="상담 요약 AI", customer="학원장",
        artifacts="작동하는 시제품", goal="다음 주 고객 시연", action="demo"))
    assert "선주문" in goods.nodes[0].title
    assert "시연본" in ai.nodes[0].title
    assert "수령" in goods.nodes[0].completion
    assert "가상" in ai.nodes[0].completion


def test_goal_change_retains_completed_work_and_stable_ids():
    p = update_plan(StartupPlan(), dict(idea="상담 요약 AI", customer="학원장",
        artifacts="시제품", goal="고객 미팅", action="demo"))
    first = p.nodes[0]
    first.completed = True
    assert update_plan(p, dict(goal="고객 미팅", action="demo")).nodes[0].id == first.id
    new = update_plan(p, dict(goal="교내 창업대회 출전", action="competition"))
    assert next(n for n in new.nodes if n.id == first.id).completed
    assert new.nodes[0].action == "choose_opportunity"
    assert first.id not in new.nodes[0].reuse


def test_missing_info_never_invents_a_customer():
    p = update_plan(StartupPlan(), dict(idea="AI 서비스"))
    assert p.nodes == []


def test_structured_model_handles_other_products_and_questions_do_not_edit():
    class Model:
        def generate(self, instruction, data, schema):
            return dict(idea="재고 예측 도구", customer="동네 서점주",
                        artifacts="재고 예측 시제품", goal="서점 방문 시연", action="demo")
    fields = extract_fields("서점의 재고 예측 도구를 만들었고 방문해서 시연할 거예요", StartupPlan(), Model())
    plan = update_plan(StartupPlan(), fields)
    assert "서점주" in plan.nodes[0].title
    assert "재고 예측" in plan.nodes[0].title
    assert extract_fields("다른 팀이 대회에 나간다면?", plan, Model()) == {}
    revised = update_plan(plan, dict(idea="새 상품"), new_project=True)
    assert revised.customer == "" and not any(n.active for n in revised.nodes)


def test_api_intake_completion_goal_change_and_isolation():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    from app.assistant.router import make_router
    from app.assistant.service_data import MemoryAssistantStore

    class Model:
        def generate(self, *args):
            raise OSError("model unavailable")

    store = MemoryAssistantStore()
    posting = dict(id="startup-owned", title="교내 창업대회", versions=[dict(version=1)],
        applyUrl="https://school.example/startup",
        sections=[dict(text="사업계획서 1부를 제출하세요.")],
        startup=dict(requirements=[dict(document_type="사업계획서", necessity="required",
            evidence_quote="사업계획서 1부를 제출하세요.")]))
    service = SimpleNamespace(store=store, model=Model(),
        data=SimpleNamespace(get_startup_posting=lambda pid: posting if pid == posting["id"] else None))
    app = FastAPI()
    identity = SimpleNamespace(id="demo:plan-test")
    app.include_router(make_router(lambda: identity, service))
    c = TestClient(app)
    body = dict(message="학원 상담 요약 AI 시제품이 있고 다음 주 원장님에게 보여줘",
                mode="startup_intake", conversationId="main", requestId="first")
    first = c.post("/api/assistant/chat", json=body)
    assert first.status_code == 200, first.text
    assert "시연본" in first.json()["answer"]
    snapshot = c.get("/api/assistant/startup-plan").json()
    node = snapshot["plan"]["nodes"][0]
    assert c.post("/api/assistant/chat", json=body).json() == first.json()
    assert c.get("/api/assistant/startup-plan").json()["revision"] == snapshot["revision"]
    completed = c.patch("/api/assistant/startup-plan", json={
        "revision": snapshot["revision"], "node_id": node["id"], "completed": True})
    assert completed.status_code == 200
    assert c.patch("/api/assistant/startup-plan", json={
        "revision": snapshot["revision"], "fields": {"goal": "제품 출시"}}).status_code == 409
    changed = c.post("/api/assistant/chat", json={
        "message": "이제 교내 창업대회에 낼래", "conversationId": "main", "requestId": "second",
        "context": {"page": "tree", "startupNodeId": node["id"]}})
    assert changed.status_code == 200
    final = c.get("/api/assistant/startup-plan").json()["plan"]
    assert final["nodes"][0]["action"] == "choose_opportunity"
    assert next(n for n in final["nodes"] if n["id"] == node["id"])["completed"]
    detail = c.post("/api/assistant/chat", json={
        "message": "어떻게 준비해?", "context": {"startupNodeId": node["id"]}})
    assert node["completion"] in detail.json()["answer"]
    # Each form sends only changed fields, so a second tab preserves the first tab's goal.
    current = c.get("/api/assistant/startup-plan").json()
    a = c.patch("/api/assistant/startup-plan", json={
        "revision": current["revision"], "fields": {"goal": "전국 창업경진대회 지원"}})
    assert a.status_code == 200
    b = c.patch("/api/assistant/startup-plan", json={
        "revision": a.json()["revision"], "fields": {"customer": "지역 학원장"}})
    assert b.json()["plan"]["goal"] == "전국 창업경진대회 지원"
    selected = c.patch("/api/assistant/startup-plan", json={
        "revision": b.json()["revision"], "opportunity_id": posting["id"]})
    assert selected.status_code == 200, selected.text
    submission = next(n for n in selected.json()["plan"]["nodes"] if n["active"])
    assert submission["evidence"][0]["quote"] == "사업계획서 1부를 제출하세요."
    assert node["id"] in submission["reuse"]
    assert submission["evidence"][0]["posting_id"] == posting["id"]
    second = c.patch("/api/assistant/startup-plan", json={
        "revision": selected.json()["revision"], "fields": {"goal": "다른 창업대회 지원"}})
    assert second.status_code == 200
    assert second.json()["plan"]["opportunity"] is None
    assert next(n for n in second.json()["plan"]["nodes"] if n["active"])["completed"] is False
    identity.id = "demo:other"
    assert c.get("/api/assistant/startup-plan").json()["plan"] is None
    assert c.patch("/api/assistant/startup-plan", json={
        "revision": 0, "node_id": node["id"], "completed": True}).status_code == 422
