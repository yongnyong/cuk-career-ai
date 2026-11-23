"""Interactive preview of externally authored skill trees using AssistantService."""

import argparse
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from .contracts import ChatRequest, Screen
from .errors import AssistantError
from .live_check import DEFAULT_MODEL, RequestBudget, RequestLimitReached
from .model import GeminiModel
from .privacy import catalog_text, redact
from .repository import JsonAssistantStore, MockCareerData
from .service import AssistantService
from .skill_context import CatalogSkillData

_CATALOG = Path(__file__).with_name("skill_lab_catalog.json")
_USERS = {"demo001": "demo001", "demo002": "demo002"}
_CONVERSATION = "skill-lab"
_KEY = re.compile(r"AIza[A-Za-z0-9_-]{35}")
_COMMANDS = (
    ":users 가상 사용자 목록  :user <id> 사용자 변경\n"
    ":jobs 직무 목록  :job <id> 직무 선택  :nodes 현재 직무 노드 목록\n"
    ":node <id> 노드 선택  :status 현재 선택 확인  :help 도움말  :quit 종료"
)


def _safe_text(text: str, api_key: str = "") -> str:
    if api_key:
        text = text.replace(api_key, "[인증 정보 삭제]")
    return redact(_KEY.sub("[인증 정보 삭제]", text))


def _load_catalog(path: Path) -> CatalogSkillData:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    catalog = CatalogSkillData(raw, mock=True)
    if not any(tree.nodes for tree in catalog.trees.values()):
        raise ValueError("empty skill catalog")
    return catalog


def _print_jobs(data, api_key: str = "") -> None:
    for role in data.list_career_roles():
        tree = data.get_skill_tree(role.id)
        count = len(tree.nodes) if tree else 0
        print(f"{_safe_text(role.id, api_key)} · {_safe_text(catalog_text(role.name), api_key)} ({count}개 노드)")


def _status(user: str, screen: Screen, api_key: str) -> None:
    job_id = _safe_text(screen.job_id, api_key) if screen.job_id else "-"
    skill_id = _safe_text(screen.skill_id, api_key) if screen.skill_id else "-"
    print(f"가상 사용자 {user} · conversationId={_CONVERSATION} · jobId={job_id} · skillId={skill_id}")


def run_session(service: AssistantService, *, api_key: str = "") -> None:
    """Send each question through the normal application service and screen contract."""
    user = next(iter(_USERS))
    selections = {key: Screen(page="tree") for key in _USERS}
    previous = {}
    data = service.data
    print("스킬트리 상담 실험실 · 가상 사용자와 로컬 카탈로그")
    print(_COMMANDS)
    _print_jobs(data, api_key)
    _status(user, selections[user], api_key)
    while True:
        try:
            line = input("\n질문 또는 명령> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not line:
            continue
        screen = selections[user]
        if line.startswith(":"):
            parts = line.split(maxsplit=1)
            command, argument = parts[0], parts[1] if len(parts) == 2 else ""
            if command == ":quit":
                return
            if command == ":help":
                print(_COMMANDS)
            elif command == ":users":
                print("가상 사용자 · " + ", ".join(_USERS))
            elif command == ":user":
                if argument in _USERS:
                    user = argument
                    _status(user, selections[user], api_key)
                else:
                    print("가상 사용자 ID를 확인해 주세요. :users")
            elif command == ":jobs":
                _print_jobs(data, api_key)
            elif command == ":status":
                _status(user, screen, api_key)
            elif command == ":nodes":
                tree = data.get_skill_tree(screen.job_id) if screen.job_id else None
                if not tree:
                    print("먼저 직무를 선택해 주세요. :jobs")
                else:
                    for node in tree.nodes.values():
                        print(f"{_safe_text(node.skill_id, api_key)} · "
                              f"{_safe_text(catalog_text(node.skill_name), api_key)}")
            elif command in (":job", ":node"):
                if command == ":job" and data.get_skill_tree(argument):
                    selected = Screen(page="tree", job_id=argument)
                elif command == ":node" and screen.job_id and data.get_skill_node(screen.job_id, argument):
                    selected = Screen(page="tree", job_id=screen.job_id, skill_id=argument)
                else:
                    print("선택할 ID를 확인해 주세요. :jobs 또는 :nodes")
                    continue
                if screen.job_id and selected != screen and (screen.skill_id or screen.job_id != selected.job_id):
                    previous[user] = screen
                selections[user] = selected
                _status(user, selected, api_key)
            else:
                print("지원하는 명령은 :help에서 볼 수 있어요.")
            continue
        if not screen.job_id:
            print("먼저 직무를 선택해 주세요. :jobs")
            continue
        message = _safe_text(line, api_key)
        if len(message) > 2000:
            print("질문은 2,000자 이내로 입력해 주세요.")
            continue
        try:
            result = service.chat(
                user, ChatRequest(message=message, conversation_id=_CONVERSATION, context=screen),
                previous_selection=previous.get(user),
            )
        except RequestLimitReached as error:
            print(str(error))
            return
        except AssistantError as error:
            print(_safe_text(str(error), api_key))
            continue
        print("AI:", _safe_text(result.answer, api_key))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="가상 사용자 스킬트리 상담의 로컬 체험")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="호출 계획과 선택 가능한 직무를 확인합니다. 기본 동작입니다.")
    mode.add_argument("--live", action="store_true", help="Gemini를 사용하는 대화 세션을 시작합니다.")
    parser.add_argument("--catalog", type=Path, default=_CATALOG, help="팀의 skills/jobs 형식 JSON 파일입니다.")
    parser.add_argument("--model", help="Gemini 모델 ID입니다. 생략하면 GEMINI_MODEL 또는 개발 기본값을 사용합니다.")
    parser.add_argument("--max-requests", type=int, default=20, help="세션 전체의 실제 Gemini 요청 상한입니다.")
    args = parser.parse_args(argv)
    if args.max_requests < 1:
        parser.error("요청 상한에는 양수를 지정해 주세요.")
    try:
        catalog = _load_catalog(args.catalog)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        print("카탈로그를 읽을 수 없어요. skills, jobs와 직무별 nodes 형식을 확인해 주세요.")
        return 2
    print(f"호출 계획 · 선택 명령 0회, 상담 턴 최대 2회, 세션 전체 최대 {args.max_requests}회")
    if not args.live:
        print("계획 확인 · Gemini 요청 0회")
        _print_jobs(catalog)
        print(_COMMANDS)
        return 0
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("실시간 상담을 시작하려면 환경에 Gemini 인증을 설정해 주세요.")
        return 2
    budget = RequestBudget(args.max_requests)
    try:
        model = GeminiModel(api_key, args.model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
                            max_503_retries=0, before_request=budget.take)
    except ValueError:
        print("Gemini 모델 설정을 확인해 주세요.")
        return 2
    data = MockCareerData(_USERS, skill_catalog=catalog)
    with TemporaryDirectory(prefix="cuk-skill-lab-") as directory:
        run_session(AssistantService(data, JsonAssistantStore(Path(directory)), model), api_key=api_key)
    print(f"Gemini 요청 시도 {budget.attempted}회 / 상한 {budget.limit}회")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
