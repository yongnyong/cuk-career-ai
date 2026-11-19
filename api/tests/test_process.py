import os
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient  # noqa: E402

from app import collect, main, process  # noqa: E402

NOW = datetime(2026, 11, 19, 9, 0, tzinfo=collect.KST)
POSTING = {
    "id": "w24-1", "title": "신입 공채", "org": "회사",
    "sections": [
        {"id": "§1", "title": "지원 자격", "text": "- 4년제 대학교 졸업(예정)자\n- 남자의 경우 병역필 또는 면제자"},
        {"id": "§2", "title": "전형 절차", "text": "서류전형 → 면접"},
    ],
    "required": [{"key": "other", "label": "응시자격", "src": "§1"}],
    "facts": [],
    "versions": [{"version": 1, "deadline": "2026-12-10T23:59:00+09:00"}],
}
AI = [
    {"category": "학력", "label": "4년제 졸업(예정)", "kind": "required", "quote": "4년제 대학교 졸업(예정)자", "degree": "bachelor"},
    {"category": "병역", "label": "병역필 또는 면제", "kind": "required", "quote": "남자는 병역필 또는 면제자"},
    {"category": "어학", "label": "토익 900점 이상", "kind": "required", "quote": "TOEIC 900점 이상 필수", "skill": "SK-TOEIC", "min": "900"},
]


def test_explain_shows_kept_and_dropped_with_reasons():
    t = process.explain(POSTING, lambda p, s: [{"id": "w24-1", "conditions": AI}])
    assert (t["kept"], t["dropped"]) == (2, 1)
    assert [(c["ok"], c["exact"]) for c in t["checks"]] == [(True, True), (True, False), (False, False)]
    assert "찾지 못해" in t["checks"][2]["reason"] and t["checks"][2]["becomes"] is None
    assert [c["key"] for c in t["final"]] == ["degree", "other"]
    assert [s["used"] for s in t["sections"]] == [True, False]
    assert POSTING["required"][0]["label"] == "응시자격"  # 원본 공고는 바뀌지 않는다


def test_manual_posting_marks_human_source_and_removes_personal_info():
    body = process.ManualPosting(text="동계 현장실습생 모집\n대상: 3~4학년 재학생\n문의 010-1234-5678\n마감 12월 5일", sourceName="현장실습지원센터", sourceUrl="https://co-op.catholic.ac.kr/")
    g = {"is_opportunity": True, "type": "현장실습", "org": "현장실습지원센터", "deadline": "2026-12-05T23:59", "grades": [3, 4], "status": ["재학"], "confidence": 0.9}
    o = process.manual_posting(body, NOW, lambda text: g)
    assert o["id"].startswith("man-") and o["title"] == "동계 현장실습생 모집" and o["isVirtual"] is False
    assert "직접 확인해 등록" in o["source"]["name"] and "010-1234-5678" not in str(o)
    assert process.manual_posting(body, NOW, lambda text: {**g, "deadline": ""}) is None


def test_admin_only_endpoints(monkeypatch):
    c = TestClient(main.app)
    payload = {"text": "가" * 40, "sourceName": "센터"}
    assert c.post("/api/admin/postings", json=payload).status_code == 401
    c.post("/api/auth/signup", json={"id": "writer01", "password": "secret12"})
    assert c.post("/api/admin/postings", json=payload).status_code == 403
    assert c.delete("/api/admin/postings/kst-1").status_code == 403
    monkeypatch.setattr(main, "ADMIN_IDS", {"writer01"})
    assert c.delete("/api/admin/postings/kst-1").status_code == 400
    assert c.get("/api/process/none-1").status_code == 404
