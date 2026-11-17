"""학교 공지사항(취창업·장학) 수집기.

실행: python -m app.collect   (서버: docker compose exec api python -m app.collect)

대회 준수사항
- 요청 전에 robots.txt를 확인한다. /_attach/, /_custom/, /_res/ 는 요청하지 않는다(첨부·이미지 미수집).
- 공지 목록과 본문만 읽고, 요청 사이에 INTERVAL초를 둔다.
- 결과 발표·명단 공지는 저장하지 않고, 전화번호·학번은 저장과 AI 입력 전에 지운다.
- 모든 공고에 출처·확인 시각·원문 링크를 남긴다.
"""
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser

from defusedxml.ElementTree import fromstring as parse_xml  # 외부 XML은 안전한 파서로만 읽는다

BASE = "https://www.catholic.ac.kr"
LIST_URL = BASE + "/ko/campuslife/notice.do"
CATEGORIES = {23: "취창업", 22: "장학"}
PER_CATEGORY = 20
INTERVAL = 3.0
UA = "CUK-Career-AI/0.1 (student contest project)"
KST = timezone(timedelta(hours=9))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
CATALOG = json.loads((Path(__file__).parent / "catalog.json").read_text(encoding="utf-8"))
TYPES = ["현장실습", "창업지원", "채용", "장학", "학사", "비교과"]
STATUSES = ["재학", "휴학", "졸업예정"]

# 개인정보가 들어 있을 가능성이 높은 공지(선발 결과·명단)는 건너뛴다
SKIP_TITLE = re.compile(r"명단|합격자|선발자|선정자|수혜자|당첨|(선발|선정|심사|합격)\s*결과")
PHONE = re.compile(r"01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}")
STUDENT_NO = re.compile(r"(?<!\d)(19|20)\d{7}(?!\d)")
BUILD_VERSION = "2"  # 공고 구조가 바뀌면 올린다 → 학교 공지·K-Startup을 한 번 다시 만든다
# 금액 표현이 들어간 구절(지원금·상금 등). 공고문에 적힌 표현을 그대로 옮기기 위해 문장 단위로 뽑는다
MONEY = re.compile(r"[^.\n·※]*?(?:최대\s*)?\d[\d,.]*\s*(?:억|천만|백만|만)\s*원[^.\n·※]*")


def money_lines(text: str, limit: int = 2) -> str:
    """공고문에서 금액이 적힌 구절을 최대 limit개 돌려준다. 없으면 빈 문자열(지어내지 않는다)."""
    found = [re.sub(r"\s+", " ", m.group(0)).strip(" -,") for m in MONEY.finditer(text or "")]
    # 매출·자본금 같은 자격 기준 금액은 지원금이 아니므로 뺀다
    found = [x for x in found if re.search(r"지원|상금|지급|제공|무상|상당|혜택|장학", x) and not re.search(r"매출|자본금|이상인", x)]
    return " / ".join(dict.fromkeys(x[:90] for x in found if x))[: 90 * limit + 3] if found else ""


def facts(pairs: list[tuple[str, str | None]]) -> list[dict]:
    """화면의 '핵심 정보' 표. 값이 있는 항목만 남긴다."""
    return [{"label": k, "value": scrub(re.sub(r"\s+", " ", v)).strip()[:200]} for k, v in pairs if v and str(v).strip()]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def strip_tags(fragment: str) -> str:
    fragment = re.sub(r"(?is)<(script|style).*?</\1>", "", fragment)
    fragment = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d)>", "\n", fragment)
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in text.splitlines()]
    return "\n".join(x for x in lines if x)


def parse_list(page: str) -> list[dict]:
    out = []
    for row in page.split("<tr")[1:]:
        m = re.search(r'class="b-title" data-article-no="(\d+)"[^>]*>(.*?)</a>', row, re.S)
        if not m:
            continue
        date = re.search(r'b-date">\s*([\d.]+)', row)
        writer = re.search(r'b-writer">\s*([^<]+)', row)
        out.append(
            {
                "no": m.group(1),
                "title": strip_tags(m.group(2)).replace("\n", " "),
                "date": date.group(1) if date else "",
                "writer": writer.group(1).strip() if writer else "",
            }
        )
    return out


def parse_body(page: str) -> str:
    start = page.find('class="b-content-box"')
    if start < 0:
        return ""
    ends = [i for i in (page.find(k, start) for k in ('class="b-file-box"', 'class="b-pager-box"')) if i > 0]
    return strip_tags(page[page.find(">", start) + 1 : min(ends) if ends else start + 20000])


def scrub(text: str) -> str:
    return STUDENT_NO.sub("[학번 삭제]", PHONE.sub("[전화번호 삭제]", text))


def chunk(text: str, size: int = 350) -> list[dict]:
    """원문을 근거 인용 단위(§n)로 나눈다."""
    parts, cur = [], ""
    for line in text.splitlines():
        if cur and len(cur) + len(line) > size:
            parts.append(cur)
            cur = ""
        cur = f"{cur}\n{line}".strip()
    if cur:
        parts.append(cur)
    return [{"id": f"§{i + 1}", "title": f"원문 {i + 1}", "text": t} for i, t in enumerate(parts)]


SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "is_opportunity": {"type": "BOOLEAN"},
        "type": {"type": "STRING", "enum": TYPES},
        "org": {"type": "STRING"},
        "deadline": {"type": "STRING"},
        "period": {"type": "STRING"},
        "status": {"type": "ARRAY", "items": {"type": "STRING", "enum": STATUSES}},
        "grades": {"type": "ARRAY", "items": {"type": "INTEGER"}},
        "majors": {"type": "ARRAY", "items": {"type": "STRING"}},
        "other": {"type": "ARRAY", "items": {"type": "STRING"}},
        "jobs": {"type": "ARRAY", "items": {"type": "STRING"}},
        "preferred": {"type": "ARRAY", "items": {"type": "STRING"}},
        "documents": {"type": "ARRAY", "items": {"type": "STRING"}},
        "benefit": {"type": "STRING"},
        "preferred_text": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
    },
    "required": ["is_opportunity", "type", "org", "deadline", "confidence"],
}


def prompt(item: dict, body: str) -> str:
    lst = lambda xs: ", ".join(f"{x['id']}={x['name']}" for x in xs)  # noqa: E731
    return f"""대학 공지사항을 학생용 '기회 카드'로 구조화한다. 공지에 적힌 내용만 쓰고 추측하지 않는다.

규칙
- is_opportunity: 학생이 신청·지원할 수 있는 모집 공지면 true. 결과 발표, 단순 안내, 설문은 false.
- deadline: 신청 마감 시각. "YYYY-MM-DDTHH:MM" 형식(한국 시간). 시각이 없으면 23:59. 연도가 없으면 게시일 기준으로 판단. 마감일이 없으면 빈 문자열.
- status, grades, majors: 공지에 명시된 지원 자격만. 제한이 없거나 불명확하면 빈 배열.
  majors는 다음 계열 코드만 사용: {", ".join(CATALOG["fields"])}
- other: 위 세 가지로 표현할 수 없는 자격 조건(성적, 소득분위, 팀 구성 등). 원문 표현을 짧게 옮긴다.
- jobs: 관련 직무 id만(최대 4개). 모든 학생 대상이면 빈 배열. 목록: {lst(CATALOG["jobs"])}
- preferred: 공지에 우대·필요로 적힌 역량 id만. 없으면 빈 배열. 목록: {lst(CATALOG["skills"])}
- documents: 제출 서류 이름. period: 활동 기간(없으면 빈 문자열). org: 주관 부서·기관.
- benefit: 지원금·장학금·상금·급여 등 받는 혜택. 금액과 조건을 공지 표현 그대로 한두 문장으로. 공지에 없으면 빈 문자열.
- preferred_text: 우대 사항·가산점. 공지 표현 그대로. 없으면 빈 문자열.
- 사람 이름, 전화번호, 학번은 어떤 필드에도 쓰지 않는다.
- confidence: 구조화 결과에 대한 확신(0~1). 마감일이나 자격이 모호하면 0.8 미만.

게시일: {item["date"]}
제목: {item["title"]}
본문:
{body[:6000]}"""


def gemini(text: str, schema: dict = SCHEMA):
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        data=json.dumps(
            {
                "contents": [{"parts": [{"text": text}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0},
            }
        ).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                out = json.load(r)
            break
        except urllib.error.HTTPError as e:  # 무료 등급 분당 한도·일시 과부하: 잠시 쉬고 다시
            if e.code not in (429, 503) or attempt == 2:
                raise
            time.sleep(40)
    return json.loads("".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"]))


def build(item: dict, body: str, g: dict, now: datetime) -> dict | None:
    """Gemini 결과를 웹의 Opportunity 구조로 만든다. 기회가 아니거나 마감일이 없으면 None."""
    if not g.get("is_opportunity"):
        return None
    try:
        deadline = datetime.fromisoformat(g["deadline"]).replace(tzinfo=KST)
    except (ValueError, KeyError):
        return None
    sections = chunk(body)
    # 자격 조건의 근거 문단: '대상·자격'이 나오는 문단, 없으면 첫 문단
    src = next((s["id"] for s in sections if re.search(r"대상|자격", s["text"])), "§1")
    known = lambda key, values: [v for v in values or [] if v in {x["id"] for x in CATALOG[key]}]  # noqa: E731
    required = []
    if g.get("status"):
        required.append({"key": "status", "label": "·".join(g["status"]) + "생", "status": g["status"], "src": src})
    grades = [n for n in g.get("grades") or [] if 1 <= n <= 6]
    if grades:
        required.append({"key": "grade", "label": "·".join(map(str, grades)) + "학년", "grades": grades, "src": src})
    majors = [m for m in g.get("majors") or [] if m in CATALOG["fields"]]
    if majors:
        required.append({"key": "major", "label": "지정 계열 전공", "majors": majors, "src": src})
    required += [{"key": "other", "label": scrub(o)[:80], "src": src} for o in (g.get("other") or [])[:5]]
    url = f"{LIST_URL}?mode=view&articleNo={item['no']}"
    confidence = max(0.0, min(1.0, float(g.get("confidence") or 0)))
    return {
        "id": f"cuk-{item['no']}",
        "type": g["type"] if g.get("type") in TYPES else "비교과",
        "title": item["title"],
        "org": scrub(g.get("org") or item["writer"])[:60],
        "source": {"name": f"가톨릭대학교 공지사항 · {item['writer']}", "url": url},
        "isVirtual": False,
        "jobs": known("jobs", g.get("jobs"))[:4],
        "required": required,
        "preferred": known("skills", g.get("preferred")),
        "documents": [scrub(d)[:60] for d in (g.get("documents") or [])[:8]],
        "applyUrl": url,
        "period": g.get("period") or None,
        "sections": sections,
        "facts": facts([("지원금·혜택", g.get("benefit")), ("우대 사항", g.get("preferred_text")), ("활동 기간", g.get("period"))]),
        "versions": [{"version": 1, "checkedAt": now.isoformat(timespec="seconds"), "deadline": deadline.isoformat()}],
        "confidence": confidence,
        "reviewed": confidence >= 0.8,
    }


def with_history(old: dict | None, new: dict) -> dict:
    """본문이 바뀐 공고: 마감일이 달라졌으면 버전을 올리고 변경 내역을 남긴다(정정 알림의 근거)."""
    if not old:
        return new
    prev, cur = old["versions"][-1], new["versions"][0]
    if prev["deadline"] == cur["deadline"]:
        new["versions"] = old["versions"][:-1] + [{**prev, "checkedAt": cur["checkedAt"]}]
    else:
        change = {"field": "마감", "before": prev["deadline"], "after": cur["deadline"]}
        new["versions"] = old["versions"] + [{**cur, "version": prev["version"] + 1, "changes": [change]}]
    return new


KSTARTUP_URL = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
KSTARTUP_REGIONS = {"전국", "서울", "경기", "인천"}  # 교정 소재지 기준


def build_kstartup(x: dict, now: datetime) -> dict | None:
    """K-Startup 공고(공공데이터포털 공식 API, 공공누리 제1유형). 이미 구조화돼 있어 AI를 쓰지 않는다."""
    if "대학생" not in (x.get("aply_trgt") or "") or (x.get("supt_regin") or "전국") not in KSTARTUP_REGIONS:
        return None
    try:
        deadline = datetime.strptime(x["pbanc_rcpt_end_dt"], "%Y%m%d").replace(hour=23, minute=59, tzinfo=KST)
    except (ValueError, TypeError, KeyError):
        return None
    target = scrub(re.sub(r"\s+", " ", x.get("aply_trgt_ctnt") or "")).strip()
    texts = [
        ("공고 내용", x.get("pbanc_ctnt")),
        ("신청 대상", f"신청 대상: {x['aply_trgt']}. {target}"),
        ("접수 기간", f"접수 기간: {x.get('pbanc_rcpt_bgng_dt')} ~ {x['pbanc_rcpt_end_dt']}"),
        ("지원 분야·지역", f"지원 분야: {x.get('supt_biz_clsfc')}. 지역: {x.get('supt_regin')}. 창업 업력: {x.get('biz_enyy')}"),
        ("신청 제외 대상", x.get("aply_excl_trgt_ctnt")),
    ]
    sections = [{"id": f"§{i + 1}", "title": t, "text": scrub(v)[:1200]} for i, (t, v) in enumerate((t, v) for t, v in texts if v)]
    src = next(s["id"] for s in sections if s["title"] == "신청 대상")
    required = [{"key": "other", "label": f"신청 대상: {x['aply_trgt']}"[:80], "src": src}]
    if target:
        required.append({"key": "other", "label": target[:80], "src": src})
    url = x.get("detl_pg_url") or "https://www.k-startup.go.kr/"
    return {
        "id": f"kst-{x['pbanc_sn']}",
        "type": "창업지원",
        "title": x["biz_pbanc_nm"],
        "org": (x.get("pbanc_ntrp_nm") or "")[:60],
        "source": {"name": "K-Startup(창업진흥원) · 공공누리 제1유형", "url": url},
        "isVirtual": False,
        "jobs": ["founder"],
        "required": required,
        "preferred": [],
        "documents": [],
        "applyUrl": url,
        "period": None,
        "sections": sections,
        "facts": facts(
            [
                ("지원금·지원 규모", money_lines(f"{x.get('pbanc_ctnt') or ''}\n{x.get('aply_trgt_ctnt') or ''}") or "공고 요약에 금액 표기 없음 · 원문에서 확인"),
                ("지원 분야", x.get("supt_biz_clsfc")),
                ("우대 사항", x.get("prfn_matr") or "공고 요약에 명시 없음"),
                ("창업 단계(업력)", x.get("biz_enyy")),
                ("대상 연령", x.get("biz_trgt_age")),
                ("지역", x.get("supt_regin")),
                ("신청 제외 대상", x.get("aply_excl_trgt_ctnt")),
                ("온라인 접수처", x.get("aply_mthd_onli_rcpt_istc")),
                ("주관 기관 구분", x.get("sprv_inst")),
            ]
        ),
        "versions": [{"version": 1, "checkedAt": now.isoformat(timespec="seconds"), "deadline": deadline.isoformat()}],
        "confidence": 1.0,
        "reviewed": True,
    }


def parse_kstartup_detail(page: str) -> dict[str, str]:
    """K-Startup 공고 상세 화면의 '제목 → 내용' 묶음(신청대상, 제출서류, 선발기준, 지원내용 등)."""
    out: dict[str, str] = {}
    for m in re.finditer(r'<p class="tit">([^<]{1,80})</p>\s*<div class="list_wrap"[^>]*>(.*?)</div>', page, re.S):
        title, text = strip_tags(m.group(1)).replace("\n", " "), scrub(strip_tags(m.group(2)))
        if title and text:
            out[title] = text
    return out


def enrich_kstartup(data: dict, detail: dict[str, str]) -> dict:
    """상세 화면에서 읽은 지원 내용·금액·우대 사항·제출 서류를 공고에 채운다. 화면에 적힌 것만 쓴다."""
    if not detail:
        return data
    support = next((t for k, t in detail.items() if re.search(r"지원\s*내용|혜택|지원사항", k)), "")
    everything = "\n".join(detail.values())
    prefer = [x.strip(" -·※") for x in everything.splitlines() if re.search(r"우대|가점|가산점", x)]
    found = {
        "지원 내용": support,
        "지원금·지원 규모": money_lines(support) or money_lines(everything),
        "우대 사항": " / ".join(dict.fromkeys(prefer))[:200],
    }
    kept = [f for f in data["facts"] if f["label"] not in found or not found[f["label"]]]
    for f in kept:  # 상세 화면까지 읽었는데도 없는 항목
        f["value"] = f["value"].replace("공고 요약에", "공고 화면에")
    data["facts"] = facts([(k, v) for k, v in found.items()]) + kept
    docs = next((t for k, t in detail.items() if "제출서류" in k.replace(" ", "")), "")
    data["documents"] = [x.strip(" -·")[:60] for x in docs.splitlines() if len(x.strip(" -·")) > 1][:8]
    for title, text in detail.items():
        if re.search(r"지원\s*내용|제출\s*서류|선발|평가|혜택", title):
            data["sections"].append({"id": f"§{len(data['sections']) + 1}", "title": title[:40], "text": text[:1500]})
    return data


def fetch_kstartup() -> list[dict]:
    """모집 중인 공고 전체. 서비스 키는 URL에 들어가므로 오류 메시지에 URL을 남기지 않는다."""
    key, out, page = urllib.parse.quote(os.environ["KSTARTUP_API_KEY"], safe=""), [], 1
    while page <= 10:
        q = f"serviceKey={key}&page={page}&perPage=100&returnType=json&cond%5Brcrt_prgs_yn%3A%3AEQ%5D=Y"
        try:
            got = json.loads(fetch(f"{KSTARTUP_URL}?{q}"))
        except Exception as e:
            raise RuntimeError(f"K-Startup API 호출 실패: {type(e).__name__}") from None
        out += got.get("data") or []
        if page * 100 >= got.get("matchCount", 0):
            break
        page += 1
        time.sleep(1)
    return out


WORK24_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210{kind}21.do"
JOBS_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {"id": {"type": "STRING"}, "jobs": {"type": "ARRAY", "items": {"type": "STRING"}}},
        "required": ["id", "jobs"],
    },
}


def work24(kind: str, **params) -> ET.Element:
    """고용24 공채속보 API(개인 인증키로 허용된 범위). 인증키가 URL에 들어가므로 오류에 URL을 남기지 않는다."""
    q = urllib.parse.urlencode({"authKey": os.environ["WORK24_API_KEY"], "callTp": kind, "returnType": "XML", **params})
    try:
        root = parse_xml(fetch(f"{WORK24_URL.format(kind=kind)}?{q}"))
    except Exception as e:
        raise RuntimeError(f"고용24 API 호출 실패: {type(e).__name__}") from None
    if root.findtext("error"):
        raise RuntimeError(f"고용24 API 오류: {root.findtext('error')}")
    return root


# 고용24 학력 표기("최소|최대")에서 최소 학력을 읽는다. 값이 하나뿐이고 석·박사면 최소 학력을 알 수 없다고 본다
EDU_LEVEL = {"학력무관": "none", "고졸": "high", "대졸(2~3)": "associate", "대졸(4)": "bachelor", "석사": "master", "박사": "master"}
EDU_ORDER = ["none", "high", "associate", "bachelor", "master"]
EDU_LABEL = {
    "none": "학력 제한 없음",
    "high": "고졸 이상",
    "associate": "전문대(2~3년) 졸업 이상",
    "bachelor": "4년제 대학 졸업(예정) 이상",
    "master": "석사 이상",
    "unknown": "학력 조건은 원문에서 확인",
}
# 자격 요건 줄 가운데 조건이 아닌 것: 머리말, 학력·경력 반복, '무관', 다른 곳을 보라는 안내
QUAL_NOISE = re.compile(r"^(학력|경력|전공|최종학력|신입)\b|무관\s*$|상세\s*내용|참고|참조|^\[?\s*(응시|지원)?\s*(자격|자격요건|공통|공통자격|필수|필수사항|우대사항|경력|신입)\s*\]?\s*:?$")


def min_degree(values: list[str]) -> str:
    """모집 단위들의 학력 표기에서 가장 낮은 최소 학력(지원 문턱)을 고른다."""
    levels = []
    for v in values:
        parts = [x.strip() for x in (v or "").split("|") if x.strip()]
        if not parts:
            continue
        if len(parts) == 1 and parts[0] in ("석사", "박사"):
            levels.append("unknown")
        else:
            levels.append(EDU_LEVEL.get(parts[0], "unknown"))
    known = [x for x in levels if x != "unknown"]
    return min(known, key=EDU_ORDER.index) if known else "unknown"


# 자격 요건 문장에 적힌 학력(학력 칸이 불분명할 때 쓴다)
DEGREE_TEXT = [
    ("master", r"석사\s*(학위)?\s*(이상|소지|보유|취득)"),
    ("bachelor", r"(4년제|학사|대학교).{0,14}(졸업|학위|이상)|대졸\s*이상"),
    ("associate", r"전문학사|전문대|초대졸|2[,~·]\s*3년제"),
    ("high", r"고졸|고등학교\s*졸업"),
    ("none", r"학력\s*(및\s*경력\s*)?(무관|제한\s*없음)"),
]
DEGREE_LINE = re.compile("|".join(p for _, p in DEGREE_TEXT))


def degree_from_text(text: str) -> str:
    """자격 요건 문장에서 가장 낮은 학력 조건을 찾는다(모집 단위마다 다르면 가장 낮은 문턱)."""
    found = [level for level, pat in DEGREE_TEXT if re.search(pat, text or "")]
    return min(found, key=EDU_ORDER.index) if found else "unknown"


def qual_lines(text: str, limit: int = 3) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = raw.lstrip("-·※*○ ").strip()
        if len(line) >= 7 and not QUAL_NOISE.search(line) and not DEGREE_LINE.search(line) and line not in out:
            out.append(line)
    return out[:limit]


def build_work24(d: ET.Element, now: datetime) -> dict | None:
    """공채속보 상세 → Opportunity. 신입(또는 경력 무관)을 뽑는 모집 단위가 없으면 None. 직무 연결은 나중에 채운다."""
    clean = lambda t: scrub(re.sub(r"[ \t\r]+", " ", t or "")).strip()  # noqa: E731
    units = [u for u in d.iter("empRecrListInfo") if re.search(r"신입|무관", u.findtext("empWantedCareerNm") or "")]
    try:
        deadline = datetime.strptime(d.findtext("empWantedEndt") or "", "%Y%m%d").replace(hour=23, minute=59, tzinfo=KST)
    except ValueError:
        return None
    if not units:
        return None
    unit_text = "\n".join(
        f"[{clean(u.findtext('empRecrNm'))}] {clean(u.findtext('jobCont'))} "
        f"(경력: {u.findtext('empWantedCareerNm')}, 학력: {u.findtext('empWantedEduNm')}, 근무지: {u.findtext('workRegionNm')})"
        for u in units
    )
    quals = "\n".join(clean(u.findtext("sptCertEtc")) for u in units if u.findtext("sptCertEtc"))
    texts = [
        ("모집 분야", unit_text),
        ("지원 자격", quals),
        ("전형 절차", " → ".join(x.findtext("selsNm") or "" for x in d.iter("empSelsListInfo"))),
        ("제출 서류", clean(d.findtext("empSubmitDocCont"))),
        ("접수 방법", clean(d.findtext("empRcptMthdCont"))),
        ("기타", clean(d.findtext("empnEtcCont"))),
        ("접수 기간", f"접수 기간: {d.findtext('empWantedStdt')} ~ {d.findtext('empWantedEndt')}"),
    ]
    sections = [{"id": f"§{i + 1}", "title": t, "text": v[:1200]} for i, (t, v) in enumerate((t, v) for t, v in texts if v)]
    src = next((x["id"] for x in sections if x["title"] == "지원 자격"), "§1")
    degree = min_degree([u.findtext("empWantedEduNm") or "" for u in units])
    if degree == "unknown":
        degree = degree_from_text(quals)
    required = [{"key": "degree", "label": EDU_LABEL[degree], "degree": degree, "src": "§1"}]
    required += [{"key": "other", "label": x[:80], "src": src} for x in qual_lines(quals)]
    uniq = lambda tag: " · ".join(dict.fromkeys(clean(u.findtext(tag)) for u in units if u.findtext(tag)))  # noqa: E731
    url = d.findtext("empWantedHomepgDetail") or d.findtext("empWantedHomepg") or "https://www.work24.go.kr/"
    hint = [clean(u.findtext("empRecrNm")) for u in units] + [x.findtext("jobsCdKorNm") or "" for x in d.iter("empJobsListInfo")]
    return {
        "id": f"w24-{d.findtext('empSeqno')}",
        "type": "채용",
        "title": clean(d.findtext("empWantedTitle")),
        "org": clean(d.findtext("empBusiNm"))[:60],
        "source": {"name": "고용24 공채속보(고용노동부)", "url": url},
        "isVirtual": False,
        "jobs": ["etc"],
        "required": required,
        "preferred": [],
        "documents": [],
        "applyUrl": url,
        "period": None,
        "sections": sections,
        "facts": facts(
            [
                ("고용 형태", (d.findtext("empWantedTypeNm") or "").replace("|", " · ")),
                ("경력", uniq("empWantedCareerNm").replace("|", " · ")),
                ("학력", uniq("empWantedEduNm").replace("|", "~")),
                ("근무지", uniq("workRegionNm")),
                ("모집 분야", uniq("empRecrNm")),
            ]
        ),
        "versions": [{"version": 1, "checkedAt": now.isoformat(timespec="seconds"), "deadline": deadline.isoformat()}],
        "confidence": 1.0,
        "reviewed": True,
        "_hint": " / ".join(hint)[:300],  # 직무 연결용(저장 전에 지운다)
    }


def map_jobs(items: list[dict]) -> dict[str, list[str]]:
    """공채 제목·모집 단위를 서비스의 직무 id에 연결한다(개인정보 없음). 맞는 직무가 없으면 빈 배열."""
    jobs = ", ".join(f"{x['id']}={x['name']}" for x in CATALOG["jobs"])
    rows = "\n".join(f"{o['id']} | {o['title']} | {o['_hint']}" for o in items)
    text = (
        "채용 공고마다 관련 직무 id를 최대 3개 고른다. 목록에 맞는 직무가 없으면 빈 배열.\n"
        f"직무 목록: {jobs}\n\n공고(id | 제목 | 모집 단위·직종):\n{rows}"
    )
    valid = {x["id"] for x in CATALOG["jobs"]}
    return {r["id"]: [j for j in r.get("jobs", []) if j in valid][:3] for r in gemini(text, JOBS_SCHEMA)}


def run_work24() -> None:
    from .main import Posting, SessionLocal

    stats = {"seen": 0, "new": 0, "updated": 0, "errors": 0}
    fresh: list[tuple[str, dict]] = []
    with SessionLocal() as db:
        page = 1
        while page <= 5:
            root = work24("L", startPage=page, display=100)
            for x in root.iter("dhsOpenEmpInfo"):
                stats["seen"] += 1
                pid = f"w24-{x.findtext('empSeqno')}"
                digest = hashlib.sha256(b"w3" + ET.tostring(x)).hexdigest()
                row = db.get(Posting, pid)
                if row and row.raw_hash == digest:
                    continue  # 목록 내용이 그대로면 상세를 다시 부르지 않는다
                time.sleep(1)
                try:
                    data = build_work24(work24("D", empSeqno=x.findtext("empSeqno")), datetime.now(KST))
                except Exception as e:
                    stats["errors"] += 1
                    print(f"[오류] {pid}: {e}", file=sys.stderr)
                    continue
                if data:
                    fresh.append((digest, data))
                else:
                    save(db, Posting, pid, digest, None, datetime.now(KST), {"new": 0, "updated": 0})
            if page * 100 >= int(root.findtext("total") or 0):
                break
            page += 1
        # 직무 연결: 30건씩 묶어 Gemini 한 번. 실패하면 직무 미연결("etc")로 저장한다
        for i in range(0, len(fresh), 30):
            mapped: dict[str, list[str]] = {}
            if os.environ.get("GEMINI_API_KEY"):
                try:
                    mapped = map_jobs([d for _, d in fresh[i : i + 30]])
                    time.sleep(INTERVAL)
                except Exception as e:
                    print(f"[직무 연결 실패] {type(e).__name__}", file=sys.stderr)
            for digest, data in fresh[i : i + 30]:
                data["jobs"] = mapped.get(data["id"]) or ["etc"]
                del data["_hint"]
                save(db, Posting, data["id"], digest, data, datetime.now(KST), stats)
    print("work24", json.dumps(stats, ensure_ascii=False))


def save(db, Posting, pid: str, digest: str, data: dict | None, now: datetime, stats: dict) -> None:
    from sqlalchemy.orm.attributes import flag_modified

    row = db.get(Posting, pid)
    if row:
        row.data = with_history(row.data, data) if data else None
        row.raw_hash, row.checked_at = digest, int(now.timestamp())
        flag_modified(row, "data")
        stats["updated"] += 1
    else:
        db.add(Posting(id=pid, raw_hash=digest, data=data, checked_at=int(now.timestamp())))
        stats["new"] += 1
    db.commit()


def run_kstartup() -> None:
    from .main import Posting, SessionLocal

    stats = {"seen": 0, "new": 0, "updated": 0, "kept": 0, "detail": 0}
    robots = RobotFileParser("https://www.k-startup.go.kr/robots.txt")
    try:
        robots.read()
    except Exception:
        robots = None  # 확인하지 못하면 상세 화면은 읽지 않는다
    with SessionLocal() as db:
        for x in fetch_kstartup():
            stats["seen"] += 1
            now = datetime.now(KST)
            data = build_kstartup(x, now)
            if not data:
                continue
            stats["kept"] += 1
            digest = hashlib.sha256((BUILD_VERSION + "k3" + json.dumps(x, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
            row = db.get(Posting, data["id"])
            if row and row.raw_hash == digest:
                continue
            # 지원 내용·우대 사항은 API 요약에 없어 공고 상세 화면에서 읽는다(robots.txt 허용 범위, 요청 간격 준수)
            url = data["applyUrl"]
            if robots and url.startswith("https://www.k-startup.go.kr/") and robots.can_fetch(UA, url):
                time.sleep(INTERVAL)
                try:
                    data = enrich_kstartup(data, parse_kstartup_detail(fetch(url)))
                    stats["detail"] += 1
                except Exception as e:
                    print(f"[상세 실패] {data['id']}: {type(e).__name__}", file=sys.stderr)
            save(db, Posting, data["id"], digest, data, now, stats)
    print("k-startup", json.dumps(stats, ensure_ascii=False))


def run() -> None:
    from .main import Posting, SessionLocal

    robots = RobotFileParser(BASE + "/robots.txt")
    robots.read()
    if not robots.can_fetch(UA, LIST_URL):
        sys.exit("robots.txt가 공지 목록 수집을 허용하지 않아 중단합니다.")

    stats = {"seen": 0, "new": 0, "updated": 0, "skipped": 0, "errors": 0}
    with SessionLocal() as db:
        for cat in CATEGORIES:
            items = parse_list(fetch(f"{LIST_URL}?mode=list&srCategoryId={cat}&articleLimit={PER_CATEGORY}"))
            for item in items:
                stats["seen"] += 1
                if SKIP_TITLE.search(item["title"]):
                    stats["skipped"] += 1
                    continue
                time.sleep(INTERVAL)
                try:
                    body = scrub(parse_body(fetch(f"{LIST_URL}?mode=view&articleNo={item['no']}")))
                    digest = hashlib.sha256((BUILD_VERSION + item["title"] + body).encode()).hexdigest()
                    row = db.get(Posting, f"cuk-{item['no']}")
                    now = datetime.now(KST)
                    if row and row.raw_hash == digest:
                        continue  # 바뀌지 않은 공지는 AI를 다시 부르지 않는다
                    data = build(item, body, gemini(prompt(item, body)), now) if len(body) >= 30 else None
                    save(db, Posting, f"cuk-{item['no']}", digest, data, now, stats)
                except Exception as e:  # 한 건의 실패가 전체 수집을 멈추지 않게 한다
                    db.rollback()
                    stats["errors"] += 1
                    print(f"[오류] {item['no']} {item['title'][:30]}: {type(e).__name__} {e}", file=sys.stderr)
    print("school", json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    if os.environ.get("GEMINI_API_KEY"):
        run()
    if os.environ.get("KSTARTUP_API_KEY"):
        run_kstartup()
    if os.environ.get("WORK24_API_KEY"):
        run_work24()
    if os.environ.get("GEMINI_API_KEY"):
        from .tidy import run as run_tidy  # 조건 정리 에이전트: 새로 들어오거나 바뀐 공고만 처리

        run_tidy()
