"""Upload templates, map existing facts, and export a separate application draft."""
import re
from collections.abc import Sequence
from dataclasses import replace
from typing import get_args
from uuid import uuid4

from .contracts import (
    DocumentRecord, DocumentReference, Draft, DraftEdit, DraftField, DraftRequest,
    Fact, FieldKind, NarrativeContext, NarrativeOptions, NarrativeResult, Profile, TemplateField,
)
from .document_formats import MIME_TYPES, label_key, parse_template, render_template, validate_upload
from .errors import AssistantError, Conflict, ModelInvalidResponse, ModelUnavailable, NotFound
from .memory import certificate_preparation, identity
from .model import LanguageModel, generate_for, model_phase, model_request
from .narrative import (
    WORK_EXPERIENCE, Brief, applicable_experience, brief, compose, draft_interest, experience_focus, for_revision,
    limited_draft, restricts_sources,
)
from .privacy import catalog_text, model_fact, redact, shareable
from .prompts import FIELD_MATCHING, NARRATIVE, TEXT, enum_array, object_schema
from .repository import AssistantStore, CareerData
from .skill_context import mentioned

_FIELD_SCHEMA = object_schema(fields={"type": "ARRAY", "items": object_schema(
    id=TEXT, kind={"type": "STRING", "enum": list(get_args(FieldKind))},
)})
_DATE_LABELS = {"취득일", "자격증취득일", "certificatedate"}
_PERSONAL_KEYS = {
    "이름": "name", "성명": "name", "fullname": "name",
    "연락처": "phone", "이메일": "email", "주소": "address", "인적사항": "personal",
}


def _registered(fact: Fact) -> bool:
    return fact.source == "official" or (fact.source == "system" and fact.kind not in ("certification", "personal"))


def _owned_evidence(profile: Profile, memory: Sequence[Fact]) -> list[Fact]:
    sources = [*memory, *(fact for fact in profile.facts if not profile.mock and _registered(fact))]
    return [fact for fact in sources if shareable(fact)]


def _contested(facts: Sequence[Fact]) -> set[tuple[str, str]]:
    return {(fact.kind, identity(fact.value)) for fact in facts if fact.progress in ("preparing", "not_held")}


def _applicable(field: TemplateField, fact: Fact) -> bool:
    if field.kind == "career":
        return fact.kind in ("job", "internship")
    if field.kind != fact.kind:
        return False
    if field.kind == "personal":
        key = label_key(field.label)
        return fact.field_key in {field.id, _PERSONAL_KEYS.get(key, key)}
    if field.kind == "certification" and label_key(field.label) in _DATE_LABELS:
        return fact.date is not None
    return True


def _format_fact(field: TemplateField, fact: Fact) -> str:
    if field.kind == "certification" and label_key(field.label) in _DATE_LABELS:
        return fact.date.isoformat()
    values = [fact.value]
    if fact.date:
        values.append(fact.date.isoformat())
    if fact.detail:
        values.append(fact.detail)
    return " · ".join(values)


def _fits_pdf(value: str) -> bool:
    return all("\x20" <= char <= "\x7e" or char == "\n" for char in value)


class DocumentService:
    def __init__(self, data: CareerData, store: AssistantStore, model: LanguageModel):
        self.data = data
        self.store = store
        self.model = model

    @model_request("document_upload")
    def upload(self, user_id: str, filename: str, contents: bytes) -> DocumentRecord:
        name, format = validate_upload(filename, contents)
        template = parse_template(format, contents)
        fields = template.fields
        unknown = [{"id": field.id, "label": field.label}
                   for field in fields if field.kind == "unknown" and catalog_text(field.label) == field.label][:20]
        if unknown:
            allowed_ids = {item["id"] for item in unknown}
            try:
                result = generate_for(self.model, "field_matching", FIELD_MATCHING, {"fields": unknown}, _FIELD_SCHEMA)
            except ModelUnavailable:
                template.warnings.append("일부 필드는 자동 분류할 수 없었어요. 해당 항목을 확인해 주세요.")
                result = {}
            proposed = result.get("fields")
            mapping = {
                item["id"]: item["kind"] for item in proposed[:20]
                if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] in allowed_ids
                and item.get("kind") in get_args(FieldKind)
            } if isinstance(proposed, list) else {}
            fields = [field.model_copy(update={"kind": mapping.get(field.id, "unknown")})
                      if field.kind == "unknown" else field for field in fields]
        record = DocumentRecord(id=uuid4().hex, filename=name, format=format, fields=fields, warnings=template.warnings)
        self.store.create_document(user_id, record, contents)
        return record

    def get(self, user_id: str, document_id: str) -> DocumentRecord:
        return self.store.get_document(user_id, document_id)

    def narrative(self, profile: Profile, topic: str, memory: Sequence[Fact] = (), *,
                  options: NarrativeOptions | None = None, previous_topic: str = "",
                  previous_text: str | None = None, previous_ids: Sequence[str] = (),
                  requirements: Brief | None = None) -> NarrativeResult:
        field = TemplateField(id="narrative", label="자기소개서", kind="narrative")
        draft = self._narrative(field, profile, memory, topic, options or NarrativeOptions(),
                                previous_topic, previous_text, previous_ids, requirements=requirements)
        return NarrativeResult(draft=draft, mock_data=profile.mock)

    def _related_preparation(self, role: str | None, topic: str, memory: Sequence[Fact]) -> Fact | None:
        preparations = [fact for fact in memory
                        if fact.kind == "certification" and fact.progress == "preparing" and shareable(fact)]
        named = [fact for fact in preparations if mentioned(fact.value, topic)]
        if named or not role or not preparations:
            return named[0] if named else None
        list_roles = getattr(self.data, "list_career_roles", None)
        get_tree = getattr(self.data, "get_skill_tree", None)
        if not list_roles or not get_tree:
            return None
        role_key = identity(role)
        roles = list_roles()
        matching = [item for item in roles if identity(item.name) == role_key]
        if not matching:
            matching = [item for item in roles if identity(item.name).startswith(role_key)]
        tree = get_tree(matching[0].id) if len(matching) == 1 else None
        if not tree:
            return None
        skills = [node.skill_name for node in tree.nodes.values() if node.required]
        for fact in preparations:
            if any(mentioned(skill, fact.value) or (
                re.fullmatch(r"[A-Za-z]{3,}", skill) and identity(fact.value).startswith(identity(skill))
            ) for skill in skills):
                return fact
        return None

    def _saved_target_role(self, facts: list[Fact]) -> str | None:
        goal = next((fact for fact in facts if fact.kind == "goal"), None)
        if not goal:
            return None
        explicit = re.fullmatch(r"(.+?)\s*(?:직무|포지션)", goal.value)
        if explicit:
            return explicit[1]
        list_roles = getattr(self.data, "list_career_roles", None)
        return next((role.name for role in list_roles() if identity(role.name) == identity(goal.value)), None) if list_roles else None

    def narrative_brief(self, profile: Profile, topic: str, memory: Sequence[Fact], *,
                        options: NarrativeOptions | None = None, previous_topic: str = "",
                        previous_text: str | None = None, previous_context: NarrativeContext | None = None) -> Brief:
        requirements = for_revision(
            brief(topic, options or NarrativeOptions(), previous_topic, previous_context), topic, previous_text,
        )
        if not requirements.role and requirements.question == "motivation":
            return replace(requirements, role=self._saved_target_role(_owned_evidence(profile, memory)))
        return requirements

    @model_request("document_narrative")
    def _narrative(self, field: TemplateField, profile: Profile, memory: Sequence[Fact], topic: str,
                   options: NarrativeOptions, previous_topic: str = "", previous_text: str | None = None,
                   previous_ids: Sequence[str] = (), *, requirements: Brief | None = None) -> DraftField:
        requirements = requirements or self.narrative_brief(
            profile, topic, memory, options=options, previous_topic=previous_topic, previous_text=previous_text,
        )
        if not requirements.valid:
            return DraftField(field=field, status="missing", note="요청하신 최소·최대 글자 수를 확인해 주세요.")
        owned = _owned_evidence(profile, memory)
        request_text = f"{previous_topic}\n{topic}"
        kinds = experience_focus(topic, previous_topic)
        if not kinds and requirements.question == "experience":
            kinds = WORK_EXPERIENCE
        contested = _contested(memory)
        preparation = None
        preparation_name = certificate_preparation(topic)
        earlier_preparation = certificate_preparation(previous_topic)
        if not preparation_name and earlier_preparation and not any(
            fact.kind == "certification" and identity(fact.value) == identity(earlier_preparation)
            and fact.progress != "preparing" for fact in memory
        ):
            preparation_name = earlier_preparation
        if preparation_name:
            key = "certification", identity(preparation_name)
            contested.add(key)
            preparation = next((fact for fact in memory if fact.kind == key[0] and identity(fact.value) == key[1]
                                and fact.progress == "preparing" and shareable(fact)), None)
            if not preparation:
                preparation = Fact(id=uuid4().hex, kind="certification", value=preparation_name,
                                   source="conversation", progress="preparing")
        elif not kinds and requirements.question == "motivation":
            preparation = self._related_preparation(requirements.role, topic, owned)

        def relevant(fact: Fact) -> bool:
            return (applicable_experience(fact) and (not kinds or fact.kind in kinds) and shareable(fact)
                    and (fact.kind, identity(fact.value)) not in contested)

        claims = [fact for fact in memory if relevant(fact)]
        profile_facts = [
            fact for fact in profile.facts if relevant(fact) and _registered(fact)
        ]
        fixture = profile.mock and not claims and not (
            requirements.role or preparation or restricts_sources(request_text) or re.search(
                r"실제|제출|실지원|확인된|(?:말한|알려\s*준|제공한)\s*정보만", request_text,
            )
        )
        allowed = ([*claims, *(profile_facts if not profile.mock or fixture else [])])[:20]
        background = [fact for fact in owned if fact.kind in ("department", "interest")]
        background.sort(key=lambda fact: (not mentioned(fact.value, topic), fact.id not in previous_ids))
        interest = draft_interest(requirements, background, topic)
        by_id = {fact.id: fact for fact in allowed}
        prior = [by_id[key] for key in previous_ids if key in by_id]

        def limited() -> DraftField:
            question = "이 문항에 넣을 실제 경험 한 가지와 그때 맡은 일을 알려주실 수 있나요?"
            if not kinds and requirements.question in ("motivation", "introduction"):
                with model_phase("draft_render"):
                    text, sources = limited_draft(requirements, background, preparation, interest)
                if text:
                    note = ("확인된 정보 범위에서 썼어요. " if requirements.question == "motivation"
                            else "말씀하신 내용과 앞으로의 계획을 바탕으로 썼어요. ")
                    return DraftField(field=field, status="draft", value=text, sources=sources, note=note + question)
            note = question
            if preparation and not kinds:
                note = "준비 상태를 담을 수 있도록 글자 수를 조정해 주시겠어요?"
            elif requirements.minimum > 1:
                note = "요청한 글자 수를 채울 근거가 부족해요. " + question
            return DraftField(field=field, status="missing", note=note)

        if not allowed:
            return limited()
        if preparation_name:
            if not prior and not kinds and requirements.question in ("motivation", "introduction"):
                return limited()
            selected = prior
        else:
            result = generate_for(
                self.model, "narrative",
                NARRATIVE, {
                    "topic": redact(topic), "previousTopic": redact(previous_topic)[-600:],
                    "previousDraft": redact(previous_text.splitlines()[1])[:500]
                    if previous_text and len(previous_text.splitlines()) > 1 and previous_text.startswith("[AI 초안]") else "",
                    "previousFactIds": [fact.id for fact in prior],
                    "targetRole": requirements.role, "question": requirements.question,
                    "minCharacters": requirements.minimum, "maxCharacters": requirements.maximum,
                    "facts": [model_fact(fact, fixture=fixture and fact.source in ("official", "system"))
                              for fact in allowed],
                },
                object_schema(factIds=enum_array(by_id)),
            )
            chosen = result.get("factIds")
            if not isinstance(chosen, list):
                raise ModelInvalidResponse("Gemini 답변의 근거 목록을 확인할 수 없어요.",
                                           operation="narrative", reason="fact_ids_schema")
            selected = [by_id[key] for key in dict.fromkeys(key for key in chosen[:4]
                                                         if isinstance(key, str) and key in by_id)]
            if prior and previous_text and requirements.concise:
                selected = prior
            if not selected:
                return limited()
        with model_phase("draft_render"):
            text, sources = compose(requirements, selected, fixture, preparation=preparation, interest=interest)
        if not text or kinds and not any(fact.kind in kinds for fact in sources):
            return limited()
        note = None
        if fixture:
            note = "가상 예시 초안이에요. 제출용으로 사용할 실제 경험을 알려 주세요."
        elif any(fact.source in ("conversation", "user_claim") and applicable_experience(fact) for fact in sources):
            note = "말씀하신 경험을 바탕으로 썼어요. 제출 전 본인이 맡은 역할과 성과를 확인해 주세요."
        if not fixture and not requirements.role and requirements.question == "motivation":
            note = "어떤 직무에 지원하는지 알려주시면 경험을 지원동기와 연결해 드릴게요."
        elif not fixture and requirements.question == "motivation" and not any(
            fact.kind in WORK_EXPERIENCE for fact in sources
        ):
            note = "지원 직무와 관련해 직접 해 본 일 한 가지가 있나요?"
        elif not fixture and all(not fact.detail for fact in sources):
            note = "이 경험에서 직접 맡은 일은 무엇이었나요?"
        return DraftField(field=field, status="draft", value=text, sources=sources, note=note)

    def _fill(self, field: TemplateField, facts: list[Fact], fixture_ids: set[str]) -> DraftField:
        if field.kind == "unknown":
            return DraftField(field=field, status="missing", note="필드의 의미를 확인해 주세요.")
        applicable = [fact for fact in facts if _applicable(field, fact)]
        matching = [fact for fact in applicable if fact.progress not in ("preparing", "not_held")]
        known = [fact for fact in matching if _registered(fact)]
        claims = [fact for fact in matching if not _registered(fact)]
        contested = _contested(applicable)
        if any((fact.kind, identity(fact.value)) in contested for fact in known):
            return DraftField(field=field, status="confirmation", suggestions=applicable,
                              note="기존 기록과 현재 진술이 달라요. 이 항목을 확인해 주세요.")
        if field.kind in ("personal", "department", "grade", "status", "goal") and len({fact.value for fact in matching}) > 1:
            return DraftField(field=field, status="confirmation", suggestions=matching, note="어느 값을 사용할지 확인해 주세요.")
        if known:
            value = "\n".join(
                _format_fact(field, fact)
                + (" [가상 예시]" if fact.id in fixture_ids and fact.kind in ("job", "internship", "project", "award") else "")
                for fact in known
            )
            if len(value) > 4000:
                return DraftField(field=field, status="confirmation", suggestions=matching,
                                  note="양식에 넣을 이력 항목을 선택해 주세요.")
            return DraftField(field=field, status="filled", value=value, sources=known, suggestions=claims,
                              note="추가 진술의 확인이 필요해요." if claims else None)
        if claims:
            return DraftField(field=field, status="confirmation", suggestions=claims, note="공식 확인 또는 사용자 검토가 필요해요.")
        return DraftField(field=field, status="missing")

    @model_request("document_draft")
    def prepare(self, record: DocumentRecord, profile: Profile, memory: list[Fact], request: DraftRequest, *,
                previous_topic: str = "", requirements: Brief | None = None) -> Draft:
        all_ids = {field.id for field in record.fields}
        if request.field_ids and not set(request.field_ids) <= all_ids:
            raise NotFound("양식에 없는 항목이에요.")
        previous = {item.field.id: item for item in record.draft.fields} if record.draft else {}
        target = set(request.field_ids) if request.field_ids else all_ids
        fixture_ids = {fact.id for fact in profile.facts} if profile.mock else set()
        actual_application = request.target_role or (
            request.narrative_prompt and re.search(r"실제|제출|실지원", request.narrative_prompt)
        )
        records = [*profile.facts, *memory] if not (profile.mock and actual_application) else memory
        results = {}
        for field in record.fields:
            current = previous.get(field.id)
            if field.id not in target:
                results[field.id] = current or DraftField(field=field, status="missing")
                continue
            if current and current.status == "edited" and not request.field_ids:
                results[field.id] = current
                continue
            if field.kind == "narrative":
                if request.narrative_prompt:
                    result = self._narrative(
                        field, profile, memory, request.narrative_prompt, request, previous_topic,
                        current.value if current else None, [fact.id for fact in current.sources] if current else (),
                        requirements=requirements,
                    )
                else:
                    result = DraftField(field=field, status="missing", note="작성할 자기소개 항목이나 주제를 선택해 주세요.")
            else:
                result = self._fill(field, records, fixture_ids)
            if record.format == "pdf" and result.value and not _fits_pdf(result.value):
                result = DraftField(field=field, status="unsupported", suggestions=[*result.sources, *result.suggestions],
                                    note="이 버전의 PDF 내보내기는 기본 라틴 문자만 지원해요. 값은 DOCX 또는 JSON 초안에서 작성해 주세요.")
            results[field.id] = result
        return Draft(revision=(record.draft.revision if record.draft else 0) + 1,
                     fields=list(results.values()), mock_data=profile.mock)

    def generate(self, user_id: str, document_id: str, request: DraftRequest) -> Draft:
        state = self.store.get_state(user_id)
        record = state.documents.get(document_id)
        if not record:
            raise NotFound("문서를 찾을 수 없어요.")
        draft = self.prepare(record, self.data.get_profile(user_id), state.memory, request)
        record.draft = draft
        self.store.save_state(user_id, state)
        return draft

    def edit(self, user_id: str, document_id: str, request: DraftEdit) -> Draft:
        record = self.get(user_id, document_id)
        current = record.draft
        if current is None or current.revision != request.revision:
            raise Conflict("문서 초안이 변경됐어요. 새로 조회한 뒤 다시 시도해 주세요.")
        if not request.values.keys() <= {field.field.id for field in current.fields}:
            raise NotFound("양식에 없는 항목이에요.")
        fields = []
        for field in current.fields:
            if field.field.id in request.values:
                value = request.values[field.field.id]
                if record.format == "pdf" and not _fits_pdf(value):
                    raise AssistantError("이 버전에서 PDF에 입력할 수 있는 문자는 기본 라틴 문자예요.")
                field = DraftField(field=field.field, status="edited", value=value or None,
                                   note="사용자가 직접 입력한 초안 값이에요.")
            fields.append(field)
        draft = current.model_copy(update={"revision": current.revision + 1, "fields": fields})
        self.store.save_draft(user_id, document_id, draft)
        return draft

    def download(self, user_id: str, document_id: str) -> tuple[str, str, bytes]:
        record = self.get(user_id, document_id)
        if not record.draft:
            raise Conflict("초안을 먼저 작성해 주세요.")
        original = self.store.get_original(user_id, document_id)
        values = {
            item.field.id: item.value for item in record.draft.fields
            if item.status in ("filled", "draft", "edited") and item.value
        }
        prefix = "assistant-mock" if record.draft.mock_data else "assistant"
        return (f"{prefix}-draft.{record.format}", MIME_TYPES[record.format],
                render_template(record.format, original, values))


def reference(record: DocumentRecord) -> DocumentReference:
    draft = record.draft
    if not draft:
        return DocumentReference(id=record.id, revision=0, missing=[field.label for field in record.fields])
    return DocumentReference(
        id=record.id, revision=draft.revision,
        filled=[item.field.label for item in draft.fields if item.status in ("filled", "draft", "edited") and item.value],
        needs_confirmation=[item.field.label for item in draft.fields if item.status == "confirmation" or item.suggestions
                            and item.status != "unsupported"],
        missing=[item.field.label for item in draft.fields if item.status == "missing" or item.status == "edited" and not item.value],
        unsupported=[item.field.label for item in draft.fields if item.status == "unsupported"],
    )
