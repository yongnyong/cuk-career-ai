"""Bounded dialogue history and a separate extractive summary."""
import re

from .contracts import Conversation, Screen, Turn
from .memory import asks_to_remember
from .practice import PracticeRequest, asks_next_step, practice_request, refers_to_plan, refers_to_practice, reported_progress
from .privacy import redact, redact_secrets, secret_values

RECENT_TURNS = 6
MAX_TURNS = 50
MAX_SUMMARY = 1800
_EXAMPLE_NAME = re.compile(
    r"""예시(?:의)?\s*이름(?:을|으로|은|는)\s*["'“‘]?"""
    r"""([가-힣A-Za-z0-9][가-힣A-Za-z0-9 _-]{0,47}?)["'”’]?\s*(?:이라고|라고)\s*(?:정하|정해|부르|불러|지었|지어)"""
)
PracticeTurn = tuple[Turn, PracticeRequest]


def conversation_secrets(conversation: Conversation) -> set[str]:
    values = secret_values(conversation.summary)
    for turn in conversation.turns:
        for text in (turn.message, turn.result.answer, turn.narrative_prompt or ""):
            values.update(secret_values(text))
    return values


def safe_history(conversation: Conversation, secrets: set[str]) -> Conversation:
    if not secrets:
        return conversation
    return conversation.model_copy(update={
        "summary": redact_secrets(conversation.summary, known=secrets),
        "example_names": [name for name in conversation.example_names if redact_secrets(name, known=secrets) == name],
        "turns": [turn.model_copy(update={
            "message": redact_secrets(turn.message, known=secrets),
            "narrative_prompt": redact_secrets(turn.narrative_prompt, known=secrets) if turn.narrative_prompt else None,
            "result": turn.result.model_copy(update={
                "answer": redact_secrets(turn.result.answer, known=secrets),
                "needs_confirmation": [redact_secrets(item, known=secrets) for item in turn.result.needs_confirmation],
            }),
        }) for turn in conversation.turns],
    })


def _document_answer(answer: str) -> bool:
    return answer.startswith("[AI 초안]") or "문서 초안을 확인했어요." in answer.split("\n", 1)[0]


def _consultation_turn(turn: Turn, *, include_practice: PracticeRequest | None = None) -> bool:
    if turn.narrative_prompt or turn.result.document or _document_answer(turn.result.answer):
        return False
    return not turn.memory_evidence or (
        include_practice is not None and not asks_to_remember(turn.message)
        and not turn.result.needs_confirmation
    )


def practice_context(conversation: Conversation, message: str, screen: Screen
                     ) -> tuple[PracticeRequest | None, PracticeTurn | None]:
    latest = latest_plan = None
    active = False
    refers_back = refers_to_practice(message)
    has_progress = reported_progress(message) is not None
    recent = conversation.turns[-RECENT_TURNS:]
    follows_progress = asks_next_step(message) and any(reported_progress(turn.message) is not None for turn in recent)
    turns = conversation.turns if has_progress or follows_progress else recent
    for turn in turns:
        same_selection = not (
            screen.job_id and turn.context.job_id and screen.job_id != turn.context.job_id
            or screen.skill_id and turn.context.skill_id and screen.skill_id != turn.context.skill_id
        )
        if not (same_selection or refers_back) or turn.result.opportunities:
            active = False
            continue
        if reported_progress(turn.message) is not None:
            prior = latest_plan
        else:
            prior = (latest_plan if refers_to_plan(turn.message) else latest) if active or refers_to_practice(turn.message) else None
        requested = practice_request(turn.message, prior[1] if prior else None)
        active = bool(requested and _consultation_turn(turn, include_practice=requested))
        if active and (not requested.verify or requested.completed_through is not None):
            latest = (turn, requested)
            if requested.mode != "task":
                latest_plan = latest

    prior = latest_plan if has_progress else (
        (latest_plan if refers_to_plan(message) else latest) if active or refers_back else None
    )
    requested = practice_request(message, prior[1] if prior else None)
    if requested and requested.completed_through is not None and not requested.verify and latest_plan:
        prior = latest_plan
    return requested, prior if requested and requested.mode != "plan" else None


def recent_consultation_answers(conversation: Conversation) -> list[str]:
    return [turn.result.answer for turn in conversation.turns[-RECENT_TURNS:]
            if _consultation_turn(turn, include_practice=practice_request(turn.message))]


def recent_example_names(conversation: Conversation, message: str) -> tuple[str, ...]:
    messages = [turn.message for turn in conversation.turns[-RECENT_TURNS:]] + [message]
    names = list(conversation.example_names)
    for text in messages:
        for match in _EXAMPLE_NAME.finditer(text):
            name = match[1].strip()
            if redact(name) == name:
                if name in names:
                    names.remove(name)
                names.append(name)
    return tuple(names[-8:])


def model_history(conversation: Conversation, *, object_names: tuple[str, ...] = (), compact: bool = False,
                  practice: PracticeTurn | None = None) -> dict:
    anchor = practice[0] if practice else None
    anchor_limit = 3000 if practice and (practice[1].days or practice[1].mode == "task") else 800
    turns = [turn for turn in conversation.turns[-RECENT_TURNS:] if turn is anchor or _consultation_turn(turn)]
    if anchor is not None and all(turn is not anchor for turn in turns):
        turns = [anchor, *turns[-(RECENT_TURNS - 1):]]
    summary = "\n".join(line for line in conversation.summary.splitlines()
                        if not _document_answer(line.partition(" / 답변 ")[2]))
    if compact and not anchor:
        turns = turns[-3:]
    return {
        "summary": redact(summary, object_names=object_names)[-600:],
        "recent": [
            {
                "page": redact(turn.context.page),
                "user": redact(turn.message, object_names=object_names)[:350] if not turn.memory_evidence else "",
                "assistant": redact(turn.result.answer, object_names=object_names)[:anchor_limit if turn is anchor else 450],
                **({"priorPractice": True} if turn is anchor else {}),
            }
            for turn in turns
        ],
    }


def append_turn(conversation: Conversation, turn: Turn, *, view: Conversation | None = None) -> None:
    view = view if view is not None else conversation
    names = recent_example_names(view, turn.message)
    conversation.example_names = list(names)
    if len(conversation.turns) >= RECENT_TURNS:
        older = view.turns[-RECENT_TURNS]
        if _consultation_turn(older):
            question = redact(older.message, object_names=names)[:140]
            answer = redact(older.result.answer, object_names=names)[:220]
            snippet = f"사용자 {question} / 답변 {answer}"
            lines = [*conversation.summary.splitlines(), " ".join(snippet.split())]
            while len("\n".join(lines)) > MAX_SUMMARY:
                lines.pop(0)
            conversation.summary = "\n".join(lines)
    conversation.turns = [*conversation.turns, turn][-MAX_TURNS:]
