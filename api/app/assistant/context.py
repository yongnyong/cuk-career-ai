"""Resolve screen IDs and evaluate notice conditions before consulting the model."""
import re
from datetime import datetime, timedelta, timezone

from .contracts import AssessedOpportunity, Condition, ConditionResult, Fact, Opportunity, Screen, Turn
from .memory import identity
from .privacy import catalog_text
from .repository import CareerData

SEOUL = timezone(timedelta(hours=9))
_VERDICTS = {"pass": "충족", "fail": "미충족", "check": "확인 필요"}
_OPPORTUNITY = re.compile(r"공고|인턴십|지원\s*(?:할|자격|조건|서류|마감|방법)|모집|채용|(?:취업|인턴)\s*추천|창업\s*(?:지원|사업)")
_FOLLOW_UP = re.compile(r"마감|서류|조건|자격|신청|어떻게\s*준비|그\s*(?:공고|회사|인턴십|사업)|이\s*공고")
_SCREEN_REFERENCE = re.compile(r"이거|이건|여기|이걸|혜택|지원금|뭘\s*하|내용|어떻게\s*해")


def assess_condition(condition: Condition, facts: list[Fact]) -> ConditionResult:
    relevant = [fact for fact in facts if fact.kind == condition.kind]
    if condition.kind == "other" or not relevant:
        return ConditionResult(label=condition.label, verdict="check", reason="확인할 학생 정보 또는 판정 기준이 부족해요.")

    if condition.kind == "certification":
        eligible = [fact for fact in relevant if fact.source == "official" and fact.progress not in ("preparing", "not_held")]
    else:
        eligible = [fact for fact in relevant if fact.source in ("system", "official")
                    and fact.progress not in ("preparing", "not_held")]

    if condition.kind == "grade" and condition.minimum is not None:
        grades = [int(fact.value) for fact in eligible if re.fullmatch(r"[1-9][0-9]?", fact.value)]
        if len(set(grades)) == 1:
            passed = grades[0] >= condition.minimum
            return ConditionResult(label=condition.label, verdict="pass" if passed else "fail", reason=f"등록된 학년은 {grades[0]}학년이에요.")
    elif condition.values:
        expected = {identity(value) for value in condition.values}
        actual = {identity(fact.value) for fact in eligible}
        if len(actual) > 1 and condition.kind in ("department", "status", "grade"):
            return ConditionResult(label=condition.label, verdict="check", reason="등록된 값이 서로 달라 확인이 필요해요.")
        if expected & actual:
            return ConditionResult(label=condition.label, verdict="pass", reason="등록 또는 공식 확인된 정보가 조건과 일치해요.")
        if eligible and condition.kind in ("department", "status", "grade"):
            return ConditionResult(label=condition.label, verdict="fail", reason="등록된 정보가 명시된 조건과 일치하지 않아요.")
        if any(identity(fact.value) in expected for fact in relevant):
            return ConditionResult(label=condition.label, verdict="check", reason="사용자 진술 또는 미검증 기록의 공식 확인이 필요해요.")
    return ConditionResult(label=condition.label, verdict="check", reason="충족 여부를 확인할 수 있는 기록이 부족해요.")


def assess(opportunity: Opportunity, facts: list[Fact], now: datetime, fixture_ids: set[str] = frozenset()) -> AssessedOpportunity:
    applicable = facts if opportunity.mock else [fact for fact in facts if fact.id not in fixture_ids]
    conditions = [assess_condition(condition, applicable) for condition in opportunity.conditions]
    for condition in conditions:
        condition.label = catalog_text(condition.label)
    if opportunity.mock and fixture_ids:
        for condition in conditions:
            if condition.verdict != "check":
                condition.reason = "가상 학생 데이터 기준 · " + condition.reason
    return AssessedOpportunity(
        id=opportunity.id, type=opportunity.type, title=catalog_text(opportunity.title),
        organization=catalog_text(opportunity.organization), description=catalog_text(opportunity.description),
        deadline=opportunity.deadline, open=opportunity.deadline > now, mock=opportunity.mock,
        documents=[catalog_text(value) for value in opportunity.documents],
        source_url=opportunity.source_url, version=opportunity.version,
        conditions=conditions,
    )


def select_opportunities(data: CareerData, screen: Screen, message: str, facts: list[Fact],
                         previous: Turn | None, now: datetime, fixture_ids: set[str] = frozenset(),
                         ) -> tuple[list[AssessedOpportunity], str | None]:
    opportunity_question = _OPPORTUNITY.search(message)
    skill_selected = screen.page == "tree" and bool(screen.job_id or screen.skill_id)
    if skill_selected and not opportunity_question:
        return [], None
    selected = screen.opportunity_id
    focus_type = "startup" if "창업" in message else "employment" if re.search("채용|취업|인턴", message) else None
    if not selected and previous and not skill_selected and not focus_type and _FOLLOW_UP.search(message):
        selected = previous.topic_opportunity_id
    if selected:
        opportunity = data.get_opportunity(selected)
        if not opportunity:
            return [], "unknown_opportunity"
        if focus_type or any(pattern.search(message) for pattern in (_OPPORTUNITY, _FOLLOW_UP, _SCREEN_REFERENCE)):
            return [assess(opportunity, facts, now, fixture_ids)], None
        return [], None
    if not opportunity_question:
        return [], None

    if not focus_type:
        goals = [fact.value for fact in facts if fact.kind == "goal"]
        if goals:
            active_goal = goals[-1]
            focus_type = "startup" if "창업" in active_goal else "employment" if re.search("취업|개발|인턴", active_goal) else None

    candidates = (
        assess(item, facts, now, fixture_ids) for item in data.list_opportunities()
        if item.deadline > now and (not focus_type or focus_type == item.type)
    )
    eligible = [item for item in candidates if all(result.verdict != "fail" for result in item.conditions)]
    interests = {identity(fact.value) for fact in facts if fact.kind in ("interest", "skill", "goal")}

    def score(item):
        text = identity(item.title + " " + item.description)
        return (-sum(r.verdict == "pass" for r in item.conditions),
                -sum(len(term) >= 2 and term in text for term in interests), item.deadline, item.id)

    eligible.sort(key=score)
    return eligible[:3], None if eligible else "no_matching_opportunity"


def describe_opportunity(item: AssessedOpportunity, include_description: bool = False) -> str:
    heading = f"{'[가상 공고] ' if item.mock else ''}{item.title} · {item.organization}"
    deadline = item.deadline.astimezone(SEOUL).strftime("%Y-%m-%d %H:%M KST")
    lines = [heading, f"마감 {deadline} · {'접수 가능 기간' if item.open else '마감 지남'}"]
    if include_description:
        lines.append("공고 설명 " + item.description)
    lines.extend(f"- {condition.label} · {_VERDICTS[condition.verdict]}. {condition.reason}" for condition in item.conditions)
    lines.append("필요 서류 " + (", ".join(item.documents) if item.documents else "공고 원문에서 확인 필요"))
    if item.source_url:
        lines.append("원문 " + item.source_url)
    return "\n".join(lines)
