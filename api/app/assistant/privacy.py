"""Minimum filtering shared by assistant model calls and persisted turns."""
import re
from collections.abc import Iterable

from .contracts import Fact

_PATTERNS = (
    r"(?<!\d)01[016789][\s.-]?\d{3,4}[\s.-]?\d{4}(?!\d)",
    r"(?<!\d)\d{6}[\s.-]?[1-8]\d{6}(?!\d)",
    r"(?<!\d)20\d{7}(?!\d)",
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    r"(?:이름|성명|주소|학번|생년월일|출생\s*연도|거주(?:지|지역)|창업\s*단계)\s*(?::|은|는|이에요|입니다)\s*[^,\n.!?]{1,80}",
    r"(?:TOEIC|TOEFL|OPIc|JLPT|토익|토플|오픽|학점|성적|어학 점수)\s*(?:은|는|이|:)?\s*(?:\d+(?:\.\d+)?(?:\s*(?:점|등급))?|(?:AL|IH|IM[123]?|IL|N[1-5])\b)",
)
_PRIVATE_TEXT = re.compile("|".join(f"(?:{value})" for value in _PATTERNS), re.IGNORECASE)
_SECRET_MARK = "[비밀정보 삭제]"
_SECRET_FIELD = re.compile(
    r"(?<![\w-])(?:x-)?(?:[A-Z][A-Z0-9]*_)*(?:api[ _-]*key|client[ _-]*secret|private[ _-]*key|"
    r"(?:access|refresh|auth)[ _-]*token|password|passwd|secret(?:[ _-]*key)?|"
    r"API\s*키|(?:접근|액세스|인증|갱신)\s*토큰|(?:클라이언트\s*)?시크릿|비밀\s*키|비밀번호)"
    r"[\"'`]?\s*(?P<separator>[:=]|(?:은|는|이|가)\s+)\s*"
    r"(?:(?P<quote>[\"'`“‘])(?P<quoted>[^\"'`”’\r\n]{1,2000})[\"'`”’]|"
    r"(?P<bare>[A-Za-z0-9_~+/.$%!=@:\-][A-Za-z0-9_~+/.$%!=@:\-]*))",
    re.I,
)
_KEY_FORMAT = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[ \t]*\r?\n"
    r"(?:[A-Za-z0-9+/=]{16,}[ \t]*(?:\r?\n|$))+(?:-----END [A-Z0-9 ]*PRIVATE KEY-----)?|"
    r"(?<![A-Za-z0-9_-])(?:AIza[A-Za-z0-9_-]{35}|sk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}|"
    r"gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"(?:AKIA|ASIA)[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{16,}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})(?![A-Za-z0-9_-])|"
    r"\bauthorization[\"']?\s*[:=]\s*[\"']?(?:Bearer|Basic)\s+(?P<auth>[A-Za-z0-9._~+/=-]{6,})",
    re.I,
)


def secret_values(text: str) -> set[str]:
    """Recognize credentials without treating a bare discussion of keys as a value."""
    found = {match["auth"] or match[0] for match in _KEY_FORMAT.finditer(text)}
    for match in _SECRET_FIELD.finditer(text):
        value = match["quoted"] or (match["bare"] or "").rstrip(".!:")
        if not value.strip():
            continue
        assigned = match["separator"] in (":", "=") or bool(match["quote"])
        if assigned or (len(value) >= 8 and (not value.isalpha() or len(value) >= 24)) or value.isdigit():
            found.add(value)
    return found


def redact_secrets(text: str, *, known: Iterable[str] = ()) -> str:
    values = secret_values(text) | set(known)
    if not values:
        return text
    for value in sorted(values, key=len, reverse=True):
        # Short assigned values should only match complete tokens when repeated elsewhere.
        pattern = r"(?<![\w])" + re.escape(value) + r"(?![\w])" if len(value) < 8 else re.escape(value)
        text = re.sub(pattern, _SECRET_MARK, text)
    return text
_PERSONAL_NAME_PREFIX = re.compile(
    r"(?:^|[\s(])(?:내|제|나의|저의|본인의|사용자의?|학생의?|친구의?|사람의?)"
    r"(?:\s+실제)?[\s*_\x60]*$"
)
_OBJECT_NAME = re.compile(r"(?:프로젝트|스킬|기술|라이브러리|노드|예시|실습|예제|서비스)(?:의)?\s*$")
_OBJECT_DECLARATION = re.compile(r"^이름\s*(?::|은|는|이에요|입니다)\s*")
_CATALOG_INSTRUCTION = re.compile(
    r"(?:ignore|disregard|override)\b.{0,90}\b(?:instructions?|prompts?|rules?)|"
    r"(?:system|developer)\s*(?:prompt|message|instruction)\s*:|"
    r"(?:이전\s*(?:지시|규칙)|시스템\s*(?:지시|프롬프트)).{0,90}(?:무시|공개|출력|따르)",
    re.I | re.S,
)


def redact(text: str, *, object_names: tuple[str, ...] = ()) -> str:
    text = redact_secrets(text)
    # Protect only exact object labels already established in the conversation or catalog.
    # Scan the surrounding text separately so an object label cannot protect another name.
    labels = sorted({name.strip() for name in object_names if name.strip() and not _PRIVATE_TEXT.search(name)},
                    key=len, reverse=True)
    def hide(match):
        prefix = match.string[max(0, match.start() - 45):match.start()]
        declaration = _OBJECT_DECLARATION.match(match.group())
        if declaration and _OBJECT_NAME.search(prefix):
            offset = declaration.end()
            return match.group()[:offset] + _PRIVATE_TEXT.sub("[개인정보 삭제]", match.group()[offset:])
        return "[개인정보 삭제]"

    if not labels:
        return _PRIVATE_TEXT.sub(hide, text)
    separator = r"[ \t*_-]*"
    known = "|".join(separator.join(re.escape(char) for char in name if not char.isspace()) for name in labels)
    declaration = re.compile(
        rf"""이름\s*(?::|은|는|이에요|입니다)\s*["'“‘*_\x60]*\s*(?:{known})\s*["'”’*_\x60]*"""
        r"(?=$|[\s,.!?)]|(?:입니다|이에요|예요|이죠|이었|였|이고|이며|이라고|라고|이야|야|죠))",
        re.IGNORECASE,
    )
    parts = []
    offset = 0
    for match in declaration.finditer(text):
        prefix = text[max(0, match.start() - 16):match.start()]
        if _PERSONAL_NAME_PREFIX.search(prefix):
            continue
        parts.append(_PRIVATE_TEXT.sub(hide, text[offset:match.start()]))
        parts.append(match.group())
        offset = match.end()
    parts.append(_PRIVATE_TEXT.sub(hide, text[offset:]))
    return "".join(parts)


def catalog_text(text: str) -> str:
    if _CATALOG_INSTRUCTION.search(text):
        return "[카탈로그 설명 확인 필요]"
    return redact(text)


def shareable(fact: Fact) -> bool:
    return fact.kind != "personal" and all(
        _SECRET_MARK not in value and catalog_text(value) == value for value in (fact.value, fact.detail or "")
    )


def provenance(fact: Fact, fixture: bool = False) -> str:
    if fixture and fact.source in ("system", "official"):
        return "fixture"
    return {"official": "verified", "system": "registered"}.get(fact.source, "user_statement")


def model_fact(fact: Fact, *, fixture: bool = False) -> dict:
    data = {"id": fact.id, "kind": fact.kind, "source": fact.source, "value": redact(fact.value),
            "provenance": provenance(fact, fixture)}
    if fact.detail:
        data["detail"] = redact(fact.detail)[:500]
    if fact.date:
        data["date"] = fact.date.isoformat()
    if fact.progress:
        data["progress"] = fact.progress
    return data
