"""Offline learning plans through the same service used by HTTP and the CLI."""

import re

import pytest

from .contracts import MemoryEdit
from .errors import ModelInvalidResponse
from .prompts import MEMORY, PRACTICE
from .test_chat import FakeModel, ask, update
from .test_skill_lab import AI, lab_service


def _day(task, minutes, done):
    return {"task": task, "minutes": minutes, "done": done}


def test_seven_day_plan_adjustment_today_and_verification(tmp_path):
    messages = (
        "나는 Python 기초만 알고 있어.\nPandas를 일주일 동안 공부할 계획을 세워줘.",
        "하루에 20분 정도밖에 못 하고, 처음부터 여러 개를 배우면 포기할 것 같아.",
        "오늘 당장 해야 하는 것 하나만 알려줘. 끝났는지 확인하는 방법도 알려줘.",
        "방금 실습을 제대로 끝냈는지 어떻게 확인해?",
    )
    original = [
        _day("CSV 파일을 열고 첫 행을 출력해요.", 35, "첫 행이 화면에 보여요."),
        _day("금액 열 하나를 출력해요.", 20, "금액만 세 개 보여요."),
        _day("조건에 맞는 행을 골라요.", 25, "조건에 맞는 행만 보여요."),
        _day("비어 있는 값을 찾아요.", 25, "빈 값의 개수를 확인해요."),
        _day("금액 전체의 합계를 계산해요.", 25, "합계가 숫자 하나로 나와요."),
        _day("항목별 합계를 계산해요.", 30, "항목마다 합계가 하나 나와요."),
        _day("같은 표로 지금까지 배운 작업을 복습해요.", 30, "표를 읽고 합계를 구하는 순서를 설명할 수 있어요."),
    ]
    revised = [
        _day("금액 3개만 입력해 작은 표를 출력해요.", 10, "금액 열이 하나이고 값이 100, 200, 300이에요."),
        original[1],
        _day("같은 표에서 200원 이상인 행만 골라요.", 15, "200과 300이 보여요."),
        _day("빈 값이 있는지 한 번 확인해요.", 15, "빈 값의 개수를 확인해요."),
        _day("금액 열의 합계를 계산해요.", 15, "600이 출력돼요."),
        _day("금액 열 하나를 다시 출력해요.", 10, "금액만 세 개 보여요."),
        _day("같은 표로 합계 한 가지만 복습해요.", 15, "도움 없이 600을 출력할 수 있어요."),
    ]
    code = 'import pandas as pd\nprint(pd.DataFrame({"금액": [100, 200, 300]}))'
    task = _day(f"아래 코드를 Pandas가 설치된 Python에서 실행해요.\n```python\n{code}\n```", 10,
                "`금액` 열 하나에 100, 200, 300이 한 줄씩 나오면 끝이에요.")
    expected = [
        {"mode": "plan", "days": 7}, {"mode": "adjust", "days": 7, "dailyMinutes": 20},
        {"mode": "task", "dailyMinutes": 20}, {"mode": "task", "dailyMinutes": 20, "verify": True},
    ]

    class ScriptedGemini(FakeModel):
        def generate(self, instruction, data, schema):
            result = super().generate(instruction, data, schema)
            if instruction == MEMORY:
                return result
            index = messages.index(data["message"])
            assert PRACTICE in instruction and data["practiceRequest"] == expected[index]
            prior = [turn["assistant"] for turn in data["conversation"]["recent"] if turn.get("priorPractice")]
            if index == 0:
                assert not prior
                assert any(fact["value"] == "Python" and fact["progress"] == "beginner"
                           and fact["provenance"] == "user_statement" for fact in data["facts"])
                return {"answer": "Python 기초에서 출발하는 7일 계획이에요.", "schedule": original}
            if index == 1:
                assert len(prior) == 1 and "CSV 파일" in prior[0] and "7일차" in prior[0]
                return {"answer": "7일 일정은 유지해요. 첫날에는 파일 준비를 빼면 더 쉽게 시작할 수 있어 작은 표를 만들어요.",
                        "schedule": revised}
            if index == 2:
                assert len(prior) == 1 and "1일차 · 10분" in prior[0] and "7일차" in prior[0]
                return {"answer": "조정한 계획의 첫 실습만 해 봐요.", "exercise": task}
            assert len(prior) == 1 and code in prior[0] and "7일차" not in prior[0]
            return {"answer": "출력의 열 이름이 `금액`인지 먼저 확인해요. 아래에 100, 200, 300이 각각 한 행씩 나오면 완료예요. 왼쪽 0, 1, 2는 행 번호예요."}

    service = lab_service(tmp_path, ScriptedGemini())
    quote = "나는 Python 기초만 알고 있어."
    service.model.updates[messages[0]] = [update("skill", "add", "Python", quote, progress="beginner")]
    counts, answers = [], []
    for message in messages:
        before = len(service.model.calls)
        answers.append(ask(service, message, page="tree", job_id=AI, skill_id="mock-pandas").answer)
        counts.append(len(service.model.calls) - before)

    full, adjusted, today, verification = answers
    day_numbers = r"\*\*(\d+)일차"
    assert re.findall(day_numbers, full) == re.findall(day_numbers, adjusted) == list("1234567")
    assert "파일 준비를 빼면 더 쉽게" in adjusted
    assert all(int(minutes) <= 20 for minutes in re.findall(r"일차 · (\d+)분", adjusted))
    assert adjusted.count("금액만 세 개 보여요.") == 2  # repeated checks on separate days are meaningful
    assert today.count("완료 기준") == 1 and "약 10분" in today and code in today and "2일차" not in today
    compile(code, "pandas_example", "exec")
    assert "100, 200, 300이 각각 한 행씩" in verification and "오늘 할 일" not in verification
    assert counts == [2, 2, 1, 1]  # unchanged from the original conversation


@pytest.mark.parametrize(("message", "days", "level", "subject", "task"), [
    ("Python을 3일 동안 연습할 계획을 세우면 어떨까?", 3, "beginner", "Python", "리스트에서 첫 값을 출력해요."),
    ("Python을 3일 동안 연습할 계획을 세우면 어떨까?", 3, "intermediate", "Python", "제너레이터의 메모리 사용 차이를 비교해요."),
    ("SQL을 7일간 학습할 계획을 세우면 어떨까?", 7, "beginner", "SQL", "SELECT로 열 하나만 골라요."),
    ("SQLD 자격증 1주일 준비 계획을 세우고 날마다 완료 기준을 확인할 수 있게 알려줄래요?",
     7, "preparing", "SQLD", "데이터 모델링 개념을 하나의 예시로 설명해요."),
])
def test_learning_plan_scope_applies_across_levels_and_subjects(tmp_path, message, days, level, subject, task):
    service = lab_service(tmp_path)
    kind = "certification" if level == "preparing" else "skill"
    service.add_memory("alice", MemoryEdit(kind=kind, value=subject, progress=level))
    service.model.answer = {"answer": "말씀하신 수준에 맞춰 기간 전체를 나눴어요.",
                            "schedule": [_day(task, 15, f"{day}번째 실습 결과를 확인해요.") for day in range(1, days + 1)]}
    reply = ask(service, message)
    prompt, context, schema = service.model.calls[-1]
    assert PRACTICE in prompt and context["practiceRequest"] == {"mode": "plan", "days": days}
    assert any(entry["value"] == subject and entry["progress"] == level for entry in context["facts"])
    assert schema["properties"]["schedule"]["minItems"] == schema["properties"]["schedule"]["maxItems"] == days
    assert f"{days}일차" in reply.answer and task in reply.answer and len(service.model.calls) == 1


def test_explicit_new_length_and_limit_stay_with_the_plan_across_a_document_turn(tmp_path):
    service = lab_service(tmp_path)
    fundamentals = _day("SELECT로 예시 표의 필요한 열을 선택해요.", 25, "고른 열이 두 개 보여요.")
    service.model.answer = {"answer": "SQL을 연습하는 7일 계획이에요.", "schedule": [fundamentals] * 7}
    ask(service, "SQL 학습 계획을 7일 동안 어떻게 진행하면 좋을까?")
    calls = len(service.model.calls)
    draft = ask(service, "데이터 분석 직무 지원동기를 300자 이내로 작성해줘. 없는 경력은 만들지 마.")
    assert draft.answer.startswith("[AI 초안]\n") and len(service.model.calls) == calls

    service.model.answer = {"answer": "기존 SQL 계획에서 가장 기본인 조회부터 3일 동안 연습해요.",
                            "schedule": [_day("열 하나만 조회해요.", 10, "열 하나가 나와요.")] * 3}
    revised = ask(service, "아까 7일 계획을 하루 20분 대신 하루 10분으로, 3일로 줄여줄래요?")
    _, context, _ = service.model.calls[-1]
    assert context["practiceRequest"] == {"mode": "adjust", "days": 3, "dailyMinutes": 10}
    assert "SELECT" in next(turn["assistant"] for turn in context["conversation"]["recent"] if turn.get("priorPractice"))
    assert "3일차" in revised.answer and "4일차" not in revised.answer


@pytest.mark.parametrize("count,minutes", [(1, 10), (7, 25)])
def test_incomplete_or_over_budget_schedule_is_not_presented_as_complete(tmp_path, count, minutes):
    service = lab_service(tmp_path)
    service.model.answer = {"answer": "일주일 계획이에요.",
                            "schedule": [_day("작은 실습을 해요.", minutes, "결과를 확인해요.")] * count}
    with pytest.raises(ModelInvalidResponse, match="학습 계획"):
        ask(service, "하루 20분으로 SQL을 일주일 공부할 계획은 어떻게 짜면 될까요?")
    assert len(service.model.calls) == 1
