"""Developer-only CLI. Stored data lives outside the source tree."""

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from .contracts import ChatRequest, ChatResult, Conversation, Fact, Identifier, Screen, Turn
from .errors import AssistantError, Conflict
from .history import append_turn
from .model import GeminiModel
from .privacy import redact, shareable
from .repository import JsonAssistantStore, MockCareerData

_DEV_STORAGE = Path(gettempdir()) / "cuk-career-ai-assistant-dev"


def build_demo(user_id: str = "demo001", store: Path = _DEV_STORAGE):
    from .service import AssistantService

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("CLI에서 Gemini를 사용하려면 환경에 인증을 설정해 주세요.")
    model = GeminiModel(api_key, os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
    data = MockCareerData({user_id: user_id} if user_id in ("demo001", "demo002") else {})
    return AssistantService(data, JsonAssistantStore(store), model)


def import_legacy(store: JsonAssistantStore, user: str, directory: Path):
    state = store.get_state(user)
    if state.revision:
        raise Conflict("새 저장소에 이미 데이터가 있어 가져오기를 중단했어요.")

    def load(filename, default):
        path = directory / filename
        return json.loads(path.read_text(encoding="utf-8")).get(user, default) if path.is_file() else default

    memory = load("memory_store.json", {})
    for kind, values in (
        ("interest", memory.get("interests", [])), ("certification", memory.get("claimed_certificates", [])),
        ("goal", [memory.get("goal")]),
    ):
        for value in values:
            if isinstance(value, str) and value.strip():
                fact = Fact(id=uuid4().hex, kind=kind, source="conversation", value=value[:240])
                if shareable(fact):
                    state.memory.append(fact)
    conversation = Conversation()
    for turn in load("history_store.json", []):
        context = Screen.model_validate(turn.get("context", {}))
        append_turn(conversation, Turn(
            timestamp=datetime.fromisoformat(turn["timestamp"]), message=redact(turn["user"]),
            result=ChatResult(answer=redact(turn["assistant"]), conversation_id="default", mock_data=True),
            context=context, topic_opportunity_id=context.opportunity_id,
        ))
    if conversation.turns:
        state.conversations["default"] = conversation
    if state.memory or conversation.turns:
        store.save_state(user, state)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", choices=("demo001", "demo002"), default="demo001")
    parser.add_argument("--store", type=Path, default=_DEV_STORAGE)
    parser.add_argument("--conversation-id", help="같은 저장소에서 이어갈 대화 ID입니다.")
    parser.add_argument("--import-legacy", type=Path)
    parser.add_argument("--trace-timing", action="store_true", help="Gemini 처리 시간과 요청 크기를 표시합니다.")
    options = parser.parse_args()
    if options.import_legacy:
        import_legacy(JsonAssistantStore(options.store), options.user, options.import_legacy)
        return
    try:
        conversation_id = TypeAdapter(Identifier).validate_python(options.conversation_id or uuid4().hex)
    except ValidationError:
        parser.error("대화 ID 형식을 확인해 주세요.")
    if options.trace_timing:
        logger = logging.getLogger(GeminiModel.__module__)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    assistant = build_demo(options.user, options.store)
    print(f"CUK Career AI 가상 사용자 상담 (대화 ID {conversation_id}, 종료 exit)")
    while True:
        try:
            message = input("\n사용자: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if message.lower() == "exit":
            break
        if 0 < len(message) <= 2000:
            try:
                print("AI:", assistant.chat(options.user, ChatRequest(
                    message=message, conversation_id=conversation_id,
                )).answer)
            except AssistantError as error:
                print(str(error))


if __name__ == "__main__":
    main()
