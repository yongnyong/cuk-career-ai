"""Render explicit personal-memory queries from saved records and their sources."""

import re

from .contracts import EXPERIENCE_KINDS, Fact, Profile
from .memory import identity
from .privacy import provenance, shareable
from .response_style import korean_list, particle
from .skill_context import mentioned

_OWN_RECORD = re.compile(
    r"(?:내가|제가|나는|저는)\s*(?:(?:아까|전에|직접|이전에)\s*)*(?:말|알려|입력|언급|저장|이야기|진술)|"
    r"직접\s*(?:말했|말한|알려|입력했|진술한)|(?:내|제)\s*(?:장기\s*)?(?:기억|저장된\s*기록)|기억해\s*둔"
)
_LOOKUP = re.compile(r"알려|기억나|뭐|무엇|어떤|보여|확인|정리")
_ADVICE = re.compile(
    r"추천|어울|(?:실습|연습|공부|활용)\s*(?:방법|순서)|어떻게\s*(?:학습|공부|배우|실습|활용)|지원\s*조건"
)
_UNCONFIRMED_ACK = re.compile(
    r"기억\s*(?:했|할게|하겠|해\s*(?:둘|뒀|두었|두겠|드릴))|"
    r"(?:말씀하신|알려주신|해당|이)\s*(?:내용|정보).{0,30}(?:저장|기록)\s*"
    r"(?:했|할게|하겠|해\s*(?:둘|뒀|두었|두겠|드릴))"
)
_TOPICS = {
    "skill": (r"실력|숙련도|역량|스킬|기술\s*(?:수준|기억)|어느\s*정도|기초", "기술 수준"),
    "project": (r"프로젝트|포트폴리오", "프로젝트 경험"),
    "internship": (r"인턴", "인턴 경험"),
    "job": (r"경력|근무", "근무 경험"),
    "interest": (r"관심|흥미", "관심 분야"),
    "goal": (r"목표", "진로 목표"),
    "study_time": (r"공부\s*시간|학습\s*시간", "학습 가능 시간"),
}
_PROGRESS = {
    "preparing": "준비 중이라고 말씀하셨어요.",
    "completed": "완료했다고 말씀하셨어요.",
    "beginner": "기초 수준이라고 말씀하셨어요.",
    "intermediate": "중급 수준이라고 말씀하셨어요.",
}
_SKILL_TARGET = re.compile(
    r"(?<![\w.+#-])(?P<name>[가-힣A-Za-z0-9][가-힣A-Za-z0-9.+#_-]*?)"
    r"(?:의)?\s+(?:실력|숙련도|역량|스킬|기술\s*수준|수준)(?=[을를과와은는이가의\s,.?!]|$)"
)
_GENERIC_SKILL_MODIFIER = re.compile(
    r"(?:말했\w*|말한|알려\w*|저장\w*|언급\w*|입력\w*|진술\w*|기억\w*|이야기\w*|배운|공부한|"
    r"내|제|현재|지금|전반적인|어떤|무슨|보유\w*|기술|스킬|전체|학습\w*|확인\w*|등록\w*)"
)


def asks_for_user_memory(message: str) -> bool:
    return bool(_OWN_RECORD.search(message) and _LOOKUP.search(message) and not _ADVICE.search(message))


def without_unconfirmed_ack(answer: str) -> str:
    if not _UNCONFIRMED_ACK.search(answer):
        return answer
    lines = []
    for line in answer.splitlines():
        sentences = re.split(r"(?<=[.!?。])\s+", line)
        lines.append(" ".join(sentence for sentence in sentences if not _UNCONFIRMED_ACK.search(sentence)))
    return "\n".join(lines).strip()


def describe_user_fact(fact: Fact) -> str:
    subject = f"{fact.value}{particle(fact.value, '은', '는')}"
    if fact.progress == "not_held":
        wording = "해 본 경험이 없다고 말씀하셨어요." if fact.kind in EXPERIENCE_KINDS else "보유하지 않았다고 말씀하셨어요."
    elif fact.kind == "skill" and fact.detail and fact.progress in ("beginner", "intermediate"):
        if fact.detail.endswith("알고"):
            return f"{fact.value} {fact.detail} 있다고 말씀하셨어요."
        else:
            wording = f"“{fact.detail.rstrip('.')}”라고 말씀하셨어요."
    elif fact.kind in EXPERIENCE_KINDS:
        wording = "직접 경험했다고 말씀하셨어요."
    elif fact.kind == "interest":
        return f"{fact.value}에 관심이 있다고 말씀하셨어요."
    else:
        wording = _PROGRESS.get(fact.progress, "직접 말씀하신 내용이에요.")
    return f"{subject} {wording}"


def _matching(facts: list[Fact], message: str) -> list[Fact]:
    named = [fact for fact in facts if mentioned(fact.value, message)]
    return (named or facts)[:5]


def user_memory_answer(message: str, profile: Profile, memory: list[Fact]) -> str:
    kinds = [kind for kind, (pattern, _) in _TOPICS.items() if re.search(pattern, message)]
    targets = [match["name"] for match in _SKILL_TARGET.finditer(message)
               if not _GENERIC_SKILL_MODIFIER.fullmatch(match["name"])] if "skill" in kinds else []

    def relevant(fact: Fact) -> bool:
        return (shareable(fact) and fact.kind != "certification" and (
            fact.kind != "skill" or not targets or any(
                identity(name) == identity(fact.value) or mentioned(name, fact.value) for name in targets
            )
        ))

    direct = [fact for fact in memory if relevant(fact)]
    lines = []
    if kinds:
        for kind in kinds:
            matches = _matching([fact for fact in direct if fact.kind == kind], message)
            lines.extend(describe_user_fact(item) for item in matches)
            if not matches:
                topic = f"{korean_list(targets)} 실력" if kind == "skill" and targets else _TOPICS[kind][1]
                lines.append(f"{topic}에 관해 직접 말씀하신 내용은 저장돼 있지 않아요.")
    else:
        matches = _matching(direct, message)
        lines.extend(describe_user_fact(item) for item in matches)
        if not matches:
            lines.append("직접 말씀하신 내용 중 현재 저장된 기록이 없어요.")

    sections = [" ".join(lines)]
    if re.search(r"가상|공식|등록|출처|구분", message):
        related = [fact for fact in profile.facts if relevant(fact)
                   and (not kinds or fact.kind in kinds)]
        for source, description in (
            ("verified", "공식 확인 기록에는 {values}{subject} 있어요."),
            ("registered", "프로필에 등록된 항목에는 {values}{subject} 있어요."),
            ("fixture", "가상 사용자 데이터에는 상담용 예시로 {values}{subject} 들어 있어요."),
        ):
            entries = [fact for fact in related if provenance(fact, profile.mock) == source]
            if not entries:
                continue
            values = [fact.value for fact in _matching(entries, message)]
            sections.append(description.format(values=korean_list(values), subject=particle(values[-1], "이", "가")))
    return "\n\n".join(sections)
