import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app import chat  # noqa: E402

POSTING = {
    "title": "동계 현장실습 모집", "org": "현장실습지원센터",
    "versions": [{"version": 2, "deadline": "2026-11-24T17:00:00+09:00"}],
    "sections": [{"id": "§1", "title": "원문 1", "text": "참가 대상: 3~4학년 재학생"}, {"id": "§2", "title": "원문 2", "text": "제출 서류: 신청서"}],
}


def fake(out, seen=None):
    def ask(prompt, schema):
        if seen is not None:
            seen.append(prompt)
        return out
    return ask


def test_answer_with_valid_citation():
    a = chat.answer(POSTING, "누가 지원해요?", fake({"held": False, "text": "3~4학년 재학생이에요.", "citations": ["§1", "§1"]}))
    assert a == {"text": "3~4학년 재학생이에요.", "citations": [{"sectionId": "§1", "version": 2}], "held": False}


def test_unknown_or_missing_citation_is_held():
    for cites in (["§9"], []):
        a = chat.answer(POSTING, "토익 몇 점?", fake({"held": False, "text": "800점이에요.", "citations": cites}))
        assert a["held"] and a["citations"] == [] and "800" not in a["text"]


def test_model_hold_is_kept_and_personal_info_is_not_sent():
    seen = []
    a = chat.answer(POSTING, "제 번호 010-1234-5678 학번 202112345 인데 합격할까요?", fake({"held": True, "text": "예측하지 않아요.", "citations": ["§1"]}, seen))
    assert a == {"text": "예측하지 않아요.", "citations": [], "held": True}
    assert "010-1234-5678" not in seen[0] and "202112345" not in seen[0] and "[§1] 원문 1" in seen[0]


def test_rate_limit():
    chat._hits.clear()
    assert [chat.limited("1.1.1.1") for _ in range(11)] == [False] * 10 + [True]
