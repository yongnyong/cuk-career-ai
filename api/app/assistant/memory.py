"""Extract and reconcile only user-owned, evidenced career facts."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import get_args
from uuid import uuid4

from .contracts import EXPERIENCE_KINDS, Fact, MemoryEdit, MemoryKind, Progress
from .model import LanguageModel, generate_for
from .privacy import catalog_text, model_fact, redact, shareable
from .prompts import MEMORY, TEXT, object_schema

MEMORY_LIMIT = 120
_KINDS = get_args(MemoryKind)
_PROGRESS = get_args(Progress)
SINGLE_VALUES = {"goal", "department", "grade", "study_time"}
_ACTIONS = ("add", "set", "remove", "replace")
_UPDATE = object_schema(
    kind={"type": "STRING", "enum": list(_KINDS)},
    action={"type": "STRING", "enum": list(_ACTIONS)},
    value=TEXT,
    quote=TEXT,
    target_id=TEXT,
    previous_value=TEXT,
    detail=TEXT,
    date=TEXT,
    progress={"type": "STRING", "enum": list(_PROGRESS)},
)
_UPDATE["required"] = ["kind", "action", "value", "quote"]
SCHEMA = object_schema(updates={"type": "ARRAY", "items": _UPDATE})
_QUESTION = re.compile(r"(?:뭐(?:야|지|예요)|나요|까요|인가요|인지|어떻게|언제|추천해|알려줘|무엇)(?:[.!?…\s]|$)")
_QUESTION_END = re.compile(r"[?❓❔](?:[^\w]|_)*$")
_REQUEST_ONLY = re.compile(r"^(?:이|그|저)\s*(?:노드|기술|스킬)?\s*(?:설명|비교)해\s*줘[.!]?$")
_HYPOTHETICAL = re.compile(
    r"취득하고 싶|취득\s*예정|취득하려|취득할|취득하면|취득했으면|취득해야|"
    r"취득(?:을|이)?\s*(?:준비|목표)|딴다면|따면|있다면|한다면|됐으면|예를 들어|가상의?\s*(?:프로젝트|예시|경력|인턴)|가정|"
    r"아직.*(?:없|아니|못)|못\s*(?:땄|취득)|취득하지\s*않"
)
_OTHER = re.compile(r"(?:친구|동기|동생|선배|팀원|그 사람)(?:가|이|는|은|의)|(?:AI|챗봇)(?:가|이|는|은)")
_CHANGE = re.compile(r"이제|바꿨|바꿀|전에는|보다는|대신|정정|아니라|변경|됐어|되었어|정했|정정할")
_RETRACT = re.compile(r"아직|아니|아뇨|말고|취소|삭제|없|잘못|정정|빼|잊어|착각")
_CERTIFIED_CLAIM = re.compile(r"취득|땄|따\s*놨|합격|발급|획득|보유")
_CERTIFICATE_SUFFIX = re.compile(r"\s+자격증$")
_CERTIFICATE_CONTINUATION = re.compile(
    r"\s*(?:자격증|시험)?\s*(?:을|를|은|는|도|에)?\s*(?:(?:이미|최근에|이번에|작년에|올해)\s+)?"
    rf"(?:{_CERTIFIED_CLAIM.pattern})"
)
_META_INSTRUCTION = re.compile(r"(?:시스템|이전\s*지시|프롬프트).*(?:규칙|무시|저장)|(?:취득|보유)했다고\s*(?:기록|저장|가정)")
_PREPARING = re.compile(r"(?:준비|공부|학습|연습)\s*(?:하는\s*|하고\s*있|중)")
_NEGATED_CERTIFICATE = re.compile(
    r"(?:취득|합격|발급|획득|보유)(?:한|했|하는|이)?\s*(?:(?:게|건|것은|것이|것도)\s*)?(?:아니|못|하지\s*않)|"
    r"(?:안|못)\s*(?:땄|따|취득|합격)|딴\s*(?:(?:게|건|것은|것이)\s*)?아니"
)
_SHORT_PREPARATION = re.compile(
    r"^(?:(?:사실|정확히는)\s+)?(?:아니(?:요)?|아뇨)[,\s]+(?:(?:아직|지금)\s+)?"
    r"(?:시험(?:을)?\s+)?(?:준비|공부)\s*(?:중(?:이야|이에요|이예요|이다|입니다)?|하고\s*있(?:어(?:요)?|습니다|다))"
    r"[.!。]*$"
)
_CERTIFICATE_SUBJECT = re.compile(
    r"^(?:(?:사실|정확히는|그리고|저는|나는|제가|내가|나|저|이번에|최근에)\s+)*"
    r"(?P<name>[A-Za-z0-9가-힣][A-Za-z0-9가-힣 .+/#_-]{0,45}?)"
    r"(?:\s+자격증)?\s*(?:을|를|은|는|에|도)?\s*"
    rf"(?={_CERTIFIED_CLAIM.pattern}|{_NEGATED_CERTIFICATE.pattern}|{_PREPARING.pattern})"
)
_AMBIGUOUS_SUBJECT = re.compile(
    r"^(?:사실|정확히는|그|이|저|아직|지금|자격증|시험)(?:\s|$)|[,·]|(?:와|과|이랑|랑|하고|및|또는)\s|"
    r"취득|준비\s*중|합격|아니라|아니고"
)
_DRAFT_DIRECTIVE = re.compile(r"표현해|써\s*줘|작성|반영해|바꿔\s*줘")
_REMEMBER = re.compile(r"(?:기억|저장|기록)\s*(?:해\s*(?:줘|주|줄|둬|두|놔)|부탁|해\s*주세요)")
_FORGET = re.compile(r"잊어|(?:기억|기록|정보)(?:을|를)?\s*(?:지워|삭제|빼)")
_CLAUSE_BOUNDARY = re.compile(r"(?<=지만)[,，]?\s+|(?<=했고)[,，]?\s+|(?<=있고)[,，]?\s+|[,，]\s*(?:다만|반면|그리고)\s+")
_BASIC_SKILL = re.compile(
    r"(?:기초|기본)(?:\s*(?:문법|개념|사용법|기능))?(?:을|를|은|는|만)?\s*"
    r"(?:(?:어느\s*정도|조금|기본적으로)\s*)?(?:알고|알아|압니다|익혔|다룰\s*줄\s*알)"
)
_PROGRESS_EVIDENCE = {
    "preparing": _PREPARING,
    "completed": re.compile(r"취득|땄|합격|수료|마쳤|완료|할\s*줄\s*알|다뤄봤|써봤"),
    "not_held": re.compile(r"없|못|아니|않"),
    "beginner": re.compile(rf"초급|초보|입문|기초만|{_BASIC_SKILL.pattern}"),
    "intermediate": re.compile(r"중급"),
}
_EXPERIENCE_ASSERTION = {
    "project": re.compile(
        r"참여|수행|담당|맡았|만들|개발했|진행|제작|구현|프로젝트(?:를|을|은|는)?\s*(?:직접\s*)?"
        r"(?:했|해\s*(?:봤|보았|본\s*적(?:이|은)?\s*있))|프로젝트\s*경험(?:이|은|도)?\s*있"
    ),
    "job": re.compile(r"근무|재직|입사|일했|일하고"),
    "internship": re.compile(r"인턴(?:으로|을|이었|했)|인턴십(?:을)?\s*(?:했|마쳤|수료)|인턴\s*(?:근무|경험)"),
    "award": re.compile(r"수상했|수상한|상을?\s*받|입상|선정됐"),
    "activity": re.compile(r"활동했|활동 중|참여|운영|봉사했|동아리(?:를)?\s*했"),
}
_EXPERIENCE_ABSENCE = re.compile(
    r"(?:(?:해\s*본|해본|해\s*보았던|한|참여한|수행한|맡은|개발한|구현한|일한|다닌)\s*(?:적|경험)|경험|이력)"
    r"(?:은|는|이|가|을|를|도)?\s*(?:(?:전혀|아직|한\s*번도)\s*)?없(?=$|[.!?…]|어|었|습니|다|음|고|지만)|"
    r"해\s*보(?:지는|진)\s*못|(?:한\s*번도\s*)?(?:안|못)\s*해\s*(?:봤|보았)"
)
_NONFACTUAL_EXPERIENCE = re.compile(
    r"예를\s*들어|^예시로|가정|가상의?\s*(?:프로젝트|경력|인턴|활동|사례)|이라면|한다면|있다면|(?:할|있을|없을)\s*경우|"
    r"(?:할|참여할|진행할)\s*(?:계획|예정)|(?:계획|예정)(?:이야|입니다)|"
    r"(?:해|하(?:고|고는)|참여하고|맡고|진행하고)\s*싶|(?:했다고|있다고|없다고)\s*(?:써|적|기록|저장)|"
    r"(?:써|적어|표현해|반영해|작성해)\s*(?:줘|주세|줄래)"
)
_SELF = re.compile(r"(?:^|[,\s]+)(?:나는|저는|내가|제가|나|저)(?=\s)")
_SUBJECT = (
    r"^(?:(?:나는|저는|내가|제가|나|저|사실|실제|실제로|아직|다만|지금|요즘)\s+)*"
    r"(?P<name>[가-힣A-Za-z][가-힣A-Za-z0-9 .+/#_-]{0,55}?)\s*"
)
_DIRECT_BASIC_SKILL = re.compile(rf"{_SUBJECT}(?P<detail>{_BASIC_SKILL.pattern})")
_DIRECT_ABSENCE = re.compile(rf"{_SUBJECT}(?:을|를|은|는|에)?\s*(?={_EXPERIENCE_ABSENCE.pattern})")
_AMBIGUOUS_DIRECT = re.compile(r"[,·]|(?:와|과|및|또는)\s|\b(?:and|or)\b|^(?:그|이|저)(?:\s|$)", re.I)


@dataclass
class MemoryDiagnostic:
    """Opt-in, value-free observation of extraction, validation and commit."""

    extraction: str = "not_started"
    update_count: int = 0
    field_shapes: list[dict[str, str]] = field(default_factory=list)
    validation: dict[int, str] = field(default_factory=dict)
    memory_committed: bool = False

    def observe(self, updates: list) -> None:
        self.extraction = "received" if updates else "empty_updates"
        self.update_count = len(updates)
        for item in updates[:8]:
            shapes = {}
            if isinstance(item, dict):
                for key in _UPDATE["properties"]:
                    value = item.get(key)
                    if key not in item:
                        shapes[key] = "missing"
                    elif value is None:
                        shapes[key] = "null"
                    elif isinstance(value, str):
                        choices = _KINDS if key == "kind" else _ACTIONS if key == "action" else ()
                        token = _enum(value)
                        shapes[key] = token if token in choices else "text" if token else "empty"
                    else:
                        shapes[key] = "invalid_type"
            self.field_shapes.append(shapes)


def _normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def identity(value: str) -> str:
    return _normal(value).replace(" ", "").casefold()


def _found(value: str, text: str) -> bool:
    if not value or identity(value) not in identity(text):
        return False
    if re.fullmatch(r"[A-Za-z0-9._+-]+", value):
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])", text, re.I) is not None
    return True


def _statements(message: str) -> list[str]:
    text = unicodedata.normalize("NFKC", message)
    text = re.sub(r"(아니고|아니라|않고|지만|있으며|중)([,，]?)[ \t]*\r?\n[ \t]*(?=\S)", r"\1\2 ", text)
    pieces = re.split(r"(?<=[.!?❓❔])(?=\s|[가-힣])|\n|[,;]\s*(?=(?:아니(?:요)?|아뇨)[,\s])", text)
    return [_normal(piece) for piece in pieces
            if any(char.isalnum() for char in re.sub(r"[0-9]\ufe0f?\u20e3", "", piece))]


def _quoted_statement(statements: list[str], quote: str) -> tuple[int, str] | None:
    matches = [(index, statement) for index, statement in enumerate(statements) if quote in statement]
    return matches[0] if len(matches) == 1 else None


def _certificate_subject(statement: str) -> str | None:
    match = _CERTIFICATE_SUBJECT.match(statement)
    name = match["name"].strip() if match else ""
    if name and not _AMBIGUOUS_SUBJECT.search(name) and catalog_text(name) == name:
        return name
    return None


def _personal_statement(statement: str) -> bool:
    return not any(p.search(statement) for p in (_QUESTION_END, _QUESTION, _OTHER, _META_INSTRUCTION))


def asks_to_remember(message: str) -> bool:
    return bool(_REMEMBER.search(message) and not re.search(r"(?:잊|기억하지|저장하지)\s*마", message))


def _claim_scope(statement: str, value: str, quote: str) -> str:
    clauses = [part for part in _CLAUSE_BOUNDARY.split(statement) if _found(value, part)
               and (quote in part or part in quote)]
    return clauses[0] if len(clauses) == 1 else statement


def _direct_claims(message: str, statements: list[str]) -> list[dict]:
    """Recover plainly worded, self-owned information from a remember request."""
    if not asks_to_remember(message) or not _SELF.search(message) or _OTHER.search(message):
        return []
    updates = []
    for statement in statements:
        if not _personal_statement(statement) or _NONFACTUAL_EXPERIENCE.search(statement):
            continue
        for clause in _CLAUSE_BOUNDARY.split(statement):
            skill = _DIRECT_BASIC_SKILL.match(clause)
            if skill and not re.search(r"몰|않|못|없는|알지\s*못", clause):
                name = skill["name"].strip()
                if not _AMBIGUOUS_DIRECT.search(name):
                    updates.append(dict(kind="skill", action="set", value=name, quote=clause,
                                        detail=skill["detail"], progress="beginner"))
                continue
            absence = _DIRECT_ABSENCE.match(clause)
            if absence:
                name = absence["name"].strip()
                if "프로젝트" in name and not _AMBIGUOUS_DIRECT.search(name):
                    updates.append(dict(kind="project", action="set", value=name, quote=clause, progress="not_held"))
    return updates


def _preparation_statement(statement: str) -> bool:
    return bool(_PREPARING.search(statement) and not re.search(r"예를 들어|가정|이라면|한다면", statement))


def certificate_preparation(topic: str) -> str | None:
    """Read a named status correction scoped to a draft, without changing memory."""
    for statement in reversed(_statements(topic)):
        clauses = re.split(r",\s*|(?:줄이고|늘리고|다듬고)\s+", statement)
        for clause in reversed(clauses):
            if any(pattern.search(clause) for pattern in (_OTHER, _META_INSTRUCTION)):
                continue
            if (_personal_statement(clause) or _DRAFT_DIRECTIVE.search(clause)) and (
                _NEGATED_CERTIFICATE.search(clause) and _preparation_statement(clause)
            ):
                name = _certificate_subject(clause)
                if name:
                    return name
    return None


def _enum(value):
    return value.strip().lower() if isinstance(value, str) else None


def manual_fact(edit: MemoryEdit, fact_id: str | None = None) -> Fact:
    return Fact(id=fact_id or uuid4().hex, source="user_claim", **edit.model_dump())


def needs_extraction(message: str) -> bool:
    return any(not _QUESTION_END.search(part) and not _QUESTION.search(part) and not _REQUEST_ONLY.fullmatch(part)
               for part in _statements(message))


def extraction_context(message: str, memory: list[Fact], recent: list[str]) -> dict:
    candidates = [fact for fact in reversed(memory) if shareable(fact)]
    candidates.sort(key=lambda fact: (
        not _found(fact.value, message), not any(_found(fact.value, text) for text in recent),
    ))
    return {
        "memory": [{key: value for key, value in model_fact(fact).items() if key in ("id", "kind", "value", "progress")}
                   for fact in candidates[:12]],
        "recent": [redact(item)[-260:] for item in recent[-2:]],
    }


def read_updates(out: dict, diagnostic: MemoryDiagnostic | None = None) -> list:
    updates = out.get("updates")
    if not isinstance(updates, list):
        if diagnostic is not None:
            diagnostic.extraction = "invalid_updates" if "updates" in out else "missing_updates"
        return []
    if diagnostic is not None:
        diagnostic.observe(updates)
    return updates[:8]


def extract_updates(model: LanguageModel, message: str, memory: list[Fact], recent: list[str],
                    diagnostic: MemoryDiagnostic | None = None) -> list:
    if not needs_extraction(message):
        if diagnostic is not None:
            diagnostic.extraction = "skipped_question"
        return []
    if diagnostic is not None:
        diagnostic.extraction = "requested"
    out = generate_for(
        model, "memory", MEMORY, {"message": redact(message), **extraction_context(message, memory, recent)},
        SCHEMA,
    )
    return read_updates(out, diagnostic)


def _target(kind, item, quote, memories, recent):
    group = [fact for fact in memories if fact.kind == kind]
    direct = [fact for fact in group if _found(fact.value, quote)]
    previous = item.get("previous_value")
    if isinstance(previous, str) and _found(previous, quote):
        direct = [fact for fact in direct if identity(fact.value) == identity(previous)]
    deictic = re.search(
        r"(?:그\s*(?:자격증|경력|활동|프로젝트|목표|교육)|그거|그\s*정보|아까|전에\s*말한|"
        r"사실.*(?:아니|착각|정정)|(?:취득|딴).*아니라)", quote,
    )
    if not direct and deictic:
        mentioned = [fact for fact in group if any(_found(fact.value, item) for item in recent[-2:])]
        direct = mentioned or group
    if len(direct) == 1 and item.get("target_id") in (None, "", direct[0].id):
        return direct[0]
    return None


def effective_facts(registered: list[Fact], memories: list[Fact]) -> tuple[list[Fact], list[Fact]]:
    """Conversation claims can change advice without modifying the profile."""
    keys = {(fact.kind, identity(fact.value)) for fact in memories if fact.progress in ("preparing", "not_held")}
    single = {fact.kind for fact in memories} & SINGLE_VALUES
    active, conflicting = [], []
    for fact in registered:
        destination = conflicting if fact.kind in single or (fact.kind, identity(fact.value)) in keys else active
        destination.append(fact)
    return [*memories, *active], conflicting


def _acquisition_subject(statement: str) -> str | None:
    if not (_personal_statement(statement) and _CERTIFIED_CLAIM.search(statement)) or (
        _HYPOTHETICAL.search(statement) or _NEGATED_CERTIFICATE.search(statement) or _DRAFT_DIRECTIVE.search(statement)
    ):
        return None
    name = _certificate_subject(statement)
    return name if name and _CERTIFICATE_CONTINUATION.match(statement.partition(name)[2]) else None


def _turn_corrections(statements: list[str], previous_message: str) -> dict[int, tuple[str, str]]:
    corrections = {}
    for index, statement in enumerate(statements):
        short = _SHORT_PREPARATION.search(statement)
        if not (_personal_statement(statement) and (short or _NEGATED_CERTIFICATE.search(statement))):
            continue
        if re.search(r"예를 들어|가정|이라면|한다면", statement):
            continue
        name = None if short else _certificate_subject(statement)
        if not name and index:
            name = _acquisition_subject(statements[index - 1])
        elif not name and short:
            previous = [part for part in _statements(previous_message) if _personal_statement(part)
                        and (not _REMEMBER.search(part) or _CERTIFIED_CLAIM.search(part))]
            if previous:
                name = _acquisition_subject(previous[-1])
        if name and not _DRAFT_DIRECTIVE.search(statement):
            corrections[index] = name, "preparing" if _preparation_statement(statement) else "not_held"
    return corrections


def reconcile(message: str, updates: list, memories: list[Fact], registered: list[Fact], recent: list[str],
              diagnostic: MemoryDiagnostic | None = None, *, mock_profile: bool = False):
    facts = list(memories)
    questions = []
    validation = diagnostic.validation if diagnostic is not None else {}
    statements = _statements(message)
    corrections = _turn_corrections(statements, recent[-1] if recent else "")
    direct = _direct_claims(message, statements)
    direct_scopes = {(item["kind"], item["quote"]) for item in direct}
    ordered = []
    for index, item in enumerate([*updates, *direct]):
        if not isinstance(item, dict):
            validation[index] = "invalid_item"
            continue
        raw_quote = item.get("quote")
        quote = _normal(raw_quote) if isinstance(raw_quote, str) else ""
        evidence = _quoted_statement(statements, quote) if quote else None
        if not evidence:
            validation[index] = "quote_missing_or_unbound"
            continue
        position, statement = evidence
        kind = _enum(item.get("kind"))
        value = item.get("value")
        scope = _claim_scope(statement, value, quote) if isinstance(value, str) else statement
        if (kind == "certification" and position in corrections
                or index < len(updates) and (kind, scope) in direct_scopes):
            validation[index] = "reconciled_from_statement"
            continue
        ordered.append((position, statement.index(quote), index, item, quote))
    blocked = set()
    for position, statement in enumerate(statements[1:], 1):
        if (position in corrections or not _personal_statement(statement)
                or _DRAFT_DIRECTIVE.search(statement) or not (
                    _NEGATED_CERTIFICATE.search(statement) or _SHORT_PREPARATION.search(statement)
                )):
            continue
        earlier = [(index, identity(item["value"])) for clause, _, index, item, quote in ordered
                   if clause == position - 1 and _enum(item.get("kind")) == "certification"
                   and _enum(item.get("action")) in ("add", "set") and isinstance(item.get("value"), str)
                   and _CERTIFIED_CLAIM.search(quote) and _found(item["value"], quote)]
        if len({value for _, value in earlier}) > 1:
            questions.append("어떤 정보를 정정할지 이름을 알려주시겠어요?")
            blocked.update(index for index, _ in earlier)
    for position, (name, progress) in corrections.items():
        ordered.append((position, 0, len(updates) + len(direct) + position, {"kind": "certification", "action": "set",
                        "value": name, "progress": progress}, statements[position]))
    for position, _, index, item, quote in sorted(ordered, key=lambda item: item[:3]):
        if index in blocked:
            validation[index] = "ambiguous_retraction"
            continue
        kind, action = _enum(item.get("kind")), _enum(item.get("action"))
        raw_value = item.get("value", "")
        if kind not in _KINDS or action not in _ACTIONS:
            validation[index] = "invalid_kind_or_action"
            continue
        statement = statements[position]
        if redact(statement) != statement:
            validation[index] = "private_evidence"
            continue
        if not _personal_statement(statement):
            validation[index] = "not_user_assertion"
            continue
        if kind == "skill" or kind in EXPERIENCE_KINDS:
            statement = _claim_scope(statement, raw_value if isinstance(raw_value, str) else "", quote)
            if statement in quote:
                quote = statement
        progress = _enum(item.get("progress"))
        if kind in EXPERIENCE_KINDS:
            if _NONFACTUAL_EXPERIENCE.search(statement):
                validation[index] = "hypothetical_or_negated"
                continue
            explicitly_forgetting = action == "remove" and _FORGET.search(statement)
            if _EXPERIENCE_ABSENCE.search(statement) and not explicitly_forgetting:
                progress = "not_held"
                if action == "remove":
                    action = "set"
            elif progress == "not_held" and not explicitly_forgetting:
                validation[index] = "progress_not_in_quote"
                continue
            else:
                progress = None
        elif progress not in _PROGRESS or kind not in ("certification", "skill", "training"):
            progress = None
        elif not _PROGRESS_EVIDENCE[progress].search(quote):
            validation[index] = "progress_not_in_quote"
            continue
        if kind == "certification":
            if progress in ("beginner", "intermediate"):
                validation[index] = "invalid_progress"
                continue
            if _PREPARING.search(quote) and (progress == "preparing" or _NEGATED_CERTIFICATE.search(statement)):
                progress = "preparing"
            if _NEGATED_CERTIFICATE.search(statement) and progress not in ("preparing", "not_held") and action != "remove":
                validation[index] = "hypothetical_or_negated"
                continue
        if action in ("remove", "replace"):
            if not _RETRACT.search(statement):
                validation[index] = "missing_retraction"
                continue
            target = _target(kind, item, quote, facts, [*recent, *statements[:position]])
            if target is None:
                questions.append("어떤 정보를 정정할지 이름을 알려주시겠어요?")
                validation[index] = "ambiguous_retraction"
                continue
            if action == "remove" and progress not in ("preparing", "not_held"):
                facts.remove(target)
                validation[index] = "accepted"
                continue
        else:
            target = None
            if _HYPOTHETICAL.search(statement) and (progress not in ("preparing", "not_held") or
                                                   re.search(r"예를 들어|가정|한다면", statement)):
                validation[index] = "hypothetical_or_negated"
                continue
            if kind in _EXPERIENCE_ASSERTION and progress != "not_held" and not _EXPERIENCE_ASSERTION[kind].search(quote):
                validation[index] = "missing_experience_assertion"
                continue
            if kind == "certification" and progress not in ("preparing", "not_held") and not _CERTIFIED_CLAIM.search(quote):
                # A name-only citation can borrow an immediately following claim in that source sentence.
                after_quote = statement.partition(quote)[2]
                if statement.count(quote) != 1 or not _CERTIFICATE_CONTINUATION.match(after_quote):
                    validation[index] = "missing_acquisition_assertion"
                    continue
        value = _normal(raw_value) if isinstance(raw_value, str) else ""
        inherited_value = target and action in ("remove", "replace") and progress and (
            not value or identity(target.value) == identity(value)
        )
        if inherited_value:
            value = target.value
        if kind == "certification":
            value = _CERTIFICATE_SUFFIX.sub("", value)
        if len(value) > 240 or (kind == "certification" and value == "자격증") or not (
            inherited_value or _found(value, quote)
            or (kind == "certification" and position in corrections and index >= len(updates) + len(direct))
        ):
            validation[index] = "value_not_in_quote"
            continue
        if kind == "grade":
            match = re.fullmatch(r"([1-9])\s*(?:학년)?", value)
            if not match:
                validation[index] = "invalid_grade"
                continue
            value = match[1]
        if kind == "study_time" and not re.search(r"\d+\s*(?:시간|분)", value):
            validation[index] = "study_time_not_explicit"
            continue
        if kind in SINGLE_VALUES and action in ("set", "add"):
            own = next((fact for fact in facts if fact.kind == kind), None)
            prior = own or next((fact for fact in registered if fact.kind == kind), None)
            if prior and identity(prior.value) != identity(value):
                if kind != "study_time" and not _CHANGE.search(statement):
                    label = {"goal": "목표", "department": "전공", "grade": "학년"}[kind]
                    questions.append(f"저장된 {label}과 달라요. 바꾸려면 ‘{label}을(를) {value}(으)로 정정해 줘’라고 알려주세요.")
                    validation[index] = "goal_requires_confirmation" if kind == "goal" else "profile_conflict"
                    continue
                target = own
        if not target and (kind in ("certification", "skill", "training") or kind in EXPERIENCE_KINDS):
            existing = next((fact for fact in facts if fact.kind == kind and identity(fact.value) == identity(value)), None)
            if existing and existing.progress != progress and (progress or (
                (kind == "certification" or kind in EXPERIENCE_KINDS) and existing.progress in ("preparing", "not_held")
            )):
                if (progress == "preparing" and existing.progress in (None, "completed")
                        and existing in memories and not _RETRACT.search(statement)):
                    questions.append(f"{value}의 기록을 바꾸려면 ‘{value}는 취득한 게 아니라 준비 중이야’라고 알려주세요.")
                    validation[index] = "progress_requires_confirmation"
                    continue
                target = existing
        detail = item.get("detail")
        if not isinstance(detail, str) or not detail.strip() or detail not in quote or len(detail) > 2000:
            detail = None
        acquired = item.get("date")
        try:
            acquired = date.fromisoformat(acquired) if (
                isinstance(acquired, str) and acquired in quote and progress not in ("preparing", "not_held")
            ) else None
        except ValueError:
            acquired = None
        fact = Fact(
            id=target.id if target else uuid4().hex, kind=kind, value=value,
            source="conversation", detail=detail, date=acquired, progress=progress,
        )
        if not shareable(fact):
            validation[index] = "private_value"
            continue
        if kind in SINGLE_VALUES and (not mock_profile or kind == "goal") and any(
            entry.kind == kind and identity(entry.value) == identity(value) for entry in registered
        ):
            validation[index] = "registered_duplicate"
            if target and kind == "goal":
                facts.remove(target)
                validation[index] = "accepted"
            elif target:
                questions.append("같은 내용의 등록 기록이 있어요. 어떤 정보를 정정할지 확인해 주세요.")
            continue
        matches = [entry for entry in facts
                   if entry.kind == kind and identity(entry.value) == identity(value) and entry != target]
        if matches:
            if acquired and any(entry.date != acquired for entry in matches):
                questions.append(f"{value}의 취득일을 변경할지 확인해 주세요.")
            validation[index] = "memory_duplicate"
            continue
        if target:
            facts[facts.index(target)] = fact
        elif len(facts) < MEMORY_LIMIT:
            facts.append(fact)
        else:
            validation[index] = "memory_limit"
            continue
        validation[index] = "accepted"
    return facts, list(dict.fromkeys(questions))
