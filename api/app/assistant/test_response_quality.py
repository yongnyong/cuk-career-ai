"""Offline checks of the final chat reply, including deterministic and model text."""

from .contracts import Fact, MemoryEdit, Profile
from .prompts import MEMORY, PRACTICE
from .test_chat import FakeModel, ask, update
from .test_memory_recall import RECALL, STATEMENT
from .test_skill_lab import AI, DE, PIPELINE, lab_service


def test_catalog_lookup_answers_the_requested_direction_in_prose_without_a_model(tmp_path):
    service = lab_service(tmp_path)
    selection = {"page": "tree", "job_id": DE, "skill_id": PIPELINE}
    before = ask(service, "선수학습은 뭐야?", **selection).answer
    after = ask(service, "다음 노드는 뭐야?", **selection).answer

    assert "가상 스킬트리" in before and "가상 스킬트리" in after
    assert "데이터 파이프라인 전에 Python 기초와 SQL" in before and "데이터 품질 관리" not in before
    assert "데이터 파이프라인 다음에는" in after and "데이터 품질 관리" in after and "Python" not in after
    assert " · " not in before + after and "?" not in before + after
    assert not service.model.calls


def test_skill_followup_builds_on_comparison_without_echoes_or_internal_labels(tmp_path):
    service = lab_service(tmp_path)
    context = {"page": "tree", "job_id": AI}
    ask(service, "이 기술은 뭐야?", skill_id="mock-pandas", **context)
    explanation = "Pandas는 표를 다루고 NumPy는 배열 계산에 쓰여요."
    service.model.answer = {"answer": explanation}
    compared = ask(service, "이전 노드와 지금 노드는 뭐가 달라?", skill_id="mock-numpy", **context)
    assert compared.answer.startswith(explanation)
    assert "가상 스킬트리" in compared.answer and "학습 순서가 정해져 있는지 확인되지 않아요" in compared.answer

    exercise = "배열의 모양을 바꾸고 계산 결과를 확인해 보세요."
    service.model.answer = {
        "answer": f"stage=consultation\n{explanation}\n일반 학습 조언: {exercise} {exercise}\n더 궁금한 점이 있으신가요?"
    }
    calls = len(service.model.calls)
    followup = ask(service, "그럼 어떤 걸 먼저 배우는 게 좋을까?", skill_id="mock-numpy", **context)
    assert followup.answer == exercise and len(service.model.calls) == calls + 1
    assert service.model.calls[-1][1]["comparisonSkill"]["skillName"] == "Pandas"


def test_consultation_uses_public_names_and_keeps_a_useful_clarification(tmp_path):
    service = lab_service(tmp_path)
    service.model.answer = {"answer": (
        "skillId: mock-pipeline\n"
        "mock-pipeline에서는 데이터가 들어오고 처리되는 흐름을 살펴봐요.\n"
        "평일에 공부할 수 있는 시간이 얼마나 되나요?\n더 궁금한 점이 있으신가요?"
    )}
    result = ask(service, "이 노드를 어떤 실습부터 시작하면 좋을까?", page="tree", job_id=DE, skill_id=PIPELINE)

    assert result.answer.startswith("데이터 파이프라인에서는")
    assert "평일에 공부할 수 있는 시간이 얼마나 되나요?" in result.answer and result.answer.count("?") == 1
    assert "mock-pipeline" not in result.answer and "skillId" not in result.answer
    assert len(service.model.calls) == 1


def test_prose_cleanup_leaves_exercise_code_intact(tmp_path):
    service = lab_service(tmp_path)
    code = '```python\nfor _ in range(2):\n    print("연습")\n    print("연습")\n```'
    service.model.answer = {"answer": f"기초 반복문부터 연습해 보세요. 기초 반복문부터 연습해 보세요.\n\n{code}"}
    answer = ask(service, "Python 반복문 예시를 보여줘.").answer
    assert answer.count("기초 반복문부터 연습해 보세요.") == 1 and code in answer


def test_role_difference_and_personal_fit_have_different_scope(tmp_path):
    service = lab_service(tmp_path)
    service.data.profiles["demo001"] = Profile(facts=[Fact(id="sql-record", kind="skill", value="SQL", source="official")])
    service.add_memory("alice", MemoryEdit(kind="interest", value="데이터 분석"))
    comparison = "데이터 분석가는 지표를 해석하고, 데이터 엔지니어는 데이터 흐름을 구축해요."
    service.model.answer = {"answer": comparison}
    plain = ask(service, "데이터 분석가와 데이터 엔지니어의 차이는 뭐야?")
    assert plain.answer == comparison and len(service.model.calls) == 1

    personal = "말씀하신 데이터 분석에 대한 관심을 고려하면 데이터 분석가부터 살펴보는 쪽을 추천해요."
    official = "SQL 역량은 공식 기록에서 확인돼요."
    service.model.answer = {"answer": f"{personal} {official} {comparison}"}
    fit = ask(service, "데이터 분석가와 데이터 엔지니어 중 어느 쪽이 내게 더 잘 맞을까?")
    assert fit.answer.startswith(personal) and fit.answer.count("말씀하신 데이터 분석") == 1
    assert fit.answer.count("공식 기록") == 1 and "데이터 모델링 역량은 어느 정도" in fit.answer
    assert len(service.model.calls) == 2


def test_recall_uses_user_words_and_keeps_simulated_project_separate(tmp_path):
    service = lab_service(tmp_path)
    save = ask(service, STATEMENT, page="tree", job_id=AI, skill_id="mock-pandas")
    result = ask(service, RECALL, page="tree", job_id=DE, skill_id=PIPELINE)
    own, sample = result.answer.split("\n\n", 1)

    assert save.memory_updated and len(service.memory("alice")) == 2
    assert "Python 기초 문법은 어느 정도 알고 있다고 말씀하셨어요" in own
    assert "데이터 분석 프로젝트는 해 본 경험이 없다고 말씀하셨어요" in own
    assert "Campus Data Lab" not in own and "Campus Data Lab" in sample and "가상 사용자 데이터" in sample
    assert "?" not in result.answer and len(service.model.calls) == 1


def test_draft_revision_keeps_scope_and_does_not_repeat_the_question(tmp_path):
    service = lab_service(tmp_path)
    service.add_memory("alice", MemoryEdit(kind="interest", value="데이터 분석"))
    service.add_memory("alice", MemoryEdit(kind="certification", value="SQLD", progress="preparing"))
    first = ask(service, "데이터 분석 직무 지원동기를 300자 이내로 작성해줘. 없는 경력은 만들지 마.")
    ask(service, "데이터 분석가와 데이터 엔지니어의 차이는 뭐야?")
    revised = ask(service, "아까 쓴 지원동기를 120자 이내로 줄여줘. SQLD 준비 상태를 반영해줘.")

    assert first.answer.startswith("[AI 초안]\n") and first.answer.count("?") == 1
    assert revised.answer.startswith("[AI 초안]\n") and "?" not in revised.answer
    body = revised.answer.splitlines()[1]
    assert len(body) <= 120 and "데이터 분석" in body and "SQLD 자격증을 준비 중" in body
    assert "Campus Data Lab" not in revised.answer and "취득" not in body
    assert len(service.model.calls) == 1  # only the intervening consultation


def test_pandas_plan_and_project_are_scaled_down_after_user_feedback(tmp_path):
    questions = (
        "Pandas는 어떤 도구야?",
        "Pandas를 일주일 동안 어떻게 공부하면 좋을까?",
        "첫 프로젝트로 어떤 걸 해 보면 좋을까?",
        "그 프로젝트는 너무 어렵고 부담스러워요.",
    )
    explanation = "Pandas는 표 형태의 데이터를 다루는 Python 라이브러리예요. 행과 열의 구분이 꼭 필요하답니다."
    plan = ("첫날은 15분 정도 CSV를 열고 열 이름을 출력해 보세요. 열 이름을 확인하면 첫날 실습은 끝이에요. "
            "이후에는 결측치 처리와 그룹별 집계를 하나씩 연습해요. 관심 있는 분야를 알려주실 수 있나요?")
    schedule = [{"task": task, "minutes": 15, "done": done} for task, done in (
        ("CSV를 열고 열 이름을 출력해요.", "열 이름을 확인하면 끝이에요."),
        ("표에서 열 하나를 골라요.", "그 열의 값만 보여요."),
        ("비어 있는 값을 세어요.", "빈 값의 개수가 나와요."),
        ("조건에 맞는 행 하나를 골라요.", "출력된 행이 조건에 맞아요."),
        ("항목별로 값의 개수를 세어요.", "항목마다 숫자가 하나씩 나와요."),
        ("파일을 열고 원하는 범위를 다시 골라요.", "어떤 행을 골랐는지 설명할 수 있어요."),
        ("첫날부터 배운 작업을 순서대로 복습해요.", "혼자서 열과 행을 고를 수 있어요."),
    )]
    project = ("일주일간의 지출을 정리하고 항목별 합계와 그래프를 만들어 보세요. "
               "훌륭한 첫걸음이 된답니다. 어떤 분야에 관심이 있으신가요?")
    adjustment = ("지출 분석에서 그래프와 항목별 집계는 다음으로 미뤄요. "
                  "오늘은 10분 정도만 써서 예시 지출 3건을 표에 넣고 금액 열의 합계를 한 번 출력해 보세요. "
                  "합계가 숫자 하나로 나오면 오늘 실습은 끝이에요. 관심 있는 분야를 알려주실 수 있나요?")

    class ScriptedGemini(FakeModel):
        def generate(self, instruction, data, schema):
            result = super().generate(instruction, data, schema)
            if instruction == MEMORY:
                return result
            message = data["message"]
            if message == questions[1]:
                return {"answer": plan, "schedule": schedule}
            if message != questions[-1]:
                return {"answer": dict(zip(questions, (explanation, plan, project)))[message]}
            prior = next((turn for turn in data["conversation"]["recent"] if turn.get("priorPractice")), {})
            if PRACTICE in instruction and "항목별 합계와 그래프" in prior.get("assistant", ""):
                return {"answer": adjustment}
            return {"answer": "기초부터 차근차근 공부해 보세요. 어떤 분야에 관심이 있으신가요?"}

    service = lab_service(tmp_path, ScriptedGemini())
    counts, answers = [], []
    for message in questions:
        before = len(service.model.calls)
        answers.append(ask(service, message, page="tree", job_id=AI, skill_id="mock-pandas").answer)
        counts.append(len(service.model.calls) - before)

    short, week, first_project, easier = answers
    assert "구분이 꼭 필요해요" in short and "답니다" not in short
    assert "15분" in week and "열 이름을 확인하면" in week and "7일차" in week
    assert "그래프를 만들어 보세요" in first_project and "훌륭한" not in first_project
    assert "다음으로 미뤄요" in easier and "10분" in easier and "지출 3건" in easier
    assert "합계가 숫자 하나로 나오면" in easier and "차근차근" not in easier
    assert "?" not in first_project + easier
    assert PRACTICE not in service.model.calls[0][0]
    assert all(PRACTICE in service.model.calls[index][0] for index in (1, 2, 4))
    assert counts == [1, 1, 1, 2] and service.model.calls[3][0] == MEMORY
    assert service.memory("alice") == []


def test_practice_adjustment_keeps_the_recent_proposal_and_respects_a_new_topic(tmp_path):
    service = lab_service(tmp_path)
    decision = "지출 3건의 합계를 계산해 보세요."
    preface = "\n".join(f"{step}번째 단계에서는 결과를 다시 확인해요." for step in range(20))
    service.model.answer = {"answer": f"{preface}\n{decision}"}
    pandas = {"page": "tree", "job_id": AI, "skill_id": "mock-pandas"}
    ask(service, "Pandas 학습 계획은 어떻게 짜면 좋을까?", **pandas)
    service.model.answer = {"answer": "오늘은 표 한 줄을 출력해 보세요."}
    ask(service, "아까 계획이 너무 어려워요.", **pandas)
    _, context, _ = service.model.calls[-1]
    reference, = [turn for turn in context["conversation"]["recent"] if turn.get("priorPractice")]
    assert decision in reference["assistant"] and 450 < len(reference["assistant"]) <= 800

    service.model.answer = {"answer": "데이터 흐름을 작은 단계로 나누면 이해하기 쉬워요."}
    ask(service, "데이터 파이프라인 개념이 어려워요. 어떤 개념인가요?", page="tree", job_id=DE, skill_id=PIPELINE)
    prompt, context, _ = service.model.calls[-1]
    assert PRACTICE not in prompt and not any(turn.get("priorPractice") for turn in context["conversation"]["recent"])
    assert context["selectedSkill"]["skillName"] == "데이터 파이프라인"


def test_plan_with_a_saved_time_budget_stays_available_for_adjustment(tmp_path):
    service = lab_service(tmp_path)
    quote = "평일 하루 15분 공부할 수 있어."
    message = f"{quote} SQL 학습 계획은 어떻게 짤까?"
    service.model.updates[message] = [update("study_time", "set", "평일 하루 15분", quote)]
    proposal = "예시 표에서 SELECT로 열을 확인한 뒤 조건을 하나 걸어 보세요."
    service.model.answer = {"answer": proposal}
    first = ask(service, message)
    assert first.memory_updated

    service.model.answer = {"answer": "오늘은 5분만 써서 열을 하나 조회해 보세요. 결과에 열 하나가 나오면 충분해요."}
    ask(service, "아까 계획은 시간이 너무 많이 걸려요.")
    _, context, _ = service.model.calls[-1]
    [reference] = [turn for turn in context["conversation"]["recent"] if turn.get("priorPractice")]
    assert reference["assistant"] == proposal and quote not in reference["user"]
    assert context["learning"]["availableTime"] == "평일 하루 15분"


def test_consultation_keeps_useful_detail_for_complex_decisions_and_short_facts(tmp_path):
    service = lab_service(tmp_path)
    service.model.answer = {"answer": "Pandas는 표 형태의 데이터를 읽고 정리하는 Python 라이브러리예요."}
    fact = ask(service, "Pandas가 뭐야?")
    assert fact.answer == service.model.answer["answer"] and PRACTICE not in service.model.calls[-1][0]

    detail = (
        "데이터 분석가는 지표를 해석해 원인을 설명하는 데 시간을 더 써요. "
        "데이터 엔지니어는 데이터가 안정적으로 전달되도록 처리 흐름을 설계해요.\n\n"
        "결과를 사람들에게 설명하는 일이 좋다면 분석가를, 반복 작업을 자동화하는 일이 좋다면 엔지니어를 먼저 살펴보세요. "
        "같은 데이터를 써서 짧은 분석과 자동 수집을 각각 해 보면 어떤 작업이 더 맞는지 판단하기 쉬워요."
    )
    service.model.answer = {"answer": detail}
    complex_answer = ask(service, "데이터 분석가와 데이터 엔지니어의 업무 차이와 선택 기준을 설명해 줘.")
    assert complex_answer.answer == detail and "?" not in fact.answer + complex_answer.answer
    assert len(service.model.calls) == 2
