"""Resolve the requested scope of learning advice and render bounded schedules."""

import re
from dataclasses import dataclass
from typing import Literal

from .errors import ModelInvalidResponse
from .prompts import TEXT, object_schema

_PLAN = re.compile(
    r"(?:학습|공부|연습|실습|준비)\s*(?:계획|일정|순서|루틴|로드맵)|어떻게\s*(?:공부|학습|연습|실습)|"
    r"(?:첫|작은|간단한|입문용|초보자용)\s*(?:실습|프로젝트)|프로젝트.{0,20}(?:추천|해\s*보면|시작)"
)
_PLAN_TOPIC = re.compile(r"계획|일정|로드맵|공부|학습|준비|연습|실습")
_PERIOD = re.compile(
    r"(?P<amount>\d{1,3})\s*(?P<unit>주일?|일)(?=간|동안|짜리|치|로|만|[^\d가-힣]|$)|(?P<week>일주일|한\s*주)(?!말)"
)
_ONE_TASK = re.compile(
    r"(?:오늘|지금|당장|바로).{0,38}(?:하나|한\s*(?:가지|개))|"
    r"(?:첫\s*(?:단계|작업)|할\s*일|과제|실습|작업).{0,16}(?:하나|한\s*(?:가지|개))"
)
_TODAY = re.compile(r"(?:오늘|지금)(?:은|에)?\s*(?:뭐부터|뭘|무엇부터|할\s*일|첫\s*(?:작업|실습|단계))")
_CHECK = re.compile(r"끝났는지|끝냈는지|제대로\s*했는지|잘\s*됐는지|완료\s*(?:여부|기준|했는지|됐는지)|성공\s*여부")
_PROGRESS = re.compile(
    r"(?<!\d)([1-9]\d{0,2})\s*일차\s*(?:까지|를|는)?\s*"
    r"(?:(?:실습|학습|과제|공부)(?:를|는)?\s*)?(?:다\s*)?(?:끝냈|마쳤|완료했|완료했었|완료함|했어|했습니다)"
)
_NEXT_STEP = re.compile(r"(?:그\s*)?다음(?:은|에는|에|으로|\s|[?？]|$)")
_REST = re.compile(r"휴식|쉬[는어]|과제\s*없|휴무")
_BARRIER = re.compile(r"어렵|어려[워운]|부담|막막|버겁|벅차|엄두|포기|더\s*쉽|시간.{0,15}(?:없|부족|많이\s*걸)")
_REVISION = re.compile(r"조정|수정|줄여|줄이|간단하게|다시\s*(?:짜|세[워우]|작성)|맞춰\s*(?:짜|줘|바꿔)")
_PRIOR = r"(?:(?:아까|앞서|방금|이전|기존)\s*.{0,14}|(?:그|이)\s*)"
_PRIOR_PRACTICE = re.compile(rf"{_PRIOR}(?:제안|계획|일정|실습|프로젝트|작업|코드)")
_PRIOR_PLAN = re.compile(rf"{_PRIOR}(?:계획|일정)")
_DURATION = r"(?:\d{1,2}\s*시간(?:\s*\d{1,2}\s*분)?|\d{1,3}\s*분)"
_TIME_LIMIT = re.compile(
    rf"(?:하루(?:에|당)?|일일|매일|평일(?:에는|에)?|오늘(?:은|에)?)\s*({_DURATION})|"
    rf"({_DURATION})\s*(?:정도\s*)?(?:밖에|이내|만\s*(?:가능|할|공부|쓸)|공부할\s*수)"
)
_MAX_DAILY_ENTRIES = 14


@dataclass(frozen=True)
class PracticeRequest:
    mode: Literal["plan", "adjust", "task"]
    days: int | None = None
    daily_minutes: int | None = None
    verify: bool = False
    plan_days: int | None = None
    completed_through: int | None = None

    def context(self) -> dict:
        result = {"mode": self.mode}
        if self.days:
            result["days"] = self.days
        if self.daily_minutes:
            result["dailyMinutes"] = self.daily_minutes
        if self.verify:
            result["verify"] = True
        if self.plan_days is not None and self.completed_through is not None:
            result["planDays"] = self.plan_days
            result["reportedProgress"] = {"completedThroughDay": self.completed_through, "provenance": "user_statement"}
        return result


def refers_to_practice(message: str) -> bool:
    return bool(_PRIOR_PRACTICE.search(message))


def refers_to_plan(message: str) -> bool:
    return bool(_PRIOR_PLAN.search(message))


def asks_next_step(message: str) -> bool:
    return bool(_NEXT_STEP.search(message))


def reported_progress(message: str) -> int | None:
    reports = [match for match in _PROGRESS.finditer(message) if not re.match(
        r"(?:는지|냐|다고\s*(?:가정|써)|[^.!?。？！\r\n]*[?？])", message[match.end():]
    )]
    return int(reports[-1][1]) if reports else None


def time_limit(message: str, *, stored: bool = False) -> int | None:
    matches = list(_TIME_LIMIT.finditer(message))
    if matches:
        match = matches[-1]
        duration = match[1] or match[2]
    elif stored and re.fullmatch(_DURATION, message.strip()):
        duration = message
    else:
        return None
    minutes = sum(int(amount) * (60 if unit == "시간" else 1)
                  for amount, unit in re.findall(r"(\d+)\s*(시간|분)", duration))
    return minutes if 0 < minutes <= 1440 else None


def practice_request(message: str, previous: PracticeRequest | None = None) -> PracticeRequest | None:
    periods = list(_PERIOD.finditer(message))
    days = None
    if periods:
        period = periods[-1]
        days = 7 if period["week"] else int(period["amount"]) * (7 if period["unit"].startswith("주") else 1)
    minutes = time_limit(message)
    limit = minutes or (previous.daily_minutes if previous else None)
    plans = _PLAN.search(message) or days and _PLAN_TOPIC.search(message)
    plan_days = (previous.days or previous.plan_days) if previous else None
    completed = reported_progress(message)
    if not plans and plan_days and (completed is not None or asks_next_step(message) and previous.completed_through):
        completed = completed if completed is not None else previous.completed_through
        verify = completed >= plan_days or bool(_CHECK.search(message) and not asks_next_step(message))
        return PracticeRequest("task", daily_minutes=limit, verify=verify,
                               plan_days=plan_days, completed_through=completed)
    if _ONE_TASK.search(message) or not plans and _TODAY.search(message):
        return PracticeRequest("task", daily_minutes=limit, plan_days=plan_days,
                               completed_through=previous.completed_through if previous else None)
    if not plans and _CHECK.search(message):
        return PracticeRequest("task", daily_minutes=limit, verify=True, plan_days=plan_days,
                               completed_through=previous.completed_through if previous else None)
    if previous and (refers_to_practice(message) or not plans) and (
        minutes or _BARRIER.search(message) or _REVISION.search(message)
    ):
        return PracticeRequest("adjust", days or previous.days, limit)
    if plans and previous and _REVISION.search(message):
        return PracticeRequest("adjust", days or previous.days, limit)
    if plans:
        return PracticeRequest("plan", days, minutes)
    return None


def practice_schema(request: PracticeRequest | None, base: dict) -> dict:
    if not request:
        return base
    daily = bool(request.days and request.days <= _MAX_DAILY_ENTRIES)
    minutes = {"type": "INTEGER", "minimum": 0 if daily else 1, "maximum": request.daily_minutes or 1440}
    exercise = object_schema(task=TEXT, minutes=minutes, done=TEXT)
    if daily:
        schedule = {"type": "ARRAY", "minItems": request.days, "maxItems": request.days, "items": exercise}
        return object_schema(**base["properties"], schedule=schedule)
    if request.mode == "task" and not request.verify:
        return object_schema(**base["properties"], exercise=exercise)
    return base


def render_practice(result: dict, answer: str, request: PracticeRequest, schema: dict) -> str:
    def exercise(entry, *, day: int | None = None) -> str:
        if not isinstance(entry, dict):
            raise invalid
        task, minutes, done = (entry.get(key) for key in ("task", "minutes", "done"))
        minimum = 0 if day is not None else 1
        if (not isinstance(task, str) or not task.strip() or not isinstance(done, str) or not done.strip()
                or type(minutes) is not int or not minimum <= minutes <= (request.daily_minutes or 1440)
                or minutes == 0 and not _REST.search(task)):
            raise invalid
        heading = f"{day}일차 · {minutes}분" if day else f"오늘 할 일 · 약 {minutes}분"
        rest = "**휴식일** " if minutes == 0 else ""
        return f"**{heading}**\n{rest}{task.strip()}\n**완료 기준** {done.strip()}"

    invalid = ModelInvalidResponse("학습 계획의 일정이나 실습 내용을 확인할 수 없어요. 다시 시도해 주세요.",
                                   operation="consultation", reason="practice_schema")
    if "schedule" in schema["properties"]:
        schedule = result.get("schedule")
        if not isinstance(schedule, list) or len(schedule) != request.days:
            raise invalid
        return "\n\n".join([answer, *(exercise(entry, day=day) for day, entry in enumerate(schedule, start=1))])
    if "exercise" in schema["properties"]:
        return f"{answer}\n\n{exercise(result.get('exercise'))}"
    return answer
