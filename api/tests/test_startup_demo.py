import json
from pathlib import Path

from app.assistant.service_data import MemoryAssistantStore
from app.assistant.startup_demo import seojun_plan
from app.assistant.startup_plan import update_plan


def test_demo_is_shared_with_frontend_and_only_seeds_seojun():
    root = Path(__file__).resolve().parents[2]
    web = json.loads((root / "web/src/lib/data/startupDemo.json").read_text(encoding="utf-8"))
    api = json.loads((root / "api/app/assistant/startup_demo.json").read_text(encoding="utf-8"))
    assert api == web
    store = MemoryAssistantStore()
    assert store.get_state("demo:demo-minji:abc").startup_plan is None
    assert store.get_state("real-user").startup_plan is None
    state = store.get_state("demo:demo-seojun:abc")
    assert len(state.startup_plan.nodes) == 14
    assert sum(n.completed for n in state.startup_plan.nodes) == 4
    assert state.startup_plan.nodes[0].title == "맞춤 스킬트리 체험 테스트"
    state.startup_plan.nodes[0].completed = True
    store.save_state("demo:demo-seojun:abc", state)
    assert store.get_state("demo:demo-seojun:abc").startup_plan.nodes[0].completed
    assert not store.get_state("demo:demo-seojun:other").startup_plan.nodes[0].completed


def test_demo_completion_preserves_fixture_without_model_call():
    class NoCall:
        def generate(self, *args):
            raise AssertionError("fixture must not invoke Gemini")
    plan = seojun_plan()
    plan.nodes[0].completed = True
    result = update_plan(plan, {}, model=NoCall())
    assert result.generation_status == "fixture"
    assert len(result.nodes) == 14
    assert result.nodes[0].completed
