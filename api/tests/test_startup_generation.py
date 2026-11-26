"""Contract tests use model doubles, not claims about live Gemini quality."""
from copy import deepcopy

import pytest

from app.assistant.startup_node_prompt import COMMON, SECTIONS
from app.assistant.startup_plan import StartupPlan, update_plan


def response(subject="맞춤 스킬트리 체험 테스트"):
    titles = [*COMMON, subject, "아이템 시제품 완성", "사업 운영 비용 산정"]
    return {"nodes": [dict(key=f"task_{i}", section=SECTIONS[0 if i < 3 else i - 2],
        title=title, completion=f"{title} 결과물과 확인 기록을 저장하세요.",
        reason="입력한 아이디어의 사용 가능성을 확인하기 위한 추천이에요.",
        priority=1 if i == 3 else 2, depends_on=[]) for i, title in enumerate(titles)]}


class Model:
    def __init__(self, result=None):
        self.result = result or response()
        self.calls = 0

    def generate(self, instruction, data, schema):
        self.calls += 1
        assert "미확인" in instruction and "식품" in instruction
        assert "nodes" in schema["properties"]
        self.data = data
        return deepcopy(self.result)


def test_idea_only_generates_four_sections_and_does_not_invent_profile():
    model = Model()
    plan = update_plan(StartupPlan(), {"idea": "대학생 취업·창업 AI 서비스"}, model=model)
    assert plan.generation_status == "generated"
    assert plan.customer == plan.goal == plan.artifacts == ""
    assert {n.section for n in plan.nodes} == set(SECTIONS)
    assert plan.nodes[0].title == "맞춤 스킬트리 체험 테스트"
    assert all(not n.completed and not n.evidence for n in plan.nodes)


def test_cache_completion_reload_and_goal_change():
    model = Model()
    plan = update_plan(StartupPlan(), {"idea": "AI 서비스"}, model=model)
    plan.nodes[0].completed = True
    identity = plan.nodes[0].id
    reloaded = StartupPlan.model_validate_json(plan.model_dump_json())
    same = update_plan(reloaded, {}, model=model)
    assert model.calls == 1
    assert same.nodes[0].completed and same.nodes[0].id == identity
    changed = update_plan(same, {"goal": "출시 준비"}, model=model)
    assert model.calls == 2
    assert next(n for n in changed.nodes if n.id == identity).completed
    fresh = update_plan(changed, {"idea": "식품 샘플"}, new_project=True, model=model)
    assert all(n.id != identity for n in fresh.nodes if n.active)


@pytest.mark.parametrize("invalid", ["cycle", "missing", "duplicate", "common", "completed"])
def test_invalid_generation_uses_rule_fallback(invalid):
    payload = response()
    if invalid == "cycle":
        payload["nodes"][0]["depends_on"] = ["task_3"]
        payload["nodes"][3]["depends_on"] = ["task_0"]
    elif invalid == "missing":
        payload["nodes"][0]["depends_on"] = ["missing"]
    elif invalid == "duplicate":
        payload["nodes"][0]["key"] = "task_1"
    elif invalid == "common":
        payload["nodes"][0]["title"] = "일반 역량 강화"
    else:
        payload["nodes"][0]["completed"] = True
    plan = update_plan(StartupPlan(), dict(idea="AI 서비스", customer="학생", goal="고객 인터뷰"), model=Model(payload))
    assert plan.generation_status == "fallback"
    assert plan.nodes[0].action == "customer"


def test_two_items_receive_distinct_model_outputs_and_topological_order():
    software = update_plan(StartupPlan(), {"idea": "진로 AI"}, model=Model())
    payload = response("시범 코칭 참여자 피드백 확인")
    payload["nodes"][3]["depends_on"] = ["task_4"]
    service = update_plan(StartupPlan(), {"idea": "초보 러너 코칭"}, model=Model(payload))
    assert software.nodes[0].title != service.nodes[0].title
    child = next(n for n in service.nodes if n.action == "generated:task_3")
    assert child.requires == [service.nodes[0].id]


def test_model_failure_does_not_erase_completed_work():
    class Unavailable:
        def generate(self, *args):
            raise OSError("unavailable")
    plan = update_plan(StartupPlan(), {"idea": "AI 서비스"}, model=Model())
    plan.nodes[0].completed = True
    changed = update_plan(plan, {"goal": "출시"}, model=Unavailable())
    assert changed.generation_status == "fallback"
    assert any(n.id == plan.nodes[0].id and n.completed for n in changed.nodes)


def test_intake_persists_generated_tree_and_stops_extra_signup_questions():
    from types import SimpleNamespace
    from app.assistant.contracts import ChatRequest
    from app.assistant.service_data import MemoryAssistantStore
    from app.assistant.startup_plan import chat_plan
    class IntakeModel(Model):
        def generate(self, instruction, data, schema):
            if "message" in data:
                return {"idea": "대학생 진로 AI 서비스"}
            return super().generate(instruction, data, schema)
    model = IntakeModel()
    service = SimpleNamespace(model=model, store=MemoryAssistantStore())
    request = ChatRequest(message="대학생 진로 AI 서비스를 만들어요", mode="startup_intake", request_id="once")
    answer = chat_plan(service, "alice", request)
    assert "체험 테스트" in answer.answer
    assert "누가 어떤 상황" not in answer.answer
    assert service.store.get_state("alice").startup_plan.generation_status == "generated"
    assert chat_plan(service, "alice", request) == answer
    assert model.calls == 1
    assert service.store.get_state("bob").startup_plan is None
