"""Small, shared formatting rules for Korean chat replies."""

import re
from collections.abc import Sequence

_SENTENCE_BREAK = re.compile(r"(?<=[.!?。？！])\s+")
_FOLLOWUP = re.compile(r"^\s*(?:그럼|그러면|그중|그다음|그 다음)(?:\s|,)")
_FILLER = re.compile(
    r"(?:더\s*)?(?:궁금한\s*(?:점|것)이\s*(?:있으신가요|있나요)|"
    r"궁금한\s*(?:점|것)이\s*있으면\s*(?:편하게\s*)?(?:물어봐|말씀해)\s*주세요)[.!?？]*|"
    r"(?:정말\s+)?(?:훌륭한|멋진)\s*(?:첫걸음|출발점)이\s*(?:된답니다|됩니다|돼요|될\s*거예요)[.!]*"
)
_INTERNAL_LINE = re.compile(
    r"^\s*(?:[-*>#`]\s*)*(?:(?:stage|factIds?|skillId|jobId|provenance)[`*]*\s*[:=]|"
    r"(?:내부\s*ID|일반\s*학습\s*조언)[`*]*\s*(?:[:：=]|$))", re.I
)
_ADVICE_LABEL = re.compile(r"^\s*(?:[-*>#]\s*)*일반\s*학습\s*조언\**\s*[:：]\s*")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_PRACTICE_HEADING = re.compile(r"^\*\*(?:\d+일차|오늘 할 일) · ")
_TONE = {
    "하답니다": "해요", "한답니다": "해요", "된답니다": "돼요", "있답니다": "있어요",
    "없답니다": "없어요", "좋답니다": "좋아요", "많답니다": "많아요", "같답니다": "같아요",
    "쉽답니다": "쉬워요", "어렵답니다": "어려워요", "이랍니다": "이에요", "거랍니다": "거예요",
}
_TONE_ENDING = re.compile(r"(?:" + "|".join(_TONE) + r")(?=[.!?。？！*]*$)")
_PRAISE = re.compile(r"(?:훌륭한|멋진)\s*(?=(?:첫걸음|출발점)이\s*(?:된답니다|됩니다|돼요|될\s*거예요)[.!*]*$)")
_ASK_INPUT = re.compile(
    r"(?:알려|말해|말씀해)\s*(?:주세요|주시겠어요|(?:주실|줄)\s*수\s*있(?:나요|을까요)|주실래요)[.?？]*$"
)
_QUESTION_ENDING = re.compile(r"(?:있으신가요|있나요|있으세요|있으신지)$")
_INTEREST_QUESTION = re.compile(
    r"(?:(?:어떤|어느|무슨)(?:분야|주제)(?:에|가)?(?:관심|흥미)(?:이|가)?|"
    r"(?:관심|흥미)(?:이|가)?있는(?:분야|주제)(?:을|를|가|는)?)"
)
_REQUESTED_QUESTIONS = re.compile(
    r"(?:질문|문항).{0,20}(?:예시|목록|다시|만들|뽑아|적어|추천|보여)|"
    r"(?:예시|목록|다시).{0,16}(?:질문|문항)"
)


def particle(value: str, consonant: str, vowel: str) -> str:
    last = value[-1:]
    if "가" <= last <= "힣":
        ending = (ord(last) - ord("가")) % 28 != 0
    else:
        ending = last.lower() in {"b", "l", "m", "n", "1", "3", "6", "7", "8", "0"}
    return consonant if ending else vowel


def korean_list(values: list[str]) -> str:
    if len(values) < 2:
        return "".join(values)
    if len(values) == 2:
        first, second = values
        return f"{first}{particle(first, '과', '와')} {second}"
    return ", ".join(values)


def public_consultation(text: str, labels: dict[str, str]) -> str:
    ids = [re.escape(key) for key, name in labels.items() if key.casefold() != name.casefold() and "-" in key]
    ids.append(r"mock-[a-z0-9-]+")
    pattern = re.compile(r"(?<![\w-])(?:" + "|".join(ids) + r")(?![a-z0-9-])", re.I)
    names = {key.casefold(): name for key, name in labels.items()}

    def name_for_id(match: re.Match) -> str:
        return names.get(match[0].casefold(), "선택한 항목")

    lines = []
    for line in text.splitlines():
        line = _ADVICE_LABEL.sub("", line)
        if _INTERNAL_LINE.match(line):
            continue
        lines.append(pattern.sub(name_for_id, line))
    return "\n".join(lines).strip()


def _question_key(sentence: str) -> str:
    if not (sentence.endswith(("?", "？")) or _ASK_INPUT.search(sentence)):
        return ""
    stem = _ASK_INPUT.sub("", sentence).rstrip(".!?？")
    stem = re.sub(r"\s+", "", _QUESTION_ENDING.sub("", stem)).removeprefix("혹시")
    return "관심 분야" if _INTEREST_QUESTION.fullmatch(stem) else stem.casefold()


def concise_consultation(answer: str, message: str, previous_answer: str = "", *,
                         recent_answers: Sequence[str] = (), preserve_steps: bool = False) -> str:
    asked = set()
    if not _REQUESTED_QUESTIONS.search(message):
        for reply in recent_answers:
            paragraphs = reply.rstrip().split("\n\n")
            edges = paragraphs[0].splitlines()[-1:] + paragraphs[-1].splitlines()[-1:]
            asked.update(_question_key(sentence.strip(" -*#`")) for line in edges
                         for sentence in _SENTENCE_BREAK.split(line))
        asked.discard("")

    def render(omit: set[str]) -> str:
        seen = set(omit)
        lines = []
        fence = ""
        schedule = False
        for line in answer.splitlines():
            schedule = schedule or bool(preserve_steps and _PRACTICE_HEADING.match(line))
            if schedule:
                lines.append(line)
                continue
            marker = _FENCE.match(line)
            if marker:
                if not fence:
                    fence = marker[1]
                elif marker[1].startswith(fence) and line.strip() == marker[1]:
                    fence = ""
                lines.append(line)
                continue
            if fence:
                lines.append(line)
                continue
            kept = []
            for sentence in _SENTENCE_BREAK.split(line.rstrip()):
                key = sentence.strip(" -*#`")
                if key and (preserve_steps or key not in seen) and not _FILLER.fullmatch(key) and _question_key(key) not in asked:
                    seen.add(key)
                    sentence = _TONE_ENDING.sub(lambda match: _TONE[match[0]], _PRAISE.sub("", sentence))
                    kept.append(sentence)
            lines.append(" ".join(kept))
        return "\n".join(lines).strip()

    if previous_answer and not preserve_steps and _FOLLOWUP.match(message):
        previous = {sentence.strip(" -*#`*") for line in previous_answer.splitlines()
                    for sentence in _SENTENCE_BREAK.split(line.strip())}
        shortened = render(previous)
        if shortened:
            return shortened
    return render(set())


def draft_note(note: str | None, *, repeating: bool) -> str:
    """Show a new question when it can help the user improve the draft."""
    if not note:
        return ""
    if repeating and note.endswith("?"):
        return " ".join(_SENTENCE_BREAK.split(note)[:-1])
    return note
