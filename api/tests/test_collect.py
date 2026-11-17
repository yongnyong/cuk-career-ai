import os
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app import collect  # noqa: E402

LIST = """<table><tr class=""><td>취창업</td><td>
<a class="b-title" data-article-no="123" href="?mode=view&amp;articleNo=123">
  [현장실습지원센터] 동계 현장실습 모집 </a>
<span class="b-con b-date">2026.11.10</span><span class="b-con b-writer">현장실습지원센터</span></td></tr></table>"""

DETAIL = """<div class="b-content-box"><div class="fr-view"><p>참가 대상 : 3~4학년 재학생</p>
<p>문의 010-1234-5678 / 학번 202112345</p><img src="/_attach/x.png"></div></div>
<div class="b-file-box">신청서.hwp</div><div class="b-pager-box">이전글 다른 공지</div>"""

ITEM = {"no": "123", "title": "동계 현장실습 모집", "date": "2026.11.10", "writer": "현장실습지원센터"}
NOW = datetime(2026, 11, 17, 9, 0, tzinfo=collect.KST)
G = {"is_opportunity": True, "type": "현장실습", "org": "현장실습지원센터", "deadline": "2026-11-20T17:00",
     "status": ["재학"], "grades": [3, 4], "majors": ["ict", "없는계열"], "other": ["평점 3.0 이상"],
     "jobs": ["ai-engineer", "없는직무"], "preferred": ["SK-PY-01", "SK-NOPE"], "documents": ["신청서"], "confidence": 0.9}


def test_list_and_body_parsing():
    assert collect.parse_list(LIST) == [{"no": "123", "title": "[현장실습지원센터] 동계 현장실습 모집", "date": "2026.11.10", "writer": "현장실습지원센터"}]
    body = collect.parse_body(DETAIL)
    assert "참가 대상" in body and "신청서.hwp" not in body and "이전글" not in body


def test_personal_info_is_removed_and_result_notices_skipped():
    body = collect.scrub(collect.parse_body(DETAIL))
    assert "010-1234-5678" not in body and "202112345" not in body
    assert collect.SKIP_TITLE.search("동계 현장실습 선발 결과 안내")
    assert not collect.SKIP_TITLE.search("동계 현장실습 모집")


def test_build_matches_web_contract_and_drops_unknown_ids():
    o = collect.build(ITEM, "참가 대상 : 3~4학년 재학생", G, NOW)
    assert o["id"] == "cuk-123" and o["isVirtual"] is False and o["reviewed"] is True
    assert o["jobs"] == ["ai-engineer"] and o["preferred"] == ["SK-PY-01"]
    assert [c["key"] for c in o["required"]] == ["status", "grade", "major", "other"]
    assert o["required"][2]["majors"] == ["ict"] and o["required"][0]["src"] == "§1"
    assert o["versions"][0]["deadline"] == "2026-11-20T17:00:00+09:00"
    assert "articleNo=123" in o["source"]["url"]


def test_non_opportunity_or_missing_deadline_is_not_stored():
    assert collect.build(ITEM, "x", {**G, "is_opportunity": False}, NOW) is None
    assert collect.build(ITEM, "x", {**G, "deadline": ""}, NOW) is None


def test_deadline_change_adds_version():
    old = collect.build(ITEM, "본문", G, NOW)
    new = collect.with_history(old, collect.build(ITEM, "본문 정정", {**G, "deadline": "2026-11-24T17:00"}, NOW))
    assert [v["version"] for v in new["versions"]] == [1, 2]
    assert new["versions"][1]["changes"][0]["after"] == "2026-11-24T17:00:00+09:00"
    same = collect.with_history(old, collect.build(ITEM, "본문 오타 수정", G, NOW))
    assert len(same["versions"]) == 1
