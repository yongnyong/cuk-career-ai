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


KST_ITEM = {"pbanc_sn": 9, "biz_pbanc_nm": "창업 캠프", "pbanc_ntrp_nm": "기관", "aply_trgt": "대학생,일반인",
            "aply_trgt_ctnt": "예비창업자 / 문의 010-1234-5678", "pbanc_ctnt": "모집합니다", "supt_regin": "서울",
            "pbanc_rcpt_bgng_dt": "20261116", "pbanc_rcpt_end_dt": "20261210", "detl_pg_url": "https://www.k-startup.go.kr/x"}


def test_kstartup_build_and_filters():
    o = collect.build_kstartup(KST_ITEM, NOW)
    assert o["id"] == "kst-9" and o["type"] == "창업지원" and o["jobs"] == ["founder"]
    assert o["versions"][0]["deadline"] == "2026-12-10T23:59:00+09:00"
    assert all(c["key"] == "other" for c in o["required"]) and "010-1234-5678" not in str(o)
    assert {c["src"] for c in o["required"]} <= {s["id"] for s in o["sections"]}
    assert collect.build_kstartup({**KST_ITEM, "aply_trgt": "일반기업"}, NOW) is None
    assert collect.build_kstartup({**KST_ITEM, "supt_regin": "부산"}, NOW) is None


W24 = """<r><empSeqno>7</empSeqno><empWantedTitle>신입 공채</empWantedTitle><empBusiNm>회사</empBusiNm>
<empWantedStdt>20261109</empWantedStdt><empWantedEndt>20261120</empWantedEndt><empWantedHomepgDetail>https://corp.example/apply</empWantedHomepgDetail>
<empSelsList><empSelsListInfo><selsNm>서류전형</selsNm></empSelsListInfo><empSelsListInfo><selsNm>면접</selsNm></empSelsListInfo></empSelsList>
<empRecrList><empRecrListInfo><empRecrNm>데이터 분석</empRecrNm><jobCont>분석 업무</jobCont><empWantedCareerNm>CAREER</empWantedCareerNm>
<empWantedEduNm>대졸(4년)</empWantedEduNm><sptCertEtc>- 관련 전공 학사 / 문의 010-1234-5678</sptCertEtc><workRegionNm>서울</workRegionNm></empRecrListInfo></empRecrList>
<empJobsList><empJobsListInfo><jobsCdKorNm>데이터 전문가</jobsCdKorNm></empJobsListInfo></empJobsList></r>"""


def test_work24_build_keeps_only_entry_level():
    import xml.etree.ElementTree as ET

    o = collect.build_work24(ET.fromstring(W24.replace("CAREER", "신입")), NOW)
    assert o["id"] == "w24-7" and o["type"] == "채용" and o["applyUrl"] == "https://corp.example/apply"
    assert o["versions"][0]["deadline"] == "2026-11-20T23:59:00+09:00"
    assert o["required"][0] == {"key": "degree", "label": "학력 조건은 원문에서 확인", "degree": "unknown", "src": "§1"} and "010-1234-5678" not in str(o)
    assert {c["src"] for c in o["required"]} <= {s["id"] for s in o["sections"]}
    assert "데이터 전문가" in o["_hint"]
    assert collect.build_work24(ET.fromstring(W24.replace("CAREER", "경력")), NOW) is None


def test_facts_show_money_and_preference_without_inventing():
    assert "400만원" in collect.money_lines("본선 진출 혜택 - 창업 지원금 총 400만원 (등수별 차등 지급). 그 외 안내")
    assert collect.money_lines("모집합니다. 자세한 내용은 공고문 참고") == ""
    k = collect.build_kstartup({**KST_ITEM, "pbanc_ctnt": "선정 시 사업화 자금 최대 1억원 지원", "prfn_matr": None, "supt_biz_clsfc": "사업화", "biz_enyy": "예비창업자"}, NOW)
    got = {f["label"]: f["value"] for f in k["facts"]}
    assert "1억원" in got["지원금·지원 규모"] and got["우대 사항"] == "공고 요약에 명시 없음" and got["창업 단계(업력)"] == "예비창업자"
    none = {f["label"]: f["value"] for f in collect.build_kstartup(KST_ITEM, NOW)["facts"]}
    assert none["지원금·지원 규모"].startswith("공고 요약에 금액 표기 없음")
    o = collect.build(ITEM, "본문", {**G, "benefit": "장학금 100만원", "preferred_text": ""}, NOW)
    assert [f["label"] for f in o["facts"]] == ["지원금·혜택"]
    assert collect.money_lines("연 매출액이 1,900만원 이상인 기업") == ""


KST_DETAIL = """<li class="dot_list"><p class="tit">신청대상</p><div class="list_wrap"><p class="list">예비창업자<br/>- 여성 창업자 우대</p></div></li>
<li class="dot_list"><p class="tit">제출서류 (PDF 업로드)</p><div class="list_wrap"><p class="list">- 사업계획서<br/>- 신분증 사본</p></div></li>
<li class="dot_list"><p class="tit">프로그램 운영 및 지원내용</p><div class="list_wrap"><p class="list">- 사업화 자금 최대 3,000만원 지원<br/>- 사무공간 제공, 문의 010-1234-5678</p></div></li>"""


def test_kstartup_detail_fills_support_preference_and_documents():
    detail = collect.parse_kstartup_detail(KST_DETAIL)
    assert list(detail) == ["신청대상", "제출서류 (PDF 업로드)", "프로그램 운영 및 지원내용"]
    o = collect.enrich_kstartup(collect.build_kstartup(KST_ITEM, NOW), detail)
    got = {f["label"]: f["value"] for f in o["facts"]}
    assert "3,000만원" in got["지원금·지원 규모"] and "사무공간" in got["지원 내용"] and "여성 창업자 우대" in got["우대 사항"]
    assert o["documents"] == ["사업계획서", "신분증 사본"] and "010-1234-5678" not in str(o)
    assert [f["label"] for f in o["facts"]].count("우대 사항") == 1
    assert any(s["title"].startswith("프로그램 운영") for s in o["sections"])
    same = collect.enrich_kstartup(collect.build_kstartup(KST_ITEM, NOW), {})
    assert same["documents"] == []


def test_work24_degree_and_noise_lines():
    assert collect.min_degree(["대졸(4)|박사"]) == "bachelor" and collect.min_degree(["고졸|박사", "대졸(4)"]) == "high"
    assert collect.min_degree(["박사"]) == "unknown" and collect.min_degree(["학력무관"]) == "none" and collect.min_degree([""]) == "unknown"
    text = "응시자격\n- 학력 : 대학교(학사)졸 이상\n- 경력 : 신입/경력 7년 이하\n[경력]\n전공무관\n- 해외여행에 결격사유가 없는 분\n- 모집분야별 상세 내용은 채용 홈페이지 참고\n- 교대근무 가능자입니다"
    assert collect.qual_lines(text) == ["해외여행에 결격사유가 없는 분", "교대근무 가능자입니다"]
