import os
import tempfile

# 파일 DB를 써야 연결이 바뀌어도 테이블이 남는다(다른 테스트 파일과 같은 방식)
for key, name in (("DATABASE_URL", "test.db"), ("CAREER_DATABASE_URL", "career.db")):
    os.environ.setdefault(key, "sqlite:///" + os.path.join(tempfile.mkdtemp(), name).replace("\\", "/"))

from fastapi.testclient import TestClient  # noqa: E402

from app import assistant, main  # noqa: E402
from app.career_db import CareerSessionLocal, Posting  # noqa: E402

OPP = {
    "id": "kst-77", "title": "예비창업패키지 모집", "org": "창업진흥원", "type": "창업지원",
    "sections": [{"id": "§1", "title": "지원 대상", "text": "공고일 기준 창업 경험이 없는 예비창업자"},
                 {"id": "§2", "title": "신청 기간", "text": "2026.12.10. 18:00까지"}],
    "versions": [{"version": 2, "deadline": "2026-12-10T18:00:00+09:00"}],
}
PROFILE = {"departmentId": "ai", "grade": 3, "jobId": "ai-research", "careerInterest": "startup",
           "skills": {"SK-PY-01": "verified"}, "startup": {"stage": "pre"}, "pseudoId": "x"}


def ctx(**kw):
    return {"student": "학생", "page": "/", "postings": {"kst-77": OPP}, "statuses": {"kst-77": "check"},
            "current": None, "history": [], **kw}


def test_verified_citations_pass_and_unknown_ones_hold():
    ok = assistant.answer(ctx(), "언제까지?", lambda p, s: {"held": False, "text": "2026.12.10. 18:00까지예요.",
                          "citations": [{"oppId": "kst-77", "sectionId": "§2"}], "suggestions": ["서류는?"]})
    assert not ok["held"] and ok["citations"] == [{"oppId": "kst-77", "sectionId": "§2", "title": OPP["title"], "version": 2}]
    bad = assistant.answer(ctx(), "언제까지?", lambda p, s: {"held": False, "text": "12월 10일이에요.",
                           "citations": [{"oppId": "kst-77", "sectionId": "§9"}], "suggestions": []})
    assert bad["held"] and bad["text"] == assistant.HOLD_VERIFY
    other = assistant.answer(ctx(), "?", lambda p, s: {"held": False, "text": "x", "citations": [{"oppId": "w24-1", "sectionId": "§1"}], "suggestions": []})
    assert other["held"]


def test_posting_named_without_citation_is_held_but_profile_answer_is_not():
    named = assistant.answer(ctx(), "추천?", lambda p, s: {"held": False, "text": "예비창업패키지 모집에 지원할 수 있어요.", "citations": [], "suggestions": []})
    assert named["held"]
    guide = assistant.answer(ctx(), "다음 뭐 해?", lambda p, s: {"held": False, "text": "다음 추천 노드는 머신러닝 기초예요.", "citations": [], "suggestions": []})
    assert not guide["held"]


def test_prompt_has_profile_and_rule_status_but_no_login_id():
    seen = {}
    def ask(prompt, schema):
        seen["p"] = prompt
        return {"held": True, "text": "", "citations": [], "suggestions": []}
    text = assistant.student_text({**PROFILE, "pseudoId": "secretid9", "startup": {"stage": "pre", "region": "부산", "birthYear": 2003}, "scores": {"SK-TOEIC": "905"}}, "SK-PY-01")
    assistant.answer(ctx(student=text), "전화 010-1234-5678 로 알려줘", ask)
    p = seen["p"]
    assert "3학년" in p and "예비창업자" in p and "규칙 엔진 판정: 확인 필요" in p
    assert "secretid9" not in p and "010-1234-5678" not in p
    assert "부산" not in p and "2003" not in p and "905" not in p


def test_history_is_saved_per_account_and_demo_is_not(monkeypatch):
    with CareerSessionLocal() as s:
        s.merge(Posting(id="kst-77", raw_hash="h", data=OPP, checked_at=1))
        s.commit()
    calls = []
    def fake(prompt, schema):
        calls.append(prompt)
        return {"held": False, "text": "2026.12.10. 18:00까지예요.", "citations": [{"oppId": "kst-77", "sectionId": "§2"}], "suggestions": ["서류는요?"]}
    monkeypatch.setattr(assistant, "generate_json", fake)

    demo = TestClient(main.app)
    r = demo.post("/api/assistant", json={"question": "마감?", "candidates": [{"id": "kst-77", "status": "pass"}], "profile": PROFILE})
    assert r.status_code == 200 and r.json()["saved"] is False
    assert demo.get("/api/assistant/history").json() == {"messages": [], "saved": False}

    c = TestClient(main.app)
    c.post("/api/auth/signup", json={"id": "chatuser1", "password": "secret12"})
    c.put("/api/me/state", json={"state": {"profile": PROFILE}})
    for q in ["마감 언제야?", "그럼 서류는?"]:
        r = c.post("/api/assistant", json={"question": q, "path": "/tree", "candidates": [{"id": "kst-77", "status": "check"}]})
        assert r.status_code == 200 and r.json()["saved"] is True
    msgs = c.get("/api/assistant/history").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "bot", "user", "bot"]
    assert msgs[0]["path"] == "/tree" and msgs[1]["suggestions"] == ["서류는요?"]
    assert "마감 언제야?" in calls[-1] and "3학년" in calls[-1]  # 이전 대화와 서버 저장 프로필이 들어간다

    other = TestClient(main.app)
    other.post("/api/auth/signup", json={"id": "chatuser2", "password": "secret12"})
    assert other.get("/api/assistant/history").json()["messages"] == []

    c.delete("/api/me")
    with main.SessionLocal() as db:
        assert not db.query(main.ChatMessage).filter_by(user_id="chatuser1").count()
