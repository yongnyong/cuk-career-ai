"""Owned startup facts, deterministic task planning and conversational intake."""
import hashlib
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .errors import ModelUnavailable
from .startup_tasks import Task, artifact_types, goal_intent, task_for
from .startup_application import StartupApplication

FACT_FIELDS = ("idea", "customer", "artifacts", "goal", "action")
_LOGGER = logging.getLogger(__name__)


class PlanEvidence(BaseModel):
    posting_id: str
    version: int
    title: str
    quote: str
    source_url: str


class SelectedOpportunity(BaseModel):
    id: str
    version: int
    title: str
    source_url: str
    documents: list[PlanEvidence] = Field(default_factory=list)


class PlanNode(BaseModel):
    id: str
    action: str
    title: str
    completion: str
    reason: str
    completed: bool = False
    active: bool = True
    reuse: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    project_id: str = ""
    goal_id: str = ""
    output: str = ""
    stage: int = 2
    evidence: list[PlanEvidence] = Field(default_factory=list)


class StartupPlan(BaseModel):
    idea: str = ""
    customer: str = ""
    artifacts: str = ""
    goal: str = ""
    action: str = ""
    nodes: list[PlanNode] = Field(default_factory=list)
    turns: int = 0
    project_id: str = ""
    goal_id: str = ""
    opportunity: SelectedOpportunity | None = None
    application: StartupApplication | None = None


class PlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    fields: dict[str, str] = Field(default_factory=dict, max_length=5)
    node_id: str | None = None
    completed: bool | None = None
    new_project: bool = False
    opportunity_id: str | None = None


def _key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _clean(text: str) -> str:
    from .privacy import redact
    return redact(text).strip()[:240]


def update_plan(plan: StartupPlan, fields: dict[str, str], *, new_project: bool = False) -> StartupPlan:
    """Recompute from merged facts. Arrival order never determines the chosen task."""
    result = plan.model_copy(deep=True)
    previous_goal = plan.goal
    if new_project:
        result.project_id = uuid4().hex[:16]
        result.customer = ""
        result.artifacts = ""
        result.goal = ""
        result.action = ""
        result.opportunity = None
        result.application = None
    for key in FACT_FIELDS:
        if key in fields:
            setattr(result, key, _clean(fields[key]))

    # Legacy nodes retain their public IDs and completed snapshots.
    if not result.project_id and result.idea:
        result.project_id = _key(result.idea)
        legacy_id = "SUP-" + _key(plan.idea + "|" + plan.customer + "|" + (
            "choose_opportunity" if plan.action == "competition" else plan.action))
        for node in result.nodes:
            if node.id == legacy_id:
                node.project_id = result.project_id
                node.goal_id = _key(result.project_id + "|" + plan.goal)
                if node.action in {"demo", "prototype", "customer", "preorder", "launch", "choose_opportunity"}:
                    task = task_for(plan, node.action)
                    node.output = task.output
                    node.stage = task.stage

    if result.goal != previous_goal or new_project:
        result.opportunity = None
    result.goal_id = _key(result.project_id + "|" + result.goal)

    # goal text and optional intent are interpreted identically for chat and manual edits.
    hint = fields.get("action", result.action) if result.goal == previous_goal else fields.get("action", "")
    result.action = goal_intent(result.goal, hint)
    for node in result.nodes:
        node.active = False
    if not result.idea or not result.customer or not result.goal:
        result.nodes = [node for node in result.nodes if node.completed]
        return result

    available = artifact_types(result.artifacts)
    completed = [node for node in result.nodes if node.completed and node.project_id == result.project_id]
    available.update(node.output for node in completed)
    action = result.action
    if action == "meeting":
        action = "demo" if "prototype" in available else "customer"
    if action == "competition":
        action = "choose_opportunity"

    tasks = []
    if action == "demo" and "prototype" not in available:
        tasks.append(task_for(result, "prototype"))
    tasks.append(task_for(result, action))
    evidence_by_task = {}
    if action == "choose_opportunity" and result.opportunity:
        tasks = []
        for doc in result.opportunity.documents:
            task_action = "submission-" + _key(doc.title)
            tasks.append(Task(task_action, f"{result.opportunity.title} · {doc.title} 준비",
                f"{result.idea}와 {result.customer}에 맞춰 {doc.title}를 작성하고 공고의 지정 양식·제출 방법과 대조한 파일을 저장하세요.",
                "submission", 4, ("customer_demo", "customer_findings", "offer")))
            evidence_by_task[task_action] = [doc]
        if not tasks:
            tasks.append(Task("verify_documents", f"{result.opportunity.title} 제출물 원문 확인",
                "공고의 첨부파일에서 제출자료 목록과 지정 양식을 확인하고 원문 링크를 기록하세요.",
                "document_list", 4))

    if result.application and result.action == "competition" and result.application.goal_id == result.goal_id:
        # Starting this form explicitly chooses the named demonstration target.
        tasks = [task for task in tasks if task.action != "choose_opportunity"]
        if not result.application.feedback:
            tasks.append(Task("application_feedback", "신청서에 반영할 학생 피드백 기록",
                f"{result.customer}에게 현재 서비스 사용의 어려움을 확인하고 들은 반응을 신청서 초안의 고객 피드백에 저장하세요.",
                "customer_findings", 2))
        tasks.append(Task("application_draft", "글로벌 창업경진대회 신청서 초안 작성",
            "아이템명·아이템 개요·문제 인식의 초안을 작성하고 팀 자료와 대조해 저장하세요.",
            "application_draft", 4))

    old_nodes = result.nodes
    active_nodes = []
    for task in tasks:
        scope = result.goal_id
        if result.opportunity:
            scope += "|" + result.opportunity.id + "|" + str(result.opportunity.version)
        existing = next((node for node in old_nodes if node.project_id == result.project_id
                         and node.goal_id == scope and node.action == task.action), None)
        if existing:
            node = existing
        else:
            node = PlanNode(id="SUP-" + _key(result.project_id + "|" + scope + "|" + task.action),
                            action=task.action, title=task.title, completion=task.completion, reason="",
                            project_id=result.project_id, goal_id=scope, output=task.output, stage=task.stage)
        node.active = True
        if not node.completed:
            # Prefer the latest completed result for each input type. Never connect unrelated projects.
            providers = [*active_nodes, *completed]
            reuse = []
            required = []
            for input_type in task.uses:
                provider = next((n for n in providers if n.id != node.id and n.output == input_type), None)
                if provider:
                    reuse.append(provider.id)
                    if input_type in task.requires and not provider.completed:
                        required.append(provider.id)
            node.title = task.title
            node.completion = task.completion
            node.reason = f"‘{result.goal}’ 목표를 위해 ‘{task.title}’를 추천해요."
            if result.artifacts:
                node.reason += f" 보유한 ‘{result.artifacts}’을 활용할 수 있어요."
            node.reuse = list(dict.fromkeys(reuse))
            node.requires = required
            node.evidence = evidence_by_task.get(task.action, [])
        active_nodes.append(node)
    active_ids = {node.id for node in active_nodes}
    result.nodes = active_nodes + [node for node in old_nodes if node.completed and node.id not in active_ids]
    return result


def is_plan_message(message: str) -> bool:
    """Only explicit own updates may divert normal chat to startup intake."""
    if re.search(r"만약|예를\s*들|다른\s*팀|친구.{0,6}(?:팀|아이디어)|[?？]", message):
        return False
    if re.search(r"안\s*(?:나가|할|하|낼)|않|생각이\s*없|계획이\s*없|취소", message):
        return False
    return bool(re.search(r"목표.*(?:바꾸|변경)|이제.*(?:출시|신청|낼|보여|미팅)|"
                          r"(?:선주문|대회|지원사업|출시|고객|시연).*(?:할래|싶|낼래|신청|준비|보여)|"
                          r"아이디어.*(?:바꿔|변경)|(?:고객|시제품|도안).*(?:있|바꿔)", message))


def extract_fields(message: str, plan: StartupPlan, model=None, *, expected: str | None = None) -> dict[str, str]:
    if re.search(r"만약|예를\s*들|다른\s*팀|친구.{0,6}(?:팀|아이디어)|[?？]", message):
        return {}
    if re.search(r"(?:대회|지원사업|선주문|출시|시연).*(?:생각이\s*없|계획이\s*없|않|안\s*나가|취소)", message):
        return {}
    from .privacy import redact
    message = redact(message)
    if model:
        from .model import generate_for
        from .prompts import object_schema
        # Use the same Gemini responseSchema dialect as the working chat path.
        schema = object_schema(**{key: {"type": "STRING"} for key in FACT_FIELDS})
        schema["properties"]["action"]["enum"] = ["preorder", "demo", "launch", "competition", "customer", ""]
        try:
            current = {key: redact(getattr(plan, key)) for key in FACT_FIELDS}
            fields = generate_for(model, 'startup_intake',
                "학생 자신의 창업 정보에서 명시한 변경만 JSON으로 추출. 기존 값 반복 금지. "
                "가정·다른 팀·일반 질문은 빈 객체. 거절하거나 취소한 목표를 새 목표로 저장하지 않는다. "
                "goal은 교내/전국 등 대상과 시기를 보존한다. action은 목표 의도이며 보유 결과물로 추론하지 않는다. "
                "서비스를 기획·구상하는 설명도 idea로 추출한다. asked_field는 직전 질문의 항목이다. "
                "명시되지 않거나 바뀌지 않은 항목은 빈 문자열. 각 값은 240자 이내. 사용자·보유 결과물·목표를 임의로 만들지 않는다.",
                {"message": message, "current": current, "asked_field": expected}, schema)
        except (OSError, ValueError, ModelUnavailable) as exc:
            _LOGGER.info('startup_intake extraction=failed error=%s', getattr(exc, 'code', type(exc).__name__))
            fields = None
        else:
            if (isinstance(fields, dict) and all(key in FACT_FIELDS and isinstance(value, str)
                    and len(value) <= 240 for key, value in fields.items())
                    and fields.get("action") in (None, "", "preorder", "demo", "launch", "competition", "customer")):
                result = {key: _clean(value) for key, value in fields.items() if value.strip()}
                _LOGGER.info('startup_intake extraction=%s fields=%d', 'model' if result else 'empty', len(result))
                return result
            _LOGGER.info('startup_intake extraction=invalid_result')
            fields = None

    # Fallback is used for an unavailable/invalid model, never for a valid empty extraction.
    if re.search(r"안\s*(?:나가|할|하|낼)|않|생각이\s*없|계획이\s*없|취소", message):
        return {}
    fields = {}
    if re.search(r"선주문|사전판매|예약판매|대회|지원사업|시연|보여|미팅|첫 고객|출시", message):
        fields["goal"] = message[:240]
    if "굿즈" in message:
        fields["idea"] = "동아리 굿즈" if "동아리" in message else "굿즈"
        if "동아리" in message:
            fields["customer"] = "동아리 학생"
    if re.search("상담.*요약", message):
        fields["idea"] = "상담 요약 AI"
    if "학원" in message or "원장" in message:
        fields["customer"] = "학원장"
    if re.search("디자인|도안", message):
        fields["artifacts"] = "없음" if re.search(r"없|아직|안\s*만들", message) else "디자인 도안"
    if "시제품" in message:
        fields["artifacts"] = "없음" if re.search(r"없|아직|안\s*만들", message) else "시제품"
    # Preserve an explicit product description without inventing its users or status.
    if not fields.get("idea") and re.search(r'서비스|웹사이트|웹\s*서비스|앱|플랫폼|제품|AI|비서|도구', message, re.I) and re.search(
            r'기획|만들|개발|구상|운영|제작', message):
        fields['idea'] = _clean(message)
    unresolved = bool(re.search(r'모르|미정|안\s*정|정하지|생각\s*중|아무거나|아직.*없', message)) or bool(
        re.fullmatch(r'(?:안녕|안녕하세요|네|응|그래|좋아|도와줘|시작|계속|다음|몰라|패스)[.! ]*', message.strip()))
    # Short replies belong to the question just asked, only during explicit intake.
    # Do not interpret a product/goal update as the answer to a different question.
    if expected and not fields and not unresolved:
        if expected == 'customer':
            fields['customer'] = _clean(message)
        elif expected == 'artifacts':
            fields['artifacts'] = _clean(message)
        elif expected == 'goal':
            fields['goal'] = _clean(message)
    if expected == 'artifacts' and re.search(r'없|아직.*기획|기획.*단계', message) and not fields.get('idea'):
        fields['artifacts'] = '없음' if re.search(r'없', message) else _clean(message)
    return fields


def select_opportunity(posting: dict | None) -> SelectedOpportunity:
    """Accept only the server's stored posting and exact source quotes."""
    from .errors import AssistantError
    if not posting or not posting.get("startup"):
        raise AssistantError("서버에 저장된 창업 공고를 선택해 주세요.")
    version = posting["versions"][-1]["version"]
    url = posting.get("applyUrl") or posting.get("source", {}).get("url", "")
    documents = []
    seen_titles = set()
    sections = [section.get("text", "") for section in posting.get("sections", [])]
    for requirement in posting["startup"].get("requirements", []):
        quote = requirement.get("evidence_quote", "").strip()
        title = requirement.get("document_type", "").strip()
        source_url = requirement.get("evidence_url") or url
        if (title not in seen_titles and requirement.get("necessity") == "required" and not requirement.get("condition_text")
                and requirement.get("stage", "application") == "application"
                and quote and title and any(quote in text for text in sections)
                and re.match(r"^https?://[^\s]+$", source_url)):
            documents.append(PlanEvidence(posting_id=posting["id"], version=version,
                title=title, quote=quote, source_url=source_url))
            seen_titles.add(title)
    return SelectedOpportunity(id=posting["id"], version=version, title=posting["title"],
                               source_url=url, documents=documents)


def chat_plan(service, user_id, request):
    from .contracts import ChatResult, Conversation, Turn
    from .errors import Conflict
    from .privacy import redact
    state = service.store.get_state(user_id)
    conversation = state.conversations.get(request.conversation_id, Conversation())
    if request.conversation_id not in state.conversations and len(state.conversations) >= 32:
        raise Conflict("보관할 수 있는 대화 수에 도달했어요.")
    fingerprint = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
    for turn in conversation.turns:
        if request.request_id and turn.request_id == request.request_id:
            if turn.request_fingerprint != fingerprint:
                raise Conflict("같은 요청 ID의 내용이 달라요.")
            return turn.result
    plan = state.startup_plan or StartupPlan()
    personal = request.context.startup_node_id
    intake = request.mode == 'startup_intake'
    expected = next((key for key in ('idea', 'customer', 'artifacts', 'goal') if not getattr(plan, key)), None) if intake else None
    fields = extract_fields(request.message, plan, service.model, expected=expected) if (
        not personal or is_plan_message(request.message)) else {}
    node = next((node for node in plan.nodes if node.id == personal), None) if personal else None
    if personal and not fields:
        answer = f"{node.title}\n{node.completion}\n{node.reason}" if node else "이 계정에서 해당 퀘스트를 찾지 못했어요."
        changed = False
    else:
        new_project = bool(re.search(r"(?:아이디어|아이템).*(?:바꿔|변경|교체)", request.message)
                           and fields.get("idea") != plan.idea and fields.get("idea"))
        plan = update_plan(plan, fields, new_project=new_project)
        plan.turns += 1
        active = next((node for node in plan.nodes if node.active and not node.completed), None)
        missing = next((question for key, question in (
            ("idea", "어떤 제품이나 서비스를 만들고 있어요?"),
            ("customer", "누가 어떤 상황에서 사용하면 좋을까요?"),
            *(([("artifacts", "지금 준비된 결과물이 있나요? 기획만 있는 단계라면 그렇게 알려 주세요.")] if intake else [])),
            ("goal", "다음으로 무엇을 해보거나 확인하고 싶어요? 아직 정하지 못했다면 그렇게 알려 주세요."))
            if not getattr(plan, key)), "")
        answer = missing if intake and missing else f"추천 퀘스트는 ‘{active.title}’예요.\n{active.completion}" if active else missing or "완료한 결과물을 활용해 다음 목표를 알려 주세요."
        if intake and fields:
            labels = {'idea': '서비스 설명', 'customer': '주요 사용자', 'artifacts': '준비한 결과물', 'goal': '다음 목표'}
            acknowledged = [f"{label}: {getattr(plan, key)}" for key, label in labels.items() if fields.get(key)]
            if acknowledged:
                answer = '알려준 내용을 기록했어요.\n' + '\n'.join(acknowledged) + '\n\n' + answer
        state.startup_plan = plan
        changed = True
    result = ChatResult(answer=redact(answer), conversation_id=request.conversation_id, startup_plan_updated=changed)
    conversation.turns.append(Turn(timestamp=datetime.now(timezone.utc), message=redact(request.message),
        result=result, context=request.context, request_id=request.request_id, request_fingerprint=fingerprint))
    conversation.turns = conversation.turns[-40:]
    state.conversations[request.conversation_id] = conversation
    service.store.save_state(user_id, state)
    return result

