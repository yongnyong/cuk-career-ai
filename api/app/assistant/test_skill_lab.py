"""Exercise the local skill lab and the shared chat contract without external calls."""

import json

from . import model, skill_lab
from .repository import JsonAssistantStore, MockCareerData
from .service import AssistantService
from .skill_context import CatalogSkillData
from .test_chat import FakeModel, ask, update
from .test_documents import client_for
from .test_gemini_diagnostics import candidate
from .test_gemini_retries import install_transport

AI = "mock-ai-engineer"
DE = "mock-data-engineer"
PIPELINE = "mock-pipeline"


def lab_service(root, language_model=None, catalog=None):
    catalog = catalog or skill_lab._load_catalog(skill_lab._CATALOG)
    data = MockCareerData({"alice": "demo001", "bob": "demo002", **skill_lab._USERS}, skill_catalog=catalog)
    return AssistantService(data, JsonAssistantStore(root), language_model or FakeModel())


def test_lab_catalog_preserves_ids_and_projects_shared_and_role_specific_technology(tmp_path):
    service = lab_service(tmp_path)
    ai, de = (service.data.get_skill_tree(job_id) for job_id in (AI, DE))
    assert 6 <= len(ai.nodes) <= 10 and 6 <= len(de.nodes) <= 10
    assert {"mock-python-basics", "mock-sql"} <= ai.nodes.keys() & de.nodes.keys()
    assert "mock-model-evaluation" in ai.nodes.keys() - de.nodes.keys()
    assert PIPELINE in de.nodes.keys() - ai.nodes.keys()
    assert ai.nodes["mock-data-analysis"].skill_name == "데이터 분석"
    assert all(node.mock and node.description and node.learning_topics and node.importance
               for tree in (ai, de) for node in tree.nodes.values())

    graph = ai.context("mock-python-basics", "특성 공학과 모델 평가까지 어떻게 연결돼?")
    assert graph["nearestSuccessorHops"]["mock-feature-engineering"] == 2
    assert graph["nearestSuccessorHops"]["mock-model-evaluation"] == 2
    assert len(graph["mentionedSkillIds"]) == 2
    assert {"from": "mock-pandas", "to": "mock-feature-engineering"} in graph["edges"]
    result = ask(service, "이 노드의 선수학습과 후속 노드는?", page="tree", job_id=DE, skill_id=PIPELINE)
    assert "Python 기초와 SQL부터 배워요" in result.answer and "데이터 품질 관리" in result.answer
    assert "가상 스킬트리" in result.answer and not service.model.calls


def test_node_selection_and_comparison_carry_into_followup(tmp_path):
    service = lab_service(tmp_path)
    base = {"page": "tree", "job_id": AI}
    ask(service, "이 노드의 개념을 설명해 줄래?", skill_id="mock-pandas", **base)
    assert "표 형식 데이터를 읽고" in service.model.calls[-1][1]["selectedSkill"]["description"]
    ask(service, "이전 노드와 지금 노드는 뭐가 달라?", skill_id="mock-numpy", **base)
    _, context, _ = service.model.calls[-1]
    assert context["selectedSkill"]["skillId"] == "mock-numpy"
    assert context["comparisonSkill"]["skillId"] == "mock-pandas"
    assert context["serverShowsRelationships"]
    assert {"from": "mock-pandas", "to": "mock-numpy"} not in context["skillGraph"]["edges"]

    answer = ask(service, "그럼 어떤 걸 먼저 배우는 게 좋을까?", skill_id="mock-numpy", **base)
    _, context, _ = service.model.calls[-1]
    assert context["comparisonSkill"]["skillId"] == "mock-pandas"
    assert "학습 순서가 정해져 있는지 확인되지 않아요" in answer.answer
    assert "일반 학습 조언" not in answer.answer

    ask(service, "Pandas와 NumPy는 어떻게 달라?", **base)
    _, context, _ = service.model.calls[-1]
    assert {context[key]["skillId"] for key in ("referencedSkill", "comparisonSkill")} == {"mock-pandas", "mock-numpy"}
    assert "selectedSkill" not in context


def test_model_advice_does_not_override_server_catalog_relationships(tmp_path):
    service = lab_service(tmp_path)
    service.model.answer = {
        "answer": "NumPy는 Pandas의 선수학습이에요. 같은 표에서 결측치를 처리하는 작은 실습을 해 보세요.",
    }
    result = ask(service, "NumPy랑 Pandas는 뭐가 달라?", page="tree", job_id=AI, skill_id="mock-pandas")
    assert "학습 순서가 정해져 있는지 확인되지 않아요" in result.answer
    assert "NumPy는 Pandas의 선수학습" not in result.answer and "결측치를 처리하는 작은 실습" in result.answer


def test_role_change_keeps_two_separate_catalogs_and_user_learning_evidence(tmp_path):
    service = lab_service(tmp_path)
    claim = "나는 Python 기초만 알아."
    service.model.updates[claim] = [update("skill", "add", "Python", claim, progress="beginner")]
    ask(service, claim, page="tree", job_id=AI, skill_id="mock-pandas")
    answer = ask(service, "아까 노드와 현재 노드의 차이는?", page="tree", job_id=DE, skill_id=PIPELINE)
    _, context, _ = service.model.calls[-1]
    assert (context["selectedSkill"]["jobId"], context["comparisonSkill"]["jobId"]) == (DE, AI)
    assert "데이터 엔지니어의 가상 스킬트리" in answer.answer and "AI 엔지니어의 가상 스킬트리" in answer.answer
    assert any(record["provenance"] == "user_statement" and record["progress"] == "beginner"
               for item in context["learning"]["skillEvidence"] if item["skill"] == "Python 기초"
               for record in item["records"])

    comparison = ask(service, "AI 엔지니어와 데이터 엔지니어 스킬트리는 어떤 차이가 있어?", page="tree", job_id=DE)
    _, context, _ = service.model.calls[-1]
    trees = context["skillTreeComparison"]["trees"]
    assert {tree["jobId"] for tree in trees} == {AI, DE}
    assert {item["skillId"] for item in context["skillTreeComparison"]["sharedSkills"]} == {
        "mock-python-basics", "mock-sql",
    }
    for tree in trees:
        ids = {item["skillId"] for item in tree["nodes"]}
        assert all(edge["from"] in ids and edge["to"] in ids for edge in tree["edges"])
    assert "AI 엔지니어 스킬트리" in comparison.answer and "데이터 엔지니어 스킬트리" in comparison.answer
    assert "일반 학습 조언" not in comparison.answer and comparison.mock_data


def test_cyclic_and_invalid_edges_cannot_become_learning_order(tmp_path):
    ids = [f"loop-{index}" for index in range(12)]
    skills = [{"id": key, "name": key} for key in [*ids, "safe", "malformed", "other-role-only"]]
    nodes = [{"skill": key, "prereq": [ids[index - 1]]} for index, key in enumerate(ids)]
    nodes[0]["prereq"].extend([ids[0], "safe", "missing", "other-role-only", {}])
    nodes.extend([{"skill": "safe", "prereq": []}, {"skill": "malformed", "prereq": "safe"}])
    catalog = CatalogSkillData({"skills": skills, "jobs": [{"id": "cyclic-role", "name": "순환 검증", "nodes": nodes}]})
    tree = catalog.get_skill_tree("cyclic-role")
    graph = tree.context(ids[0], "loop-7과 비교하면?")
    assert graph["cycleNearSelection"] and graph["partial"]
    assert graph["edges"] == [{"from": "safe", "to": ids[0]}]
    assert tree.prerequisites["malformed"] == ()
    assert tree.node_payload(ids[0])["prerequisites"] == ["safe"]
    service = lab_service(tmp_path, catalog=catalog)
    answer = ask(service, "선수학습과 후속 노드는?", page="tree", job_id="cyclic-role", skill_id=ids[0]).answer
    assert "safe부터 배워요" in answer and "서로를 선행 조건으로 가리키는 연결은 학습 순서에서 제외" in answer
    assert "loop-11" not in answer and not service.model.calls


def test_http_keeps_selection_contract_and_does_not_resolve_foreign_job_node(tmp_path):
    service = lab_service(tmp_path)
    http = client_for(service)
    http.cookies.set("cuk_session", "alice-session")
    endpoint = "/api/assistant/chat"
    first = {"page": "tree", "jobId": AI, "skillId": "mock-data-analysis"}
    second = {"page": "tree", "jobId": DE, "skillId": PIPELINE}
    for screen, question in (
        (first, "이 노드는 무엇인가요?"),
        (second, "이전 노드와 비교하면 뭐가 달라?"),
    ):
        response = http.post(endpoint, json={"message": question, "conversationId": "tree", "context": screen})
        assert response.status_code == 200 and response.json()["contextIssues"] == []
    _, context, _ = service.model.calls[-1]
    assert context["comparisonSkill"]["skillId"] == first["skillId"]
    assert context["selectedSkill"]["skillId"] == second["skillId"]

    calls = len(service.model.calls)
    invalid = http.post(endpoint, json={"message": "이 노드는 뭐야?", "conversationId": "tree",
                                        "context": {**second, "skillId": first["skillId"]}})
    assert invalid.status_code == 200 and invalid.json()["contextIssues"] == ["unknown_skill"]
    assert len(service.model.calls) == calls
    history = http.get("/api/assistant/conversations/tree").json()["messages"]
    assert [turn["context"]["jobId"] for turn in history] == [AI, DE, DE]


def test_plan_loads_external_team_catalog_without_building_a_model(monkeypatch, tmp_path, capsys):
    path = tmp_path / "external.json"
    path.write_text(json.dumps({"skills": [{"id": "external-skill", "name": "External skill"}],
                                "jobs": [{"id": "external-role", "name": "External role",
                                          "nodes": [{"skill": "external-skill", "prereq": []}]}]}), encoding="utf-8")

    def unexpected(*args, **kwargs):
        raise AssertionError("plan does not use a model")

    monkeypatch.setattr(skill_lab, "GeminiModel", unexpected)
    monkeypatch.setenv("GEMINI_API_KEY", "external-fixture-key")
    assert skill_lab.main(["--catalog", str(path), "--plan"]) == 0
    output = capsys.readouterr().out
    assert "external-role" in output and "Gemini 요청 0회" in output and "external-fixture-key" not in output


def test_live_cli_uses_real_screen_ids_and_honors_budget_with_mock_transport(monkeypatch, capsys):
    api_key = "fixture-api-key"
    monkeypatch.setenv("GEMINI_API_KEY", api_key)
    calls, _ = install_transport(
        monkeypatch, candidate({"answer": "연습 안내 fixture@example.invalid " + api_key}),
        candidate({"answer": "카탈로그와 사용 목적을 확인했어요."}),
    )
    actions = iter([
        f":job {AI}", ":nodes", ":node mock-pandas", ":node missing", ":node mock-numpy",
        "이전 노드와 지금 노드는 뭐가 달라?",
        f":job {DE}", f":node {PIPELINE}", "이 노드를 어떻게 실습할까?",
        "데이터 품질은 어떻게 연습할까?",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(actions))
    store_paths = []
    run = skill_lab.run_session

    def record_store(service, **kwargs):
        store_paths.append(service.store.root)
        run(service, **kwargs)

    monkeypatch.setattr(skill_lab, "run_session", record_store)
    assert skill_lab.main(["--live", "--model", "gemini-fixture", "--max-requests", "2"]) == 0
    first, second = (json.loads(json.loads(request.data)["contents"][0]["parts"][0]["text"])
                     for request in calls)
    assert (first["selectedSkill"]["jobId"], first["selectedSkill"]["skillId"]) == (AI, "mock-numpy")
    assert first["comparisonSkill"]["skillId"] == "mock-pandas"
    assert (second["selectedSkill"]["jobId"], second["selectedSkill"]["skillId"]) == (DE, PIPELINE)
    assert all(not path.exists() for path in store_paths)
    output = capsys.readouterr().out
    assert "선택할 ID를 확인" in output and "요청 상한 2회에 도달" in output
    assert "fixture@example.invalid" not in output and api_key not in output


def test_cli_user_switch_isolates_memory_and_preserves_selected_screen(monkeypatch, tmp_path, capsys):
    service = lab_service(tmp_path)
    statement = "나는 Python 기초만 알아."
    service.model.updates[statement] = [update("skill", "add", "Python", statement, progress="beginner")]
    actions = iter([
        f":job {AI}", ":node mock-pandas", statement,
        ":user demo002", f":job {DE}", f":node {PIPELINE}", "어떻게 실습할까?",
        ":user demo001", "어떤 실습부터 시작할까?", ":quit",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(actions))
    skill_lab.run_session(service)
    assert [fact.value for fact in service.memory("demo001")] == ["Python"]
    assert service.memory("demo002") == []
    one = service.history("demo001", "skill-lab")
    two = service.history("demo002", "skill-lab")
    assert [turn.context.skill_id for turn in one.turns] == ["mock-pandas", "mock-pandas"]
    assert [turn.context.skill_id for turn in two.turns] == [PIPELINE]
    assert "가상 사용자 demo002" in capsys.readouterr().out
