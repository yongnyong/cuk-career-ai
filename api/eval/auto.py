"""자동 검증: M7 공격 차단, M8 개인정보, M10 응답 속도. docs/EVALUATION.md 참고.

실행(api 폴더에서): python -m eval.auto [privacy|attack|latency|all] [결과 파일]
공개 사이트의 API에서 공고를 받아 검사한다. 서버 DB에 직접 접근하지 않는다.
"""
import json
import random
import re
import sys
import time
import urllib.request

from app.collect import scrub
from app.tidy import to_condition

BASE = "https://cuk-career-ai.vercel.app/api"
random.seed(20261120)


def get(path: str, data: dict | None = None, timeout: int = 90):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode() if data else None, headers={"Content-Type": "application/json"})
    started = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.load(r)
    return body, time.time() - started


# ───────── M8 개인정보
PATTERNS = {
    "휴대전화": re.compile(r"01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}"),
    "학번(19·20으로 시작하는 9자리)": re.compile(r"(?<!\d)(19|20)\d{7}(?!\d)"),
    "주민등록번호": re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
}
# 기관 연락처는 개인정보가 아니지만 개수를 참고로 보고한다
REFERENCE = {
    "이메일(기관 메일 포함)": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "유선 전화(기관 대표번호 포함)": re.compile(r"(?<!\d)0(2|[3-6]\d)[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)"),
}

SYNTHETIC = [
    ("문의 010-1234-5678", "휴대전화"), ("연락처 010 1234 5678", "휴대전화"), ("010.1234.5678로 연락", "휴대전화"),
    ("담당 01012345678", "휴대전화"), ("011-123-4567", "휴대전화"), ("016-1234-5678", "휴대전화"),
    ("학번 202112345", "학번"), ("202212345 김○○", "학번"), ("2019 12345 아님(띄어 씀)", None), ("199912345", "학번"),
    ("주민번호 990101-1234567", "주민번호"), ("9901011234567", "주민번호"),
    ("마감 2026.12.10 18:00", None), ("지원금 3,000만원", None), ("2026년 12월 10일", None),
    ("문의 02-2164-4961", None), ("공고번호 179814", None), ("TOEIC 700점", None),
    ("20261210까지", None), ("인원 20명, 기간 2027.01.04~02.26", None),
]


def privacy(postings: list[dict]) -> dict:
    found = {k: [] for k in PATTERNS}
    ref = {k: 0 for k in REFERENCE}
    for o in postings:
        texts = [o.get("title", ""), o.get("org", "")] + [s["text"] for s in o.get("sections", [])]
        texts += [c["label"] for c in o.get("required", [])] + [f["value"] for f in o.get("facts", [])] + list(o.get("documents", []))
        blob = "\n".join(texts)
        for k, pat in PATTERNS.items():
            for m in pat.finditer(blob):
                found[k].append({"id": o["id"], "match": m.group(0)})
        for k, pat in REFERENCE.items():
            ref[k] += len(pat.findall(blob))
    synth = []
    for text, kind in SYNTHETIC:
        out = scrub(text)
        removed = out != text
        synth.append({"input": text, "should_remove": kind is not None, "removed": removed, "output": out, "ok": removed == (kind is not None)})
    return {
        "postings": len(postings),
        "detected": {k: len(v) for k, v in found.items()},
        "examples": {k: v[:5] for k, v in found.items() if v},
        "reference_contacts": ref,
        "synthetic": {"total": len(synth), "ok": sum(x["ok"] for x in synth), "cases": synth},
    }


# ───────── M7 공격 차단: 원문에 없는 근거 구절을 단 가짜 조건이 걸러지는가
FAKE = ["TOEIC 900점 이상 필수", "평점 평균 4.0 이상인 자", "정보처리기사 자격증 소지자에 한함", "서울 거주 3년 이상", "만 25세 이하인 자", "여성만 지원 가능",
        "영어 원어민 수준 회화 가능자", "운전면허 1종 보통 필수", "해외 체류 경험 1년 이상", "졸업 평점 3.8 이상"]


def tamper_numbers(text: str) -> str | None:
    """원문 구절의 숫자 하나만 바꾼다(예: 3년 → 7년). 바꿀 숫자가 없으면 None."""
    m = re.search(r"\d+", text)
    if not m:
        return None
    n = int(m.group(0))
    return text[: m.start()] + str(n + 4 if n < 50 else n + 40) + text[m.end():]


def attack(postings: list[dict]) -> dict:
    pool = [o for o in postings if o.get("sections")]
    cases = []
    for phrase in FAKE:  # 원문에 없는 문장 10개
        o = random.choice(pool)
        c = {"category": "기타", "label": phrase, "kind": "required", "quote": phrase}
        cases.append({"type": "지어낸 문장", "id": o["id"], "quote": phrase, "blocked": to_condition(c, o) is None})
    tried = 0
    for o in random.sample(pool, len(pool)):  # 원문 구절에서 숫자만 바꾼 것 10개
        for s in o["sections"]:
            lines = [x.strip(" -·") for x in s["text"].splitlines() if 12 <= len(x.strip()) <= 60 and re.search(r"\d", x)]
            if not lines:
                continue
            fake = tamper_numbers(lines[0])
            if fake and fake not in s["text"]:
                c = {"category": "기타", "label": fake[:30], "kind": "required", "quote": fake}
                cases.append({"type": "숫자만 바꾼 원문 구절", "id": o["id"], "quote": fake, "original": lines[0], "blocked": to_condition(c, o) is None})
                tried += 1
            break
        if tried >= 10:
            break
    real = 0
    controls = []
    for o in random.sample(pool, len(pool)):  # 대조군: 원문 구절 그대로는 통과해야 한다
        s = o["sections"][0]
        line = next((x.strip(" -·") for x in s["text"].splitlines() if len(x.strip()) >= 12), None)
        if line:
            c = {"category": "기타", "label": line[:30], "kind": "required", "quote": line[:60]}
            controls.append({"id": o["id"], "quote": line[:60], "passed": to_condition(c, o) is not None})
            real += 1
        if real >= 10:
            break
    return {
        "attacks": len(cases),
        "blocked": sum(c["blocked"] for c in cases),
        "by_type": {t: f"{sum(c['blocked'] for c in cases if c['type'] == t)}/{sum(c['type'] == t for c in cases)}" for t in {c["type"] for c in cases}},
        "leaked": [c for c in cases if not c["blocked"]],
        "controls": {"total": len(controls), "passed": sum(c["passed"] for c in controls)},
    }


# ───────── M10 응답 속도
def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))], 3)


def latency(postings: list[dict]) -> dict:
    out = {}
    for name, path, n in (("health", "/health", 50), ("공고 목록", "/opportunities", 30)):
        ts = []
        for _ in range(n):
            ts.append(get(path)[1])
        out[name] = {"n": n, "p50": pct(ts, 0.5), "p95": pct(ts, 0.95)}
    target = next(o for o in postings if o["id"].startswith("cuk-"))
    ts, held = [], 0
    for i in range(15):  # 챗봇은 1분 10회 제한이 있어 7초 간격으로 15회
        body, t = get("/chat", {"oppId": target["id"], "question": ["누가 신청할 수 있어요?", "언제까지 신청해요?", "무엇을 지원해 줘요?"][i % 3]})
        ts.append(t)
        held += body.get("held", False)
        time.sleep(7)
    out["챗봇"] = {"n": len(ts), "p50": pct(ts, 0.5), "p95": pct(ts, 0.95), "held": held}
    ts = [get(f"/process/{target['id']}")[1] for _ in range(10)]
    out["AI 처리 과정(보관본)"] = {"n": 10, "p50": pct(ts, 0.5), "p95": pct(ts, 0.95)}
    with urllib.request.urlopen(urllib.request.Request(BASE + "/opportunities", headers={"Accept-Encoding": "gzip"}), timeout=60) as r:
        out["공고 목록 전송 크기"] = {"encoding": r.headers.get("Content-Encoding") or "없음", "bytes": len(r.read())}
    return out


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    postings, _ = get("/opportunities")
    result = {"measured_at": time.strftime("%Y-%m-%d %H:%M"), "postings": len(postings)}
    if what in ("privacy", "all"):
        result["m8"] = privacy(postings)
    if what in ("attack", "all"):
        result["m7_attack"] = attack(postings)
    if what in ("latency", "all"):
        result["m10"] = latency(postings)
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(text)
    summary = {k: v for k, v in result.items()}
    if "m8" in summary:
        summary["m8"] = {k: summary["m8"][k] for k in ("postings", "detected", "reference_contacts")} | {"synthetic": f"{result['m8']['synthetic']['ok']}/{result['m8']['synthetic']['total']}", "synthetic_fail": [c for c in result["m8"]["synthetic"]["cases"] if not c["ok"]], "examples": result["m8"]["examples"]}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
