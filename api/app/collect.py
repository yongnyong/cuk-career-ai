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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser

BASE = "https://www.catholic.ac.kr"
LIST_URL = BASE + "/ko/campuslife/notice.do"
CATEGORIES = {23: "취창업", 22: "장학"}
PER_CATEGORY = 20
INTERVAL = 3.0
UA = "CUK-Career-AI/0.1 (student contest project)"
KST = timezone(timedelta(hours=9))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
CATALOG = json.loads((Path(__file__).parent / "catalog.json").read_text(encoding="utf-8"))
TYPES = ["현장실습", "창업지원", "장학", "학사", "비교과"]
STATUSES = ["재학", "휴학", "졸업예정"]

# 개인정보가 들어 있을 가능성이 높은 공지(선발 결과·명단)는 건너뛴다
SKIP_TITLE = re.compile(r"명단|합격자|선발자|선정자|수혜자|당첨|(선발|선정|심사|합격)\s*결과")
PHONE = re.compile(r"01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}")
STUDENT_NO = re.compile(r"(?<!\d)(19|20)\d{7}(?!\d)")


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
- 사람 이름, 전화번호, 학번은 어떤 필드에도 쓰지 않는다.
- confidence: 구조화 결과에 대한 확신(0~1). 마감일이나 자격이 모호하면 0.8 미만.

게시일: {item["date"]}
제목: {item["title"]}
본문:
{body[:6000]}"""


def gemini(text: str) -> dict:
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        data=json.dumps(
            {
                "contents": [{"parts": [{"text": text}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0},
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
        "versions": [{"version": 1, "checkedAt": now.isoformat(timespec="seconds"), "deadline": deadline.isoformat()}],
        "confidence": 1.0,
        "reviewed": True,
    }


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

    stats = {"seen": 0, "new": 0, "updated": 0, "kept": 0}
    with SessionLocal() as db:
        for x in fetch_kstartup():
            stats["seen"] += 1
            now = datetime.now(KST)
            data = build_kstartup(x, now)
            if not data:
                continue
            stats["kept"] += 1
            digest = hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            row = db.get(Posting, data["id"])
            if not (row and row.raw_hash == digest):
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
                    digest = hashlib.sha256((item["title"] + body).encode()).hexdigest()
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
