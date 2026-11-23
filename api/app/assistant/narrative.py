"""Compose application prose from evidence selected by ID."""
import re
from dataclasses import dataclass, replace

from .contracts import Fact, NarrativeContext, NarrativeOptions
from .privacy import redact
from .skill_context import mentioned

_LENGTH = re.compile(r"(?<!\d)(\d{1,5})\s*자\s*(이상|이하|이내|미만|내외|정도)?")
_RANGE = re.compile(r"(?<!\d)(\d{1,5})\s*(?:자\s*)?[~–-]\s*(\d{1,5})\s*자")
_ROLE = re.compile(r"([가-힣A-Za-z][가-힣A-Za-z0-9 +./-]{1,40}?)\s*(?:직무|포지션|에 지원)")
_CHANGE_ROLE = re.compile(
    r"(?:지원|희망|목표)\s*(?:직무|포지션)(?:을|를|은|는)?\s*"
    r"([가-힣A-Za-z][가-힣A-Za-z0-9 +./-]{1,40}?)\s*(?:직무\s*)?(?:으?로)\s*(?:바꿔|바꾸|변경|수정|전환)"
)
_ROLE_PREFIX = re.compile(
    r"[.!?\n]|(?:나는|저는|제가|이번엔|이번에는|이번에|아까|방금|앞서|이전에?|이제|그럼|그리고|대신|바탕으로|"
    r"기반으로|지원용으로|제출용으로|지원동기를|자기소개서를)\s+"
)
_UNNAMED_ROLE = re.compile(r"^(?:(?:지금까지|전에)\s*)?(?:(?:말한|기존|현재|희망|목표|지원|그|이)\s*)+$")
_SHORTER = re.compile(r"짧게|간결|요약|줄여|줄이|축약|축소|단축|압축")
_LONGER = re.compile(r"길게|구체적으로|늘려|자세히")
_DRAFT_INTENT = re.compile(r"작성|써\s*줘|수정|바꿔|지원동기|초안|자기소개서|자소서|문항|중심|위주")
_SOURCE_RESTRICTION = re.compile(
    r"말하지\s*않|제공하지\s*않|확인되지\s*않|제외|빼\s*줘|(?:허위|가짜|없는)\s*(?:경력|경험|프로젝트|이력|성과|수상)|"
    r"(?:경력|경험|프로젝트)(?:은|는|이|가|을|를)?\s*(?:없[이어음고는지다]|없습니다|말고)|지어내|"
    r"(?:넣|만들|만들어\s*내|꾸미|쓰|적|추가하)지\s*(?:마|않)"
)
_SOURCE_CLAUSES = re.compile(r"[.!?。？！\n,，()]|(?<=말고)\s+|(?<=하되)\s+")
_EXPERIENCE_BASIS = re.compile(r"(?:경험|사례)(?:을|를)?\s*(?:중심|위주|근거|바탕|기반|으로)")
WORK_EXPERIENCE = {"project", "job", "internship", "activity", "training", "award"}
_EXPERIENCE = WORK_EXPERIENCE | {"skill", "certification"}


@dataclass(frozen=True)
class Brief:
    role: str | None
    question: str
    minimum: int
    maximum: int
    concise: bool
    valid: bool

    def context(self) -> NarrativeContext | None:
        if self.valid:
            return NarrativeContext(target_role=self.role, question=self.question,
                                    min_characters=self.minimum, max_characters=self.maximum)
        return None


def draft_topics(topic: str, previous_topic: str) -> list[str]:
    lines = [topic, *reversed(previous_topic.splitlines())]
    return [line for line in lines if _DRAFT_INTENT.search(line)] or lines


def restricts_sources(text: str) -> bool:
    return bool(_SOURCE_RESTRICTION.search(text))


def _affirmative_clauses(text: str) -> list[str]:
    return [clause for clause in _SOURCE_CLAUSES.split(text) if not restricts_sources(clause)]


def experience_focus(topic: str, previous_topic: str) -> set[str]:
    for text in draft_topics(topic, previous_topic):
        focus = " ".join(_affirmative_clauses(text))
        kinds = set()
        for word, matched in (("인턴", {"internship"}), ("경력", {"job", "internship"}), ("프로젝트", {"project"})):
            if word in focus:
                kinds.update(matched)
        if kinds:
            return kinds
        if _EXPERIENCE_BASIS.search(focus):
            return WORK_EXPERIENCE
    return set()


def _target_role(text: str) -> str | None:
    change = _CHANGE_ROLE.search(text)
    if change:
        return change[1].strip()
    for match in reversed(list(_ROLE.finditer(text))):
        role = _ROLE_PREFIX.split(match[1])[-1].strip()
        if role and not _UNNAMED_ROLE.fullmatch(role):
            return role
    return None


def _length_limits(text: str, previous: tuple[int, int]) -> tuple[int, int]:
    interval = _RANGE.search(text)
    if interval:
        return int(interval[1]), int(interval[2])
    matches = list(_LENGTH.finditer(text))
    if not matches:
        return previous
    low, high = 1, 3900
    for length, qualifier in (match.groups() for match in matches):
        count = int(length)
        if qualifier == "이상":
            low = count
        elif qualifier in ("내외", "정도"):
            low, high = round(count * 0.9), round(count * 1.1)
        else:
            high = count - int(qualifier == "미만")
    return low, high


def brief(topic: str, options: NarrativeOptions, previous_topic: str = "",
          previous_context: NarrativeContext | None = None) -> Brief:
    earlier = previous_topic.splitlines()
    role = options.target_role or _target_role(topic)
    if not role:
        role = previous_context.target_role if previous_context else next(
            (target for text in reversed(earlier) if (target := _target_role(text))), None,
        )
    limits = (1, 3900)
    if previous_context:
        limits = (previous_context.min_characters or 1, previous_context.max_characters or 3900)
    else:
        for text in earlier:
            limits = _length_limits(text, limits)
    low, high = _length_limits(topic, limits)
    low = options.min_characters or low
    high = options.max_characters or high
    question = previous_context.question if previous_context else "introduction"
    topics = [topic] if previous_context else draft_topics(topic, previous_topic)
    for text in topics:
        if "지원동기" in text.replace(" ", ""):
            question = "motivation"
        elif re.search(r"강점|역량", text):
            question = "strengths"
        elif any(re.search(r"경험|프로젝트|성과", clause) for clause in _affirmative_clauses(text)) and not _SHORTER.search(text):
            question = "experience"
        else:
            continue
        break
    concise = bool(_SHORTER.search(topic)) and not _LONGER.search(topic)
    maximum, minimum = min(high, 3900), max(low, 1)
    return Brief(redact(role) if role else None, question, minimum, maximum, concise, minimum <= maximum)


def for_revision(requirements: Brief, topic: str, previous_text: str | None) -> Brief:
    lines = previous_text.splitlines() if previous_text else []
    if not requirements.concise or len(lines) < 2 or not lines[0].startswith("[AI 초안]") or _LENGTH.search(topic):
        return requirements
    previous_length = len(lines[1])
    limit = min(requirements.maximum, max(requirements.minimum, previous_length - 1))
    return replace(requirements, maximum=limit)


def applicable_experience(fact: Fact) -> bool:
    return fact.kind in _EXPERIENCE and fact.progress not in ("preparing", "not_held")


def draft_interest(requirements: Brief, background: list[Fact], topic: str) -> Fact | None:
    interests = [fact for fact in background if fact.kind == "interest"]
    if not interests:
        return None
    if re.search(r"관심|흥미", topic):
        named = next((fact for fact in interests if mentioned(fact.value, topic)), None)
        if named:
            return named
    key = re.sub(r"\s+", "", requirements.role or "").casefold()
    for fact in interests:
        value = re.sub(r"\s+", "", fact.value).casefold()
        if key and (value in key or key in value):
            return fact
    return interests[0] if not key or re.search(r"관심|흥미", topic) else None


def _interest_opening(role: str | None, interest: Fact) -> tuple[str, ...]:
    if not role:
        return (f"{interest.value}에 대한 관심을 실무 역량으로 발전시키고자 합니다.",)
    return (f"{interest.value}에 대한 관심을 실제 업무에 연결하고자 {role} 직무에 지원합니다.",
            f"{interest.value}에 관심이 있어 {role} 직무에 지원합니다.")


_MOTIVATION_PLAN = (
    "업무를 맡으면 과제의 목적과 판단 기준을 먼저 파악하고, 그에 맞는 자료를 정리하겠습니다.",
    "결과를 공유할 때에는 판단의 근거와 추가 확인이 필요한 부분을 함께 전달해 다음 의사결정에 보탬이 되겠습니다.",
)


def _sentence(text: str) -> str:
    text = text.strip().rstrip(".!?。")
    if text.endswith(("담당", "진행", "구현", "개발", "작성", "수행", "분석", "수집", "개선", "참여", "정리", "완료")):
        return text + "했습니다."
    if text.endswith(("습니다", "입니다", "합니다")):
        return text + "."
    if text.endswith(("했어", "했어요", "했음")):
        return re.sub(r"했(?:어요|어|음)$", "했습니다.", text)
    return f"구체적인 활동은 {text}입니다."


def _experience(fact: Fact) -> str:
    if fact.kind == "project":
        return f"\"{fact.value}\" 프로젝트에 참여했습니다."
    if fact.kind == "internship":
        return f"\"{fact.value}\"에서 인턴 경험을 쌓았습니다."
    if fact.kind == "job":
        return f"\"{fact.value}\" 근무 경험이 있습니다."
    if fact.kind == "training":
        return f"\"{fact.value}\" 교육을 받았습니다."
    if fact.kind == "skill":
        return f"\"{fact.value}\" 학습 경험이 있습니다."
    if fact.kind == "certification":
        return f"\"{fact.value}\" 자격을 취득했습니다."
    if fact.kind == "award":
        return f"\"{fact.value}\" 수상 경험이 있습니다."
    return f"\"{fact.value}\" 활동에 참여했습니다."


def compose(requirements: Brief, sources: list[Fact], fixture: bool, *,
            preparation: Fact | None = None, interest: Fact | None = None) -> tuple[str | None, list[Fact]]:
    if not requirements.valid:
        return None, []
    role = requirements.role
    closing = ""
    if role:
        if requirements.question == "motivation":
            closing = f"이 경험을 바탕으로 {role} 업무에 지원하고자 합니다."
        elif requirements.question == "strengths":
            closing = f"{role} 업무에서도 이 경험을 활용하고 싶습니다."
    used = [preparation] if preparation else []
    sentences = [f"{preparation.value} 자격증을 준비 중입니다."] if preparation else []
    if preparation and requirements.question == "motivation" and role:
        closing = f"{role} 업무에 지원합니다."
    openings = _interest_opening(role, interest) if interest and requirements.question == "motivation" else ()
    reserved = openings[-1] if openings else closing if preparation else ""
    for fact in sources:
        description = _experience(fact)
        detail = _sentence(fact.detail) if fact.detail else ""
        if fact.kind == "project" and detail and not detail.startswith("구체적인 활동은"):
            with_detail = f"\"{fact.value}\" 프로젝트에서 {detail}"
        else:
            with_detail = f"{description} {detail}" if detail else description
        for sentence in dict.fromkeys((with_detail, description)):
            if len(" ".join(filter(None, [*sentences, sentence, reserved]))) <= requirements.maximum:
                used.append(fact)
                sentences.append(sentence)
                break
        if requirements.concise and fact in used:
            break
    if sentences and interest:
        for opening in openings:
            if len(" ".join([opening, *sentences])) <= requirements.maximum:
                sentences.insert(0, opening)
                used.insert(0, interest)
                closing = ""
                break
    if sentences and closing and len(" ".join([*sentences, closing])) <= requirements.maximum:
        sentences.append(closing)
    if requirements.question == "motivation" and sentences and not requirements.concise:
        for sentence in _MOTIVATION_PLAN:
            if len(" ".join([*sentences, sentence])) <= requirements.maximum:
                sentences.append(sentence)
    body = " ".join(sentences)
    if not used or not requirements.minimum <= len(body) <= requirements.maximum:
        return None, []
    marker = "[AI 초안] [가상 예시]" if fixture else "[AI 초안]"
    return f"{marker}\n{body}", used


def limited_draft(requirements: Brief, background: list[Fact], preparation: Fact | None,
                  interest: Fact | None) -> tuple[str | None, list[Fact]]:
    role = requirements.role
    department = next((fact for fact in background if fact.kind == "department"), None)
    parts: list[tuple[tuple[str, ...], Fact | None]] = []
    required = f"{preparation.value} 자격증을 준비 중입니다." if preparation else ""
    if requirements.question == "introduction" and department:
        parts.append(((f"저는 {department.value} 학생입니다.",), department))
    if requirements.question == "motivation" and role:
        opening = f"{role} 직무에 지원합니다."
        if interest:
            parts.append((_interest_opening(role, interest), interest))
        else:
            parts.append(((f"{role} 직무에서 문제를 파악하고 근거를 바탕으로 해결하는 일에 기여하고자 지원합니다.",
                           opening), None))
    elif interest:
        parts.append((_interest_opening(None, interest), interest))
    elif requirements.question == "motivation":
        parts.append((("지원 직무에서 맡은 과제의 목적을 이해하고 해결 과정에 기여하고자 합니다.",), None))
    if preparation:
        expanded = f"현재 {preparation.value} 자격증을 준비하며 관련 기초를 실무 과제에 적용할 방법을 익히고자 합니다."
        parts.append(((required,) if requirements.concise else (expanded, required), preparation))
    if requirements.question == "motivation" and not requirements.concise:
        parts.extend(((sentence,), None) for sentence in _MOTIVATION_PLAN)
    if not parts:
        parts.append((("직무에 필요한 기본기를 쌓고, 배운 내용을 실무에 적용하고자 합니다.",), None))
    sentences, sources = [], []
    for variants, fact in parts:
        reserved = required if preparation and preparation not in sources and fact != preparation else ""
        for sentence in variants:
            if len(" ".join(filter(None, [*sentences, sentence, reserved]))) <= requirements.maximum:
                sentences.append(sentence)
                if fact:
                    sources.append(fact)
                break
    body = " ".join(sentences)
    if (preparation and preparation not in sources) or not requirements.minimum <= len(body) <= requirements.maximum:
        return None, []
    return "[AI 초안]\n" + body, sources
