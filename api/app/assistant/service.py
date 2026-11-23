"""Application service for authenticated career chat and document follow-ups."""

import hashlib
import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable

from .advice import (
    asks_about_previous_skill, asks_for_career_fit, asks_for_catalog_order, career_context, career_fit_note,
    catalog_relationship_answer, compares_careers,
    compares_skill_nodes, complementary_skill_advice, learning_context, names_previous_topic, needs_related_questions,
    skill_tree_comparison, tree_comparison_answer,
)
from .context import describe_opportunity, select_opportunities
from .contracts import (
    EXPERIENCE_KINDS, CareerRole, ChatRequest, ChatResult, Conversation, DraftRequest, Fact, MemoryEdit, Screen, Turn,
)
from .documents import DocumentService, reference
from .errors import AssistantError, Conflict, ModelInvalidResponse, ModelUnavailable, NotFound
from .history import (
    append_turn, conversation_secrets, model_history, practice_context, recent_consultation_answers, recent_example_names,
    safe_history,
)
from .memory import (
    MEMORY_LIMIT, SCHEMA as MEMORY_SCHEMA, SINGLE_VALUES, MemoryDiagnostic, asks_to_remember, effective_facts, extract_updates,
    extraction_context, identity, manual_fact, needs_extraction, read_updates, reconcile,
)
from .model import LanguageModel, generate_for, model_phase, model_request
from .narrative import restricts_sources
from .practice import practice_request, practice_schema, render_practice, time_limit
from .privacy import catalog_text, model_fact, provenance, redact, redact_secrets, secret_values, shareable
from .prompts import ANSWER_SCHEMA, CONSULTATION, MEMORY, OPPORTUNITY, PRACTICE, SKILL, enum_array, object_schema
from .recall import asks_for_user_memory, describe_user_fact, user_memory_answer, without_unconfirmed_ack
from .repository import AssistantStore, CareerData
from .response_style import concise_consultation, draft_note, public_consultation
from .skill_context import mentioned, skill_payload

_MAX_CONVERSATIONS = 32
_DOC_SUBJECT = re.compile(r"이력서|자기\s*소개|지원서|양식|문서|초안|지원\s*(?:동기|직무)|자소서|(?:이|첨부한)\s*파일")
_DOC_REVIEW = re.compile(r"부족|누락|비어|확인|보여|필요")
_DOC_REVIEW_FOLLOWUP = re.compile(r"^(?:그럼\s*)?(?:어떤|무슨)\s*(?:정보|항목|필드)가?\s*(?:부족|누락|비어)")
_DOC_NARRATIVE = re.compile(r"자기\s*소개|지원\s*동기|기술\s*역량.*(?:작|써)|자소서|경험.*(?:중심|문항).*(?:작|써)")
_CORRECTION = re.compile(r"정정|사실|아니라|아니고|변경|바꿨|취소|삭제|말고|착각")
_ACTION_REQUEST = r"\s*(?:해|부탁|(?:을\s*)?요청|할\s*수\s*있)"
_REWRITE = re.compile(rf"다시\s*(?:한\s*번\s*)?(?:써|작성)|재작성{_ACTION_REQUEST}")
_DOC_REVISION = re.compile(
    rf"{_REWRITE.pattern}|(?:수정|변경|반영|추가|요약|축약|축소|단축|압축){_ACTION_REQUEST}|"
    r"다듬어|고쳐|줄이|줄여|늘려|바꿔|넣어|짧게\s*써|간결하게\s*써"
)
_DOC_WRITE = re.compile(rf"작성{_ACTION_REQUEST}|(?:써|적어|만들어)\s*(?:줘|주|줄)|채워|자동\s*입력|초안(?:을|이)?\s*$")
_DOC_GUIDANCE = re.compile(r"(?:작성|쓰는|수정하는)\s*(?:법|방법|요령)|어떻게\s*(?:작성|써야|쓰)|무슨\s*(?:뜻|의미)")
_PREVIOUS_DRAFT = re.compile(r"(?:방금|아까|이전에?|앞서|위에서).{0,26}(?:초안|지원\s*동기|자기\s*소개|자소서)|(?:그|이)\s*초안")
_DISCUSSED_FACTS = re.compile(r"(?:방금|아까|이전에?|앞서)\s*(?:이야기|말|정했|정한|알려)")
_BRIEF_REVISION = re.compile(
    r"^(?:(?:그럼|좀|조금|더|다시|이걸|그걸|문장을|[0-9]+\s*자\s*(?:이내로|이하로|정도로|로)?)\s*)*"
    rf"(?:짧게|길게|간결하게|줄여|줄이|늘려|고쳐|다듬어|(?:재작성|수정|요약|축약|축소|단축|압축){_ACTION_REQUEST}|써\s*(?:줘|주|줄))"
)
_DOC_FIELD_EDIT = re.compile(r"(?:넣어|추가\s*해|반영\s*해|채워)")
_FILE_REFERENCE = re.compile(r"이력서|지원서|양식|문서|파일")
_FRESH_DRAFT = re.compile(r"새로|새로운|별개로|처음부터")
_DIRECT_REQUEST = re.compile(
    r"[?？]\s*$|뭐야|뭔가|뭐지|무엇|어떤|어느|어떻게|알려|설명해|추천해|비교해|보여\s*줘"
)
_EXPERIENCE_CLAIM = re.compile(r"참여했|맡았|담당했|구현했|만들었|수료했|인턴을 했|프로젝트를 했")
_DRAFT_FACT = re.compile(
    rf"{_EXPERIENCE_CLAIM.pattern}|취득했|(?:관심|흥미)(?:이|가)?\s*있|"
    r"(?:준비|공부)\s*(?:중이(?:야|에요|예요|다|고|지만)|중입니다|하고\s*있)|학과\s*학생"
)
_OPPORTUNITY_REFERENCE = re.compile(r"공고|모집|접수|마감|지원\s*자격")
_MOCK_ENROLLMENT = re.compile(
    r"가톨릭대학교(?:에|의)?\s*(?:등록된|재학\s*중인)|"
    r"가톨릭대학교.{0,24}(?:재학\s*중이에요|학생으로\s*확인|등록\s*기록에\s*따르면)"
)
_MODEL_SOURCE_LABELS = {
    "fixture": "가상 예시", "fixtures": "가상 예시", "facts": "기록된 정보", "provenance": "출처",
    "mockprofile": "가상 프로필",
    "user_statement": "사용자가 직접 말한 내용", "verified": "공식 확인 기록", "registered": "프로필 등록 정보",
}
_MODEL_SOURCE_LABEL = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(_MODEL_SOURCE_LABELS) + r")(?![A-Za-z0-9_])", re.I)
_DOC_FIELDS = {
    "project": "프로젝트", "certification": "자격증", "career": "경력",
    "internship": "인턴", "award": "수상", "activity": "활동",
    "training": "교육", "education": "학력", "skill": "기술",
}
_DOC_PREPARATION = {
    "documents": "공고에 명시된 서류를 정리하고 제출 양식을 확인해 보세요.",
    "conditions": "확인이 필요한 조건은 원문이나 담당 기관에서 확인해 보세요.",
    "schedule": "마감 전에 원문에서 접수 일정과 정정 공지 여부를 확인해 보세요.",
}


def _utc_now():
    return datetime.now(timezone.utc)


def _recent_mentions(conversation: Conversation) -> list[str]:
    return [turn.message for turn in conversation.turns[-2:]
            if turn.memory_evidence or not (turn.narrative_prompt or turn.result.document)]


def _without_secrets(facts: list[Fact], secrets: set[str]) -> list[Fact]:
    return [fact for fact in facts if all(redact_secrets(value, known=secrets) == value
                                         for value in (fact.value, fact.detail or ""))]


def _request_clause(message: str) -> str:
    # A line wrap can split the object from its verb. A trailing edit condition
    # inherits the object of the main request instead of replacing it.
    text = " ".join(message.split())
    clauses = re.split(r"(?<=[.!?。？！])(?=\s|[가-힣])\s*", text)
    followup = None
    for clause in reversed(clauses):
        if asks_to_remember(clause):
            return clause
        if _writing_command(clause):
            if _DOC_SUBJECT.search(clause) or _DOC_NARRATIVE.search(clause):
                return clause
            followup = followup or clause
        elif _DIRECT_REQUEST.search(clause):
            return clause
    return followup or clauses[-1]


def _writing_command(clause: str) -> bool:
    return bool(
        not _DOC_GUIDANCE.search(clause) and (_DOC_WRITE.search(clause) or _DOC_REVISION.search(clause))
        and (not restricts_sources(clause) or _DOC_SUBJECT.search(clause) or _DOC_NARRATIVE.search(clause))
    )


def _has_new_draft_evidence(message: str) -> bool:
    clauses = re.split(r"(?<=[.!?。？！])(?=\s|[가-힣])|[\n,]", message)
    return any(
        _DRAFT_FACT.search(clause) and not _writing_command(clause) and needs_extraction(clause)
        for clause in clauses
    )


def _filtered_facts(facts: list[Fact], message: str, skill, fixture_ids: set[str]) -> list[dict]:
    target = identity(message)
    prerequisite = {identity(value) for value in skill.prerequisites} if skill else set()
    relevant = {
        "goal": r"목표|취업|창업|진로", "certification": r"자격증|취득|[A-Z]{2,}",
        "project": r"프로젝트|경험|이력", "internship": r"인턴|경험|이력",
        "job": r"근무|경험|이력", "education": r"학력|학과", "training": r"교육|학습",
        "award": r"수상|이력", "activity": r"활동|이력", "skill": r"스킬|기술|공부|학습|배워|역량",
    }

    def priority(fact):
        name = identity(fact.value)
        if name in prerequisite or (len(name) >= 2 and name in target):
            return 0
        if re.search(relevant.get(fact.kind, r"(?!)"), message):
            return 1
        if (fact.kind in ("goal", "department", "grade", "interest", "study_time", "skill", "certification")
                or skill and fact.kind in EXPERIENCE_KINDS and fact.progress == "not_held"):
            return 2
        return 3

    comparison = compares_careers(message)
    candidates = sorted((fact for fact in facts if shareable(fact)), key=lambda fact: (
        fact.id in fixture_ids,
        comparison and fact.kind not in ("interest", "goal", "skill"),
        fact.kind != "goal", priority(fact), fact.id in fixture_ids,
    ))
    chosen = [fact for fact in candidates if priority(fact) < 3][:10]
    compact = [model_fact(fact, fixture=fact.id in fixture_ids) for fact in chosen]
    for item in compact:
        if "detail" in item:
            item["detail"] = item["detail"][:160]
    return compact


class AssistantService:
    def __init__(self, data: CareerData, store: AssistantStore, model: LanguageModel,
                 clock: Callable[[], datetime] = _utc_now):
        self.data = data
        self.store = store
        self.model = model
        self.clock = clock
        self.documents = DocumentService(data, store, model)

    def memory(self, user_id: str) -> list[Fact]:
        state = self.store.get_state(user_id)
        secrets = set().union(*(conversation_secrets(item) for item in state.conversations.values()))
        return [fact for fact in _without_secrets(state.memory, secrets) if shareable(fact)]

    def edit_memory(self, user_id: str, memory_id: str, edit: MemoryEdit) -> Fact:
        state = self.store.get_state(user_id)
        for index, fact in enumerate(state.memory):
            if fact.id == memory_id:
                changed = manual_fact(edit, memory_id)
                if not shareable(changed):
                    raise AssistantError("이 정보는 진로 기억에 저장할 수 없어요.")
                if any(other.id != fact.id and other.kind == edit.kind
                       and (edit.kind in SINGLE_VALUES or identity(other.value) == identity(edit.value))
                       for other in state.memory):
                    raise Conflict("같은 기억이 이미 있어요.")
                state.memory[index] = changed
                self.store.save_state(user_id, state)
                return changed
        raise NotFound("저장된 기억을 찾을 수 없어요.")

    def add_memory(self, user_id: str, edit: MemoryEdit) -> Fact:
        state = self.store.get_state(user_id)
        fact = manual_fact(edit)
        if not shareable(fact):
            raise AssistantError("이 정보는 진로 기억에 저장할 수 없어요.")
        if len(state.memory) >= MEMORY_LIMIT:
            raise Conflict("보관할 수 있는 기억 수에 도달했어요.")
        if any(other.kind == fact.kind and (fact.kind in SINGLE_VALUES or identity(other.value) == identity(fact.value))
               for other in state.memory):
            raise Conflict("같은 기억이 이미 있어요. 해당 항목을 수정해 주세요.")
        state.memory.append(fact)
        self.store.save_state(user_id, state)
        return fact

    def delete_memory(self, user_id: str, memory_id: str) -> None:
        state = self.store.get_state(user_id)
        retained = [item for item in state.memory if item.id != memory_id]
        if len(retained) == len(state.memory):
            raise NotFound("저장된 기억을 찾을 수 없어요.")
        state.memory = retained
        self.store.save_state(user_id, state)

    def history(self, user_id: str, conversation_id: str) -> Conversation:
        data = self.store.get_state(user_id).conversations.get(conversation_id)
        if data is None:
            raise NotFound("대화를 찾을 수 없어요.")
        return safe_history(data, conversation_secrets(data))

    def _draft_requirements(self, profile, memory, message, previous, record=None):
        previous_text = previous.result.answer if previous else None
        if record and record.draft and previous:
            previous_text = next((item.value for item in record.draft.fields
                                  if item.field.id in previous.narrative_field_ids), None)
        return self.documents.narrative_brief(
            profile, message, memory, previous_topic=previous.narrative_prompt if previous else "",
            previous_text=previous_text, previous_context=previous.narrative_context if previous else None,
        )

    def _document_answer(self, record, profile, memory, message, prior_narrative, *, narrative, review, requirements,
                         repeating_prompt=False):
        prior_topic = prior_narrative.narrative_prompt if prior_narrative else ""
        revision = bool(prior_topic)
        chosen = []
        if not review or not record.draft:
            field_kinds = {kind for kind, term in _DOC_FIELDS.items() if term in message}
            chosen = [
                field.id for field in record.fields
                if (narrative and field.kind == "narrative") or (not narrative and field.kind in field_kinds)
                or (not narrative and field.kind == "career" and "internship" in field_kinds)
            ]
            if revision and prior_narrative.narrative_field_ids:
                chosen = prior_narrative.narrative_field_ids
            if (narrative or field_kinds) and not chosen:
                return "이 양식에서 요청한 입력 항목을 찾지 못했어요.", reference(record), [], False
            if not review:
                record.draft = self.documents.prepare(
                    record, profile, memory,
                    DraftRequest(field_ids=chosen or None, narrative_prompt=message if narrative else None),
                    previous_topic=prior_topic if revision else "",
                    requirements=requirements,
                )
        result = reference(record)
        lines = [f"{'가상 사용자 데이터로 ' if profile.mock else ''}문서 초안을 확인했어요."]
        for heading, fields in (
            ("입력된 항목", result.filled), ("확인할 항목", result.needs_confirmation),
            ("비어 있는 항목", result.missing), ("형식 제한이 있는 항목", result.unsupported),
        ):
            if fields:
                lines.append(f"{heading} · {', '.join(fields)}")
        narrative_results = [item for item in record.draft.fields if item.field.id in chosen] if (
            narrative and record.draft
        ) else []
        for item in narrative_results:
            note = draft_note(item.note, repeating=bool(
                item.status == "draft" and repeating_prompt
                and item.field.id in prior_narrative.narrative_field_ids
            ))
            if note:
                lines.append(note)
        awaiting_evidence = any(item.status == "missing" or (item.note or "").endswith("?")
                                for item in narrative_results)
        return "\n".join(lines), result, chosen if narrative else [], awaiting_evidence

    def _opportunity_answer(self, message, opportunities):
        include_description = bool(re.search("무슨|내용|역할|활동|혜택|무엇|지원금|추천", message))
        answer = "\n\n".join(describe_opportunity(item, include_description) for item in opportunities)
        search = getattr(self.data, "search", None)
        if search is not None:
            from ..career.opportunity_rag import explain, format_explanation
            from .service_data import RETRIEVAL_QUERY
            explanation_model = self.model if re.search("추천|이유|연결|맞|근거", message) else None
            explanation = explain(search, explanation_model, RETRIEVAL_QUERY.get() or message,
                                  [item.id for item in opportunities])
            grounded = format_explanation(explanation)
            if grounded:
                answer += "\n\n목표와 연결되는 공고 근거\n" + grounded
            return answer
        if re.search("준비|추천|방법|계획", message):
            try:
                suggested = generate_for(
                    self.model, "opportunity", OPPORTUNITY, {"question": redact(message), "options": _DOC_PREPARATION,
                                  "opportunities": [item.model_dump(mode="json", include={
                                      "title", "type", "open", "conditions", "documents",
                                  }) for item in opportunities]},
                    object_schema(preparationIds=enum_array(_DOC_PREPARATION)),
                ).get("preparationIds", [])
            except ModelUnavailable:
                suggested = []
            if isinstance(suggested, list):
                selected = list(dict.fromkeys(key for key in suggested[:2]
                                              if isinstance(key, str) and key in _DOC_PREPARATION))
                if selected:
                    answer += "\n\n" + "\n".join(_DOC_PREPARATION[key] for key in selected)
        return answer

    def _consult(self, message, profile, facts, conflicting, conversation, node, screen, object_names, *,
                 graph=None, previous_node=False, role=None, comparison_skill=None, tree_comparison=None,
                 server_relationships=False, extraction=None, practice=None, prior_practice=None):
        prompt = f"{CONSULTATION}\n\n{SKILL}" if screen.page == "tree" or node or tree_comparison else CONSULTATION
        with model_phase("consultation_context"):
            fixture_ids = {fact.id for fact in profile.facts} if profile.mock else set()
            roles = career_context(self.data, profile, facts, message, screen.job_id)
            coaching_topic = f"{message}\n{prior_practice[0].message}" if prior_practice else message
            coaching = learning_context(coaching_topic, facts, node, graph, fixture_ids)
            if practice:
                prompt += f"\n\n{PRACTICE}"
            context = {
                "message": redact(message, object_names=object_names),
                "facts": _filtered_facts(facts, message, node, fixture_ids),
                "conversation": model_history(conversation, object_names=object_names, compact=compares_careers(message),
                                              practice=prior_practice),
                "page": redact(screen.page),
                "mockProfile": profile.mock,
            }
        if node:
            key = "priorSkill" if previous_node else "selectedSkill" if screen.skill_id else "referencedSkill"
            context[key] = graph["nodes"][0] if graph else skill_payload(node)
        if comparison_skill:
            context["comparisonSkill"] = comparison_skill
        if tree_comparison:
            context["skillTreeComparison"] = tree_comparison
        if role:
            context["viewedRole"] = {"name": catalog_text(role.name), "purpose": catalog_text(role.description)[:360],
                                     "mock": role.mock}
        if graph:
            context["skillGraph"] = graph
        if server_relationships:
            context["serverShowsRelationships"] = True
        if roles:
            context["careerCandidates"] = roles
        if coaching:
            context["learning"] = coaching
        if practice:
            context["practiceRequest"] = practice.context()
        if conflicting:
            context["supersededForAdvice"] = [
                model_fact(fact, fixture=fact.id in fixture_ids) for fact in conflicting if shareable(fact)
            ][:6]
        if conversation.example_names:
            context["exampleNames"] = list(conversation.example_names)
        schema = ANSWER_SCHEMA
        if extraction is not None:
            context["memoryContext"] = extraction
            prompt += (
                "\n\nAlso return independent memory updates using the rules below. Use the student's explicit "
                "statements in the latest message for your comparison, even when the older profile differs. "
                "The requested comparison is not a declared goal.\n\n" + MEMORY
            )
            schema = object_schema(**ANSWER_SCHEMA["properties"], **MEMORY_SCHEMA["properties"])
        schema = practice_schema(practice, schema)
        result = generate_for(self.model, "consultation_with_memory" if extraction is not None else "consultation",
                              prompt, context, schema)
        answer = result.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ModelInvalidResponse("Gemini 답변의 answer 필드를 확인할 수 없어요.",
                                       operation="consultation", reason="answer_schema")
        if practice:
            if server_relationships:
                answer = complementary_skill_advice(answer)
            answer = render_practice(result, answer, practice, schema)
        if profile.mock and _MOCK_ENROLLMENT.search(answer):
            answer = "학교 등록 여부를 확인할 수 있는 기록이 없어요. 가상 프로필을 기준으로 상담을 이어갈 수 있어요."
        nodes = [context[key] for key in ("selectedSkill", "referencedSkill", "priorSkill", "comparisonSkill") if key in context]
        nodes.extend(graph["nodes"] if graph else [])
        for tree in tree_comparison["trees"] if tree_comparison else []:
            nodes.extend(tree["nodes"])
        labels = {key: name for entry in nodes for key, name in (
            (entry.get("skillId"), entry.get("skillName")), (entry.get("jobId"), entry.get("jobName")),
        ) if key and name}
        if role:
            labels[role.id] = catalog_text(role.name)
        answer = public_consultation(answer, labels)
        answer = _MODEL_SOURCE_LABEL.sub(lambda match: _MODEL_SOURCE_LABELS[match[0].lower()], answer)
        answer = redact(answer.strip(), object_names=object_names)
        return answer if practice else answer[:4000], roles, result

    @staticmethod
    def _certificate_answer(message, profile, memory):
        recall = re.compile(r"공식|검증|확인|주장|말했|말만|기억|(?:내가|제가)\s*(?:취득|준비|땄)|(?:내|제)\s*자격증")
        if not recall.search(message) or re.search(
            r"추천|하면|조건|난이도|프로젝트|방법|작성|써\s*줘|도움|활용|실습|어떻게|적합", message,
        ):
            return None
        practice = practice_request(message)
        if practice and practice.mode == "plan":
            return None
        facts = [*profile.facts, *memory]
        certificates = [item for item in facts if item.kind == "certification"]
        named = [item for item in certificates if mentioned(item.value, message)]
        if not named and not re.search(r"자격증", message):
            return None
        items = named or (certificates if re.search("자격증", message) else [])
        fixture_ids = {fact.id for fact in profile.facts} if profile.mock else set()
        official = [item.value for item in items if provenance(item, item.id in fixture_ids) == "verified"
                    and item.progress not in ("preparing", "not_held")]
        fixture = [item.value for item in items if provenance(item, item.id in fixture_ids) == "fixture"
                   and item.source == "official" and item.progress not in ("preparing", "not_held")]
        unverified = [item.value for item in items if item.id not in fixture_ids and item.source != "official"
                      and item.progress not in ("preparing", "not_held")]
        lines = [
            "공식 확인 기록 · " + (", ".join(official) if official else "해당 기록이 없어요."),
            "확인이 필요한 기록 · " + (", ".join(unverified) if unverified else "해당 기록이 없어요."),
        ]
        if fixture:
            lines.append("가상 데이터의 공식 확인 기록 · " + ", ".join(fixture))
        for item in items:
            if item.id in fixture_ids:
                continue
            if item.progress == "preparing":
                lines.append(f"{item.value} · 준비 중이라고 말씀하셨어요. "
                             + ("공식 기록과 현재 진술이 서로 달라요." if item.value in official else "취득 기록은 없어요."))
            elif item.progress == "not_held":
                conflict = " 공식 기록과 현재 진술이 서로 달라요." if item.value in official else ""
                lines.append(f"{item.value} · 미취득으로 말씀하셨어요.{conflict}")
        return "\n".join(lines)

    @staticmethod
    def _prior_response(conversation, request, fingerprint):
        if request.request_id and conversation:
            for turn in conversation.turns:
                if turn.request_id == request.request_id:
                    if fingerprint != turn.request_fingerprint:
                        raise Conflict("이미 사용한 요청 ID예요.")
                    return turn.result
        return None

    def _skill_context(self, screen, message, conversation, result, previous_selection):
        tree_lookup = getattr(self.data, "get_skill_tree", None)
        job_id, skill_id = (screen.job_id, screen.skill_id) if screen.page == "tree" else (None, None)
        prior = False
        if screen.page != "tree" and not (screen.document_id or screen.opportunity_id):
            prior_screens = [turn.context for turn in reversed(conversation.turns) if turn.context.page == "tree"]
            if names_previous_topic(message):
                for past in prior_screens:
                    if past.job_id and past.skill_id:
                        candidate = self.data.get_skill_node(past.job_id, past.skill_id)
                        if candidate and (mentioned(candidate.skill_name, message) or mentioned(candidate.skill_id, message)):
                            job_id, skill_id = past.job_id, past.skill_id
                            prior = True
                            break
            if not prior and prior_screens and asks_about_previous_skill(message):
                latest_tree = prior_screens[0]
                if latest_tree.job_id and latest_tree.skill_id:
                    job_id, skill_id = latest_tree.job_id, latest_tree.skill_id
                    prior = True
        tree = tree_lookup(job_id) if tree_lookup and job_id else None
        role_lookup = getattr(self.data, "list_career_roles", None)
        role = next((item for item in role_lookup() if item.id == job_id), None) if job_id and role_lookup and not skill_id else None
        if tree and not skill_id and not role and tree.nodes:
            first = next(iter(tree.nodes.values()))
            role = CareerRole(id=first.job_id, name=first.job_name, description=first.job_name, mock=first.mock)
        node = self.data.get_skill_node(job_id, skill_id) if job_id and skill_id else None
        if not prior and (job_id or skill_id) and not (role or node):
            result.context_issues.append("unknown_skill" if job_id and skill_id else "missing_skill_context")
        named = [item for item in tree.nodes.values() if mentioned(item.skill_name, message)
                 or mentioned(item.skill_id, message)] if tree and compares_skill_nodes(message) else []
        if not skill_id and len(named) >= 2:
            node = named[0]
        related_questions = []
        if node and needs_related_questions(message):
            for turn in reversed(conversation.turns[-3:]):
                if turn.context.page == "tree" and (
                    turn.context.job_id != job_id or turn.context.skill_id != skill_id
                ):
                    break
                if not turn.memory_evidence:
                    related_questions.append(turn.message)
        compared = None
        if node and (compares_skill_nodes(message) or any(compares_skill_nodes(text) for text in related_questions)):
            compared = self._comparison_skill(
                node, tree, message, related_questions, conversation, previous_selection, named,
            )
        references = (compared["skillId"],) if compared and compared["jobId"] == job_id else ()
        graph = tree.context(node.skill_id, message, related_questions, references=references) if (
            tree and node and node.skill_id in tree.nodes
        ) else None
        return node, graph, prior, role, compared

    def _comparison_skill(self, node, tree, message, related_questions, conversation, previous_selection, named):
        reference = "\n".join((message, *related_questions))
        current = node.job_id, node.skill_id
        if names_previous_topic(reference) or re.search(r"직전|방금|두\s*노드|둘\s*중", reference):
            screens = [previous_selection] if previous_selection else []
            screens.extend(turn.context for turn in reversed(conversation.turns) if turn.context.page == "tree")
            other = None
            for screen in screens:
                pair = screen.job_id, screen.skill_id
                if all(pair) and pair != current:
                    candidate = self.data.get_skill_node(*pair)
                    if candidate:
                        other = other or candidate
                        if mentioned(candidate.skill_name, reference) or mentioned(candidate.skill_id, reference):
                            other = candidate
                            break
            if other:
                get_tree = getattr(self.data, "get_skill_tree", None)
                previous_tree = get_tree(other.job_id) if get_tree else None
                if previous_tree and other.skill_id in previous_tree.nodes:
                    return previous_tree.node_payload(other.skill_id)
                return skill_payload(other)
        if tree:
            candidates = named or [item for item in tree.nodes.values() if mentioned(item.skill_name, reference)
                                   or mentioned(item.skill_id, reference)]
            other = next((item for item in candidates if item.skill_id != node.skill_id), None)
            if other:
                return tree.node_payload(other.skill_id)
        return None

    @model_request("chat")
    def chat(self, user_id: str, request: ChatRequest, *, memory_diagnostic: MemoryDiagnostic | None = None,
             previous_selection: Screen | None = None) -> ChatResult:
        with model_phase("storage_read"):
            state = self.store.get_state(user_id)
        conversation = state.conversations.get(request.conversation_id)
        fingerprint = None
        if request.request_id:
            request_data = request.model_dump_json()
            if previous_selection:
                request_data += "\n" + previous_selection.model_dump_json()
            fingerprint = hashlib.sha256(request_data.encode("utf-8")).hexdigest()
        if conversation is None:
            if len(state.conversations) >= _MAX_CONVERSATIONS:
                raise Conflict("보관할 수 있는 대화 수에 도달했어요.")
            conversation = Conversation()
        persisted = conversation
        secrets = secret_values(request.message) | conversation_secrets(conversation)
        if state.memory:
            for other_id, other in state.conversations.items():
                if other_id != request.conversation_id:
                    secrets.update(conversation_secrets(other))
        metadata = request.model_dump_json(exclude={"message"})
        if redact_secrets(metadata, known=secrets) != metadata:
            raise AssistantError("요청 식별자에는 비밀정보를 사용할 수 없어요.")
        conversation = safe_history(conversation, secrets)
        existing = self._prior_response(conversation, request, fingerprint)
        if existing:
            return existing
        screen, message = request.context, redact_secrets(request.message, known=secrets)
        object_names = recent_example_names(conversation, message)
        previous = conversation.turns[-1] if conversation.turns else None
        document_id = screen.document_id or (previous.topic_document_id if previous else None)
        record = state.documents.get(document_id) if document_id else None
        profile = self.data.get_profile(user_id)
        profile = profile.model_copy(update={"facts": _without_secrets(profile.facts, secrets)})
        result = ChatResult(answer="", conversation_id=request.conversation_id, mock_data=profile.mock)
        now = self.clock()
        topic_opportunity = previous.topic_opportunity_id if previous else None
        prior_narrative = next((turn for turn in reversed(conversation.turns) if turn.narrative_prompt
                                and turn.topic_document_id == document_id), None)
        inquiry = _request_clause(message)
        memory_recall = asks_for_user_memory(message)
        memory_requested = asks_to_remember(inquiry)
        comparison = compares_careers(message)
        current_skill = screen.page == "tree" and bool(screen.job_id or screen.skill_id)
        current_question = bool(_DIRECT_REQUEST.search(inquiry))
        named_document = bool(_DOC_SUBJECT.search(inquiry))
        document_reference = bool(_FILE_REFERENCE.search(inquiry))
        fresh_draft = bool(_FRESH_DRAFT.search(inquiry))
        brief_revision = bool(_BRIEF_REVISION.search(inquiry))
        can_use_previous = not (current_skill or screen.opportunity_id) and not fresh_draft
        previous_document = bool(can_use_previous and previous and previous.result.document)
        guidance = bool(_DOC_GUIDANCE.search(inquiry))
        writing = _writing_command(inquiry)
        review = not (guidance or writing) and bool(
            named_document and _DOC_REVIEW.search(inquiry)
            or (previous_document or screen.document_id) and _DOC_REVIEW_FOLLOWUP.search(inquiry)
        )
        explicit_narrative = writing and bool(_DOC_NARRATIVE.search(inquiry))
        follows_draft = not fresh_draft and bool(
            _PREVIOUS_DRAFT.search(inquiry)
            or explicit_narrative and (_REWRITE.search(inquiry) or _DISCUSSED_FACTS.search(message))
        )
        edit_draft = writing and not fresh_draft and bool(
            named_document and _DOC_REVISION.search(inquiry) or follows_draft and _DOC_REVISION.search(message)
            or brief_revision
        )
        if edit_draft and not document_id and not prior_narrative:
            prior_narrative = next((turn for turn in reversed(conversation.turns) if turn.narrative_prompt), None)
        supplied_evidence = bool(
            can_use_previous and not (current_question or writing or memory_requested or memory_recall)
            and previous and previous is prior_narrative
            and previous.awaiting_narrative_evidence and _EXPERIENCE_CLAIM.search(message)
        )
        revision = supplied_evidence or bool(
            prior_narrative and edit_draft and (named_document or follows_draft or can_use_previous)
        )
        if revision and not document_id and prior_narrative.topic_document_id:
            document_id = prior_narrative.topic_document_id
            record = state.documents.get(document_id)
        field_edit = bool(_DOC_FIELD_EDIT.search(inquiry) and any(term in inquiry for term in _DOC_FIELDS.values()))
        requested_document = bool(
            writing and (named_document or (previous_document or screen.document_id) and (field_edit or brief_revision))
            or review or revision and record
        )
        use_attachment = bool(
            document_reference or not fresh_draft and (
                screen.document_id or revision and record
                or previous_document and (not explicit_narrative or not prior_narrative)
            )
        )
        uploaded_document = bool(record and requested_document and use_attachment)
        standalone_narrative = not uploaded_document and not document_reference and (
            explicit_narrative or revision or writing and follows_draft
        )
        upload_request = requested_document and not uploaded_document and not standalone_narrative
        opportunity_question = bool(_OPPORTUNITY_REFERENCE.search(inquiry) or screen.opportunity_id and not comparison)
        narrative_fields, narrative_sources, narrative_prompt, awaiting_evidence = [], [], None, False

        if requested_document and use_attachment and screen.document_id and not record:
            raise NotFound("문서를 찾을 수 없어요.")
        updates = []
        original_memory = {fact.id: fact for fact in state.memory}
        memory = _without_secrets(state.memory, secrets)
        recent = _recent_mentions(conversation)

        def apply_updates(candidates):
            nonlocal memory
            with model_phase("memory_validation"):
                adjusted, questions = reconcile(message, candidates, state.memory, profile.facts, recent, memory_diagnostic,
                                                mock_profile=profile.mock)
            result.needs_confirmation = questions
            result.memory_updated = adjusted != state.memory
            state.memory = adjusted
            memory = _without_secrets(adjusted, secrets)

        combined = (
            not (uploaded_document or standalone_narrative or upload_request or current_skill
                 or opportunity_question or memory_recall or memory_requested)
            and comparison and needs_extraction(message) and not _CORRECTION.search(message)
        )
        if not combined:
            if (not (memory_recall or uploaded_document or standalone_narrative or upload_request)
                    or memory_requested or _has_new_draft_evidence(message)):
                updates = extract_updates(self.model, message, memory, recent, memory_diagnostic)
            apply_updates(updates)
        earlier_draft = prior_narrative if revision else None
        requirements = None
        if standalone_narrative or uploaded_document and not review and (explicit_narrative or revision):
            requirements = self._draft_requirements(
                profile, memory, "" if supplied_evidence else message, earlier_draft,
                record if uploaded_document else None,
            )
        repeating_prompt = bool(
            earlier_draft and requirements and not supplied_evidence and earlier_draft.awaiting_narrative_evidence
            and earlier_draft.narrative_context and earlier_draft.narrative_context.target_role == requirements.role
            and earlier_draft.narrative_context.question == requirements.question
        )
        if uploaded_document:
            result.answer, result.document, narrative_fields, awaiting_evidence = self._document_answer(
                record, profile, memory, message, earlier_draft,
                narrative=explicit_narrative or revision, review=review, requirements=requirements,
                repeating_prompt=repeating_prompt,
            )
            if narrative_fields:
                narrative_prompt = message
        elif standalone_narrative:
            narrative = self.documents.narrative(
                profile, message, memory,
                previous_topic=prior_narrative.narrative_prompt if revision else "",
                previous_text=prior_narrative.result.answer if revision else None,
                previous_ids=prior_narrative.narrative_source_ids if revision else (),
                requirements=requirements,
            ).draft
            note = draft_note(narrative.note, repeating=bool(
                repeating_prompt and narrative.status == "draft"
                and earlier_draft.result.answer.startswith("[AI 초안]")
            ))
            result.answer = "\n\n".join(part for part in (narrative.value, note) if part)
            narrative_prompt = message
            narrative_sources = [fact.id for fact in narrative.sources]
            awaiting_evidence = narrative.status == "missing" or (narrative.note or "").endswith("?")
        elif upload_request:
            result.answer = (
                "수정할 초안을 붙여 넣거나 작성할 직무와 문항을 알려주세요."
                if edit_draft and not document_reference and not screen.document_id
                else "이력서나 지원서 양식을 업로드한 뒤 작성할 문서를 선택해 주세요."
            )
        elif recall_answer := self._certificate_answer(inquiry, profile, memory):
            result.answer = "\n".join([recall_answer, *result.needs_confirmation])
            topic_opportunity = None
        elif memory_recall:
            result.answer = user_memory_answer(message, profile, memory)
            topic_opportunity = None
        elif memory_requested:
            saved = [fact for fact in memory if fact != original_memory.get(fact.id)]
            lines = ["다음 내용을 기억에 저장했어요. " + " ".join(describe_user_fact(fact) for fact in saved)] if saved else [
                "이번 요청에서 새로 저장된 내용은 없어요."
            ]
            if result.needs_confirmation:
                lines.extend(result.needs_confirmation)
            elif not saved:
                lines.append("기억할 내용이 있다면 본인의 진로 정보나 경험을 구체적으로 말씀해 주세요.")
            result.answer = "\n".join(lines)
        else:
            facts, conflicting = effective_facts(profile.facts, memory)
            fixture_ids = {fact.id for fact in profile.facts} if profile.mock else set()
            node, graph, prior, role, compared = self._skill_context(screen, message, conversation, result, previous_selection)
            past_jobs = [turn.context.job_id for turn in reversed(conversation.turns)
                         if turn.context.page == "tree" and turn.context.job_id]
            if previous_selection and previous_selection.job_id:
                past_jobs.insert(0, previous_selection.job_id)
            tree_comparison = skill_tree_comparison(self.data, message, screen.job_id, past_jobs)
            if node:
                object_names = (*object_names, node.skill_name, node.job_name, *node.prerequisites)
                if graph:
                    object_names = (*object_names, *(item["skillName"] for item in graph["nodes"]))
            if compared:
                object_names = (*object_names, compared["skillName"], compared["jobName"])
            if (comparison or tree_comparison) and not opportunity_question:
                opportunities, issue = [], None
            else:
                opportunity_topic = None if node and not opportunity_question else previous
                opportunities, issue = select_opportunities(
                    self.data, screen, message, facts, opportunity_topic, now, fixture_ids,
                )
            if issue:
                result.context_issues.append(issue)
            result.opportunities = opportunities
            if opportunities:
                result.mock_data |= any(item.mock for item in opportunities)
                topic_opportunity = opportunities[0].id if len(opportunities) == 1 else None
                result.answer = self._opportunity_answer(message, opportunities)
            elif issue == "unknown_opportunity":
                topic_opportunity = None
                result.answer = "이 공고를 찾지 못했어요. 공고를 다시 선택해 주세요."
                search = getattr(self.data, "search", None)
                selected_id = screen.opportunity_id or (previous.topic_opportunity_id if previous else None)
                if search is not None and selected_id:
                    from ..career.opportunity_rag import explain, format_explanation
                    from .service_data import RETRIEVAL_QUERY
                    _, postings = search.refresh()
                    posting = postings.get(selected_id)
                    if posting:
                        grounded = format_explanation(explain(search, None, RETRIEVAL_QUERY.get() or message,
                                                              [selected_id]))
                        topic_opportunity = selected_id
                        result.context_issues = ["unverified_opportunity_deadline"]
                        result.answer = (catalog_text(posting["title"]) + "\n모집 일정과 지원 자격은 원문에서 확인해 주세요."
                                         + ("\n\n" + grounded if grounded else ""))
            elif issue == "no_matching_opportunity":
                result.answer = "현재 제공된 공고에서 조건에 맞는 접수 중인 공고를 찾지 못했어요."
            elif result.context_issues:
                result.answer = "선택된 스킬을 확인하지 못했어요. 확인할 노드를 다시 선택해 주세요."
            else:
                result.mock_data |= bool(node and node.mock or role and role.mock or graph and graph["mock"]
                                         or compared and compared.get("mock"))
                if result.needs_confirmation and not result.memory_updated and not current_skill:
                    result.answer = "\n".join(result.needs_confirmation)
                practice, prior_practice = practice_context(conversation, message, screen)
                if practice and practice.daily_minutes is None:
                    saved_time = next((time_limit(fact.value, stored=True) for fact in memory if fact.kind == "study_time"), None)
                    if saved_time is not None:
                        practice = replace(practice, daily_minutes=saved_time)
                relationship = None
                if tree_comparison:
                    relationship = tree_comparison_answer(tree_comparison), len(tree_comparison["trees"]) == 2
                    result.mock_data |= any(item["mock"] for item in tree_comparison["trees"])
                elif graph:
                    relationship = catalog_relationship_answer(node, graph, message, compared)
                if not result.answer and relationship and not (practice or relationship[1] or result.memory_updated):
                    result.answer = relationship[0]
                if not result.answer:
                    extraction = extraction_context(message, memory, []) if combined else None
                    result.answer, roles, generated = self._consult(
                        message, profile, facts, conflicting, conversation, node, screen, object_names, graph=graph,
                        previous_node=prior, role=role, comparison_skill=compared, tree_comparison=tree_comparison,
                        server_relationships=bool(relationship), extraction=extraction,
                        practice=practice, prior_practice=prior_practice,
                    )
                    if combined:
                        updates = read_updates(generated, memory_diagnostic)
                        apply_updates(updates)
                        if result.memory_updated:
                            updated_facts, _ = effective_facts(profile.facts, memory)
                            roles = career_context(self.data, profile, updated_facts, message, screen.job_id)
                    if not result.memory_updated:
                        result.answer = without_unconfirmed_ack(result.answer)
                    result.mock_data |= any(item["mock"] for item in roles)
                    if comparison and not tree_comparison and asks_for_career_fit(message):
                        opening, evidence = career_fit_note(roles, result.answer)
                        result.answer = "\n\n".join(part for part in (opening, result.answer, evidence) if part)
                    if relationship:
                        advice = result.answer if practice else complementary_skill_advice(result.answer)
                        parts = ((relationship[0], advice) if not practice and asks_for_catalog_order(message)
                                 else (advice, relationship[0]))
                        result.answer = "\n\n".join(part for part in parts if part)
                    result.answer = concise_consultation(
                        result.answer, message, previous.result.answer if previous and not comparison else "",
                        recent_answers=recent_consultation_answers(conversation),
                        preserve_steps=practice is not None,
                    ) or "지금은 질문에 답하기 어려워요. 잠시 후 다시 시도해 주세요."

        if narrative_prompt and revision:
            narrative_prompt = f"{prior_narrative.narrative_prompt}\n{narrative_prompt}"[-2000:]

        result.answer = redact(redact_secrets(result.answer, known=secrets), object_names=object_names)
        result.needs_confirmation = [redact_secrets(item, known=secrets) for item in result.needs_confirmation]
        append_turn(persisted, Turn(
            timestamp=now, message=redact(message, object_names=object_names), result=result, context=screen,
            topic_opportunity_id=topic_opportunity, topic_document_id=document_id if uploaded_document else None,
            request_id=request.request_id, request_fingerprint=fingerprint,
            memory_evidence=bool(updates) or result.memory_updated,
            narrative_prompt=redact(narrative_prompt, object_names=object_names) if narrative_prompt else None,
            narrative_context=requirements.context() if narrative_prompt and requirements else None,
            narrative_field_ids=narrative_fields,
            narrative_source_ids=narrative_sources,
            awaiting_narrative_evidence=awaiting_evidence,
        ), view=conversation)
        state.conversations[request.conversation_id] = persisted
        try:
            with model_phase("storage_commit"):
                self.store.save_state(user_id, state)
        except Conflict:
            latest = self.store.get_state(user_id).conversations.get(request.conversation_id)
            if latest is not None:
                latest = safe_history(latest, secrets | conversation_secrets(latest))
            existing = self._prior_response(latest, request, fingerprint)
            if existing:
                return existing
            raise
        if memory_diagnostic is not None:
            memory_diagnostic.memory_committed = result.memory_updated
        return result


def chat(user_id, message, page="home", opportunity_id=None, job_id=None, skill_id=None, *, assistant=None):
    """Compatibility entry point for calls to the original CLI service."""
    if assistant is None:
        from .demo import build_demo
        assistant = build_demo(user_id)
    request = ChatRequest(message=message, context=Screen(
        page=page, opportunity_id=opportunity_id, job_id=job_id, skill_id=skill_id,
    ))
    return assistant.chat(user_id, request).answer


if __name__ == "__main__":
    from .demo import main

    main()
