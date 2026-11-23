"""Run the assistant's synthetic end-to-end scenario against the real Gemini API."""

import argparse
import json
import os
import re
import sys
import unicodedata
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from .errors import AssistantError, ModelServiceUnavailable, ModelUnavailable
from .model import MAX_503_RETRIES, GeminiModel

DEFAULT_MODEL = "gemini-3.5-flash-lite"
CHECKS = (
    ("사용자 정보 추출 및 기억 저장", 2),
    ("저장된 사용자 정보로 새 대화 답변", 1),
    ("페이지 이동 후 이전 대화 맥락 유지", 2),
    ("스킬트리 노드 상담", 1),
    ("가상 채용·창업 공고 상담", 1),
    ("챗봇에서 이력서 자동 작성 및 지원동기 초안", 1),
)
MAX_CALLS = 8
USER = "demo001"
_PREREQUISITE_ORDER = re.compile(r"선수|선행|먼저|우선|전제|전에|부터|이미.+(?:갖추|익혔|배웠|보유)")
_PREREQUISITE_DENIAL = re.compile(r"필요(?:는|가|하지)?\s*(?:없|않)|선수학습(?:이|은)?\s*아니|몰라도")


class CheckFailed(Exception):
    pass


class CheckSkipped(Exception):
    pass


class RequestLimitReached(Exception):
    pass


def require(condition, message):
    if not condition:
        raise CheckFailed(message)


class RequestBudget:
    def __init__(self, limit):
        self.limit = limit
        self.attempted = 0
        self.retries = 0
        self.metadata = 0

    def take(self, operation, retry):
        if self.attempted >= self.limit:
            detail = " HTTP 503의 추가 재시도는 보내지 않았습니다." if retry else ""
            raise RequestLimitReached(f"Gemini 요청 상한 {self.limit}회에 도달했습니다.{detail}")
        self.attempted += 1
        self.retries += bool(retry)
        self.metadata += operation != "generateContent"


class CountedModel:
    def __init__(self, model, *, trace_context=False):
        self.model = model
        self.completed = 0
        self.last_error = None
        self.trace_context = trace_context
        self.last_consultation = None

    def _call(self, operation, *args):
        try:
            response = operation(*args)
        except ModelUnavailable as error:
            self.last_error = error
            raise
        self.completed += 1
        return response

    def generate(self, instruction, data, schema):
        result = self._call(self.model.generate, instruction, data, schema)
        if self.trace_context and "conversation" in data:
            self.last_consultation = data, result.get("answer")
        return result

    def probe_text(self):
        return self._call(self.model.probe_text)


def _label_key(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", text).casefold() if char.isalnum())


def _mentions_label(answer: str, label: str) -> bool:
    expected = _label_key(label)
    return bool(expected) and expected in _label_key(answer)


def _prerequisite_key(text: str) -> str:
    text = _label_key(text).replace("파이썬", "python")
    return re.sub(r"기본문법|기본기|기본|입문", "기초", text)


def _explains_prerequisite(answer: str, prerequisite: str) -> bool:
    expected = _prerequisite_key(prerequisite)
    return any(
        expected in _prerequisite_key(clause) and _PREREQUISITE_ORDER.search(clause)
        and not _PREREQUISITE_DENIAL.search(clause)
        for clause in re.split(r"(?<=[.!?。！？])(?=\s)|\n", answer)
    )


def _trace_consultation(model, result, label, prerequisites=()):
    """Only report known fixture labels and match flags, even for a live response."""
    if not getattr(model, "trace_context", False) or model.last_consultation is None:
        return
    data, raw = model.last_consultation
    raw = raw if isinstance(raw, str) else ""
    recent = data["conversation"]["recent"]
    selected = data.get("selectedSkill")
    trace = {
        "localConversationId": result.conversation_id,
        "conversationIdSent": "conversationId" in data or "conversation_id" in data,
        "page": data["page"],
        "selectedSkill": {key: selected.get(key) for key in
                          ("jobId", "skillId", "jobName", "skillName", "prerequisites")}
        if selected else None,
        "previousPages": [turn["page"] for turn in recent],
        "label": label,
        "priorUserHasLabel": any(_mentions_label(turn["user"], label) for turn in recent),
        "priorAssistantHasLabel": any(_mentions_label(turn["assistant"], label) for turn in recent),
        "rawAnswerHasLabel": _mentions_label(raw, label),
        "displayAnswerHasLabel": _mentions_label(result.answer, label),
        "rawAnswerExplainsPrerequisite": any(_explains_prerequisite(raw, item) for item in prerequisites),
        "displayAnswerExplainsPrerequisite": any(_explains_prerequisite(result.answer, item) for item in prerequisites),
    }
    print("가상 맥락 진단 · " + json.dumps(trace, ensure_ascii=False))


def _recall_stored_memory(assistant):
    from .contracts import ChatRequest

    result = assistant.chat(USER, ChatRequest(
        conversation_id="recall", message="제가 취득했다고 알려드린 자격증을 어떻게 프로젝트 실습에 활용할까요?",
    ))
    require("SQLD" in result.answer.upper(), "별도 대화의 답변에서 저장된 SQLD 기억을 확인하지 못했습니다.")


def scenarios(assistant, memory_diagnostic):
    from .contracts import ChatRequest, Screen

    def ask(conversation, message, *, diagnostic=None, **screen):
        if getattr(assistant.model, "trace_context", False):
            assistant.model.last_consultation = None
        return assistant.chat(USER, ChatRequest(
            conversation_id=conversation, message=message, context=Screen(**screen),
        ), memory_diagnostic=diagnostic)

    def has_sqld():
        return any(
            fact.kind == "certification" and fact.value.strip().upper() == "SQLD"
            and fact.source == "conversation"
            for fact in assistant.memory(USER)
        )

    def memory():
        result = ask("record", "나 SQLD 자격증을 취득했어.", diagnostic=memory_diagnostic)
        require(result.memory_updated and has_sqld(), "SQLD 취득 주장이 사용자 기억에 저장되지 않았습니다.")

    def recall():
        if not has_sqld():
            raise CheckSkipped("기억 저장 시나리오에서 저장된 자격증을 확인하지 못했습니다.")
        _recall_stored_memory(assistant)

    def history():
        label = "별빛노트"
        first = ask("history", f"가상의 학습 예시 이름을 {label}라고 정하고 그 이름을 답에 써 줄래?", page="home")
        _trace_consultation(assistant.model, first, label)
        second = ask("history", "그러면 아까 정한 그 예시 이름을 다시 한 번 써 줄래?", page="profile")
        _trace_consultation(assistant.model, second, label)
        turns = assistant.history(USER, "history").turns
        require(first.conversation_id == second.conversation_id == "history"
                and [turn.context.page for turn in turns] == ["home", "profile"],
                "페이지 이동 전후의 두 턴이 같은 대화에 저장되지 않았습니다.")
        require(_mentions_label(first.answer, label), "첫 응답에서 사용자가 정한 예시 명칭을 확인하지 못했습니다.")
        require(_mentions_label(second.answer, label), "후속 응답에서 앞서 정한 예시 명칭을 확인하지 못했습니다.")

    def skill():
        job_id, skill_id = "mock-ai-engineer", "mock-data-analysis"
        node = assistant.data.get_skill_node(job_id, skill_id)
        require(node and node.prerequisites, "선택한 가상 노드의 카탈로그 정보를 찾지 못했습니다.")
        result = ask("skill", "이 노드의 이름과 배우기 전에 먼저 익혀 둘 기술은 뭔가요?",
                     page="tree", job_id=job_id, skill_id=skill_id)
        _trace_consultation(assistant.model, result, node.skill_name, node.prerequisites)
        require(not result.context_issues, "현재 노드가 상담 맥락으로 확인되지 않았습니다.")
        require(_mentions_label(result.answer, node.skill_name), "답변에서 선택한 노드의 명칭을 확인하지 못했습니다.")
        require(any(_explains_prerequisite(result.answer, item) for item in node.prerequisites),
                "카탈로그의 선수학습이 노드보다 먼저 필요한 기술로 설명되지 않았습니다.")

    def opportunities():
        job = ask("opportunities", "이 공고에 지원하려면 어떤 서류를 준비해야 할까요?",
                  page="opportunities", opportunity_id="mock-job-001")
        startup = ask("opportunities", "이 창업 공고의 마감일과 필요 서류는 무엇인가요?",
                      page="opportunities", opportunity_id="mock-startup-001")
        for result, ident, document in (
            (job, "mock-job-001", "이력서"), (startup, "mock-startup-001", "사업계획서"),
        ):
            require(len(result.opportunities) == 1, "선택한 공고를 조회하지 못했습니다.")
            item = result.opportunities[0]
            require(item.id == ident and item.mock and document in item.documents and "마감" in result.answer,
                    "가상 공고의 ID, 마감 안내 또는 필요 서류가 일치하지 않습니다.")
        require(any(condition.label == "SQLD 취득" and condition.verdict == "check"
                    for condition in job.opportunities[0].conditions),
                "SQLD 취득 조건이 확인 필요로 판정되지 않았습니다.")

    def resume():
        original = json.dumps({"fields": [
            {"id": "project", "label": "프로젝트", "kind": "project"},
            {"id": "intro", "label": "지원동기", "kind": "narrative"},
        ]}, ensure_ascii=False).encode("utf-8")
        record = assistant.documents.upload(USER, "live-check-resume.json", original)
        first = ask("resume", "이 이력서 양식을 내 정보로 작성해 줘.", page="documents", document_id=record.id)
        require(first.document and "프로젝트" in first.document.filled, "이력서에 등록 프로젝트가 자동 입력되지 않았습니다.")
        followup = ask("resume", "프로젝트 경험을 바탕으로 지원동기를 작성해 줘.", page="home")
        require(followup.document and followup.document.id == record.id
                and followup.document.revision == first.document.revision + 1,
                "후속 질문에서 이전 문서의 초안을 갱신하지 못했습니다.")
        draft = assistant.documents.get(USER, record.id).draft
        intro = next((item for item in draft.fields if item.field.id == "intro"), None) if draft else None
        require(intro and intro.status == "draft" and any(fact.id == "demo-project" for fact in intro.sources),
                "지원동기 초안의 등록 프로젝트 근거를 확인하지 못했습니다.")
        exported = json.loads(assistant.documents.download(USER, record.id)[2])
        require(exported["draft"] and any(field["id"] == "intro"
                and "Campus Data Lab" in (field["value"] or "") for field in exported["fields"]),
                "내보낸 이력서에 지원동기 초안이 없습니다.")
        require(assistant.store.get_original(USER, record.id) == original, "이력서 원본이 변경됐습니다.")

    return memory, recall, history, skill, opportunities, resume


def _error_summary(error: ModelUnavailable) -> str:
    details = [error.code]
    if error.operation:
        details.append(error.operation)
    if error.upstream_status is not None:
        details.append(f"Gemini HTTP {error.upstream_status}")
    if error.reason:
        details.append(error.reason)
    return f"{' / '.join(details)}. {error}"


def _report_candidates(model):
    alternatives, more = model.list_alternatives()
    if alternatives:
        print("이 키의 모델 목록에 표시된 대체 후보 · " + ", ".join(alternatives))
        print("후보의 실제 생성 접근과 할당량은 별도 검증이 필요합니다.")
    else:
        print("조회한 목록에 다른 텍스트 생성 후보가 없습니다.")
    if more:
        print("조회 한도에 따라 첫 페이지의 후보만 표시했습니다.")


def run_model_check(api_key, model_id, *, list_models=False):
    budget = RequestBudget(1)
    model = GeminiModel(api_key, model_id, timeout=20, before_request=budget.take)
    try:
        if list_models:
            _report_candidates(model)
            return 0
        supported = model.check_access()
    except ModelUnavailable as error:
        print(f"[실패] 모델 메타데이터 · {_error_summary(error)}")
        return 1
    if supported:
        print("[통과] 이 키로 모델 메타데이터를 조회했으며 generateContent 지원이 표시됩니다.")
        print("생성 요청 접근과 할당량은 실제 생성 요청에서 확인할 수 있습니다.")
        return 0
    print("[실패] 모델 메타데이터에 generateContent 지원이 표시되지 않습니다.")
    return 1


def _plan(scope, retries):
    single_request_limit = 1 + retries + bool(retries)  # One slot for discovery after repeated 503s.
    if scope == "probe":
        return (("짧은 일반 텍스트 생성", 1),), single_request_limit
    if scope == "recall":
        return CHECKS[1:2], single_request_limit
    if scope == "memory":
        return CHECKS[:1], CHECKS[0][1]
    if scope == "context":
        return CHECKS[2:4], 3
    return CHECKS, MAX_CALLS


def _run_checks(plan, checks, model, budget, memory_diagnostic=None):
    passed = failed = 0
    for index, ((label, expected), check) in enumerate(zip(plan, checks, strict=True)):
        before = budget.attempted
        retries_before = budget.retries
        completed = model.completed
        try:
            check()
            if model.last_error:
                raise model.last_error
            require(model.completed - completed == expected, "예상한 Gemini 응답을 전부 받지 못했습니다.")
        except ModelUnavailable as error:
            print(f"[실패] {label} · {_error_summary(error)} (요청 {budget.attempted - before}회, "
                  f"재시도 {budget.retries - retries_before}회)")
            failed += 1
            if isinstance(error, ModelServiceUnavailable) and error.retries_taken:
                if budget.attempted < budget.limit:
                    try:
                        _report_candidates(model.model)
                    except ModelUnavailable as lookup_error:
                        print(f"[실패] 대체 모델 조회 · {_error_summary(lookup_error)}")
                else:
                    print("요청 상한에 도달해 대체 모델 조회를 생략했습니다. --list-models로 별도 조회할 수 있습니다.")
            break
        except RequestLimitReached as error:
            print(f"[실패] {label} · {error} 남은 검증 및 추가 모델 요청을 중단합니다.")
            failed += 1
            break
        except CheckSkipped as error:
            print(f"[미실행] {label} · {error}")
        except (AssistantError, CheckFailed) as error:
            print(f"[실패] {label} · {error} (요청 {budget.attempted - before}회)")
            failed += 1
        else:
            print(f"[통과] {label} · 요청 {budget.attempted - before}회, 재시도 {budget.retries - retries_before}회")
            passed += 1
        finally:
            if index == 0 and memory_diagnostic is not None:
                print("기억 추출 진단 · " + json.dumps(asdict(memory_diagnostic), ensure_ascii=False))
    print(f"결과 · 통과 {passed}, 실패 {failed}, 미실행 {len(plan) - passed - failed}. "
          f"Gemini 요청 시도 {budget.attempted}회 / 상한 {budget.limit}회 "
          f"(생성 {budget.attempted - budget.metadata}회, 그중 재시도 {budget.retries}회, "
          f"메타데이터 {budget.metadata}회). 생성 응답 처리 {model.completed}회.")
    return 1 if failed else 0


def run_live(api_key, model_id, *, memory_only=False, scope="full", retries=MAX_503_RETRIES, trace_context=False):
    scope = "memory" if memory_only else scope
    plan, limit = _plan(scope, retries)
    budget = RequestBudget(limit)
    model = CountedModel(
        GeminiModel(api_key, model_id, timeout=20, max_503_retries=retries, before_request=budget.take),
        trace_context=trace_context,
    )
    if scope == "probe":
        return _run_checks(plan, (model.probe_text,), model, budget)

    from .contracts import MemoryEdit
    from .memory import MemoryDiagnostic
    from .repository import JsonAssistantStore, MockCareerData
    from .service import AssistantService

    with TemporaryDirectory(prefix="cuk-assistant-live-") as temp:
        assistant = AssistantService(
            MockCareerData({USER: USER}), JsonAssistantStore(Path(temp)), model,
        )
        if scope == "recall":
            assistant.add_memory(USER, MemoryEdit(kind="certification", value="SQLD"))
            return _run_checks(plan, (lambda: _recall_stored_memory(assistant),), model, budget)
        memory_diagnostic = MemoryDiagnostic()
        checks = scenarios(assistant, memory_diagnostic)
        if scope == "context":
            return _run_checks(plan, checks[2:4], model, budget)
        checks = checks[:len(plan)]
        return _run_checks(plan, checks, model, budget, memory_diagnostic)


def main(argv=None):
    parser = argparse.ArgumentParser(description="가상 데이터로 개인화 챗봇의 실제 Gemini 연동을 검증합니다.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="실제 Gemini API에 생성 요청을 보냅니다.")
    mode.add_argument("--check-model", action="store_true", help="현재 키로 지정 모델의 메타데이터만 조회합니다.")
    mode.add_argument("--list-models", action="store_true", help="현재 키로 다른 모델의 후보 목록만 조회합니다.")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--memory-only", dest="scope", action="store_const", const="memory", help="기억 추출과 저장만 점검합니다.")
    scope.add_argument("--context-only", dest="scope", action="store_const", const="context",
                       help="페이지 이동 후속 대화와 스킬트리 상담만 점검합니다.")
    scope.add_argument("--probe", dest="scope", action="store_const", const="probe", help="짧은 일반 텍스트 생성을 점검합니다.")
    scope.add_argument("--recall-only", dest="scope", action="store_const", const="recall",
                       help="가상 기억을 저장한 뒤 개인화 답변만 점검합니다.")
    parser.set_defaults(scope="full")
    parser.add_argument("--retries", type=int, choices=range(MAX_503_RETRIES + 1), default=MAX_503_RETRIES,
                        help="HTTP 503일 때 요청당 추가 재시도 횟수 (기본 2)")
    parser.add_argument("--trace-context", action="store_true", help="가상 대화의 맥락과 답변 비교 여부만 표시합니다.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini 모델 ID, 기본값 {DEFAULT_MODEL}")
    options = parser.parse_args(argv)
    if not re.fullmatch(r"gemini-[A-Za-z0-9.-]+", options.model):
        parser.error("Gemini 모델 ID 형식을 확인해 주세요.")
    metadata = options.check_model or options.list_models
    if metadata and options.scope != "full":
        parser.error("모델 메타데이터 조회와 생성 검증 모드는 별도로 실행해 주세요.")

    # Iterate environment names so preflight never accesses the credential value.
    configured = any(name == "GEMINI_API_KEY" for name in os.environ)
    print(f"GEMINI_API_KEY · {'설정됨' if configured else '미설정'}")
    print(f"실행 모델 · {options.model}")
    if metadata:
        print("모델 메타데이터 GET 1회, 생성 요청 0회. 자동 재시도 없음.", flush=True)
    else:
        plan, budget = _plan(options.scope, options.retries)
        for label, calls in plan:
            print(f"- {label} · 정상 생성 {calls}회")
        print(f"정상 시 생성 {sum(calls for _, calls in plan)}회. "
              f"총 요청 상한 {budget}회 (503 재시도·대체 모델 조회 포함).")
        delays = ", ".join(f"{2 ** index}초" for index in range(options.retries))
        print(f"HTTP 503에 한해 생성 요청당 추가 최대 {options.retries}회."
              + (f" 대기 순서 {delays}." if delays else ""))
        if options.model == DEFAULT_MODEL:
            print("표준 요금 예시(USD) · 무료 한도 내 $0. 유료는 100만 토큰당 입력 $0.30, 출력·추론 $2.50.")
            if options.scope == "memory":
                print("총 입력 2,000토큰과 출력·추론 1,000토큰을 가정하면 약 $0.0031.")
            elif options.scope == "full":
                print("총 입력 8,000토큰과 출력·추론 4,000토큰을 가정하면 약 $0.0124.")
        else:
            print("지정한 모델 및 프로젝트 요금제가 적용됩니다.")
        print("요금표 https://aistudio.google.com/docs/pricing", flush=True)
    if not (options.live or metadata):
        print("실행 계획만 확인했습니다. Gemini 호출 0회.")
        return 0

    if not configured:
        print("GEMINI_API_KEY가 없어 Gemini 호출 0회로 종료합니다.", file=sys.stderr)
        return 2
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        print("GEMINI_API_KEY가 비어 있어 Gemini 호출 0회로 종료합니다.", file=sys.stderr)
        return 2
    try:
        if metadata:
            return run_model_check(api_key, options.model, list_models=options.list_models)
        return run_live(api_key, options.model, scope=options.scope, retries=options.retries,
                        trace_context=options.trace_context)
    except ImportError:
        print("어시스턴트 의존성을 불러오지 못했습니다. INTEGRATION.md의 설치 명령을 확인해 주세요.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
