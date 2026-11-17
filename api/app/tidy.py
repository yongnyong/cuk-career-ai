"""조건 정리 에이전트.

공고의 자격 요건 문장을 Gemini가 읽어 '학력 / 학년·학적 / 전공 / 어학 / 자격증 / 병역 / …' 조건으로 나눠 정리한다.
규칙으로 줄을 걸러내던 방식은 공고마다 표현이 달라 머리말이나 중복이 섞였다.

지어내기 방지: 조건마다 근거 구절(quote)을 받고, 그 구절이 공고 원문에 실제로 있을 때만 채택한다.
AI가 실패하거나 채택된 조건이 없으면 기존(규칙 기반) 조건을 그대로 둔다.

실행: python -m app.tidy   (수집 뒤에 자동으로도 실행된다)
"""
import json
import re
import sys
import time

from .collect import CATALOG, EDU_LABEL, INTERVAL, STATUSES, gemini, scrub

BATCH = 6
CATEGORIES = ["학력", "학년·학적", "전공", "어학", "자격증", "경력", "병역", "연령", "지역", "창업 단계", "기타"]
DEGREES = ["none", "high", "associate", "bachelor", "master"]
# 점수·등급으로 비교할 수 있는 역량(웹의 SCALES와 같은 목록)
SCORED = ["SK-TOEIC", "SK-OPIC", "SK-JLPT", "SK-HSK", "SK-DELF", "SK-COMP", "SK-KHIST", "HIS-C-HANJA", "CLO-C-GTQ"]

SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "STRING"},
            "conditions": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "category": {"type": "STRING", "enum": CATEGORIES},
                        "label": {"type": "STRING"},
                        "kind": {"type": "STRING", "enum": ["required", "preferred"]},
                        "quote": {"type": "STRING"},
                        "degree": {"type": "STRING", "enum": DEGREES},
                        "grades": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                        "status": {"type": "ARRAY", "items": {"type": "STRING", "enum": STATUSES}},
                        "majors": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "skill": {"type": "STRING"},
                        "min": {"type": "STRING"},
                    },
                    "required": ["category", "label", "kind", "quote"],
                },
            },
        },
        "required": ["id", "conditions"],
    },
}

PROMPT = """모집 공고의 자격 요건 문장을 대학생이 한눈에 볼 수 있는 조건 목록으로 정리한다.

규칙
1. 공고에 적힌 조건만 쓴다. 추측하거나 일반 상식으로 채우지 않는다.
2. 조건 하나에 내용 하나. 한 문장에 조건이 여러 개면 나누고, 같은 뜻이 반복되면 하나로 합친다. 공고마다 최대 6개.
3. 조건이 아닌 것은 뺀다: "응시자격"·"[경력]" 같은 머리말, "무관"·"제한 없음", "상세 내용은 홈페이지 참고" 같은 안내, 부서·직무 이름 나열, 전형 절차.
4. label은 30자 이내의 짧은 말로 쓴다. 예: "4년제 대학 졸업(예정)", "병역필 또는 면제", "토익 700점 이상", "교대근무 가능".
5. kind: 반드시 갖춰야 하면 required, 우대·가점이면 preferred.
6. quote: 그 조건의 근거가 되는 공고 원문 구절을 글자 그대로 옮긴다(8~40자). 원문에 없는 문장을 만들지 않는다.
7. 아래 항목은 해당할 때만 채운다.
   - degree(학력): none=학력 무관, high=고졸 이상, associate=전문대 졸업 이상, bachelor=4년제 졸업(예정) 이상, master=석사 이상
   - grades(학년): 지원 가능한 학년 숫자 배열. status(학적): {statuses}
   - majors(전공): 다음 계열 코드만 — {fields}
   - skill + min(어학·자격 점수): skill은 다음 id만 — {scored}. min은 점수나 등급만(예: "700", "IM2", "N2", "2급")
8. 사람 이름, 전화번호는 쓰지 않는다.

공고 목록(각 공고의 id와 자격 요건 문장)
{items}"""


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def source_text(posting: dict) -> str:
    """조건을 읽을 문단: 자격·대상·모집 분야를 담은 문단만(전형 절차·접수 기간 등은 제외)."""
    keep = [s["text"] for s in posting["sections"] if re.search(r"자격|대상|모집 분야|원문", s["title"])]
    return "\n".join(keep)[:2500]


def to_condition(c: dict, posting: dict) -> dict | None:
    """에이전트가 낸 조건 하나를 검증해 웹의 Condition으로 바꾼다. 근거 구절이 원문에 없으면 버린다."""
    quote, label = norm(c.get("quote", "")), scrub(str(c.get("label", ""))).strip()[:40]
    if len(quote) < 4 or not label:
        return None
    src = next((s["id"] for s in posting["sections"] if quote in norm(s["text"])), None)
    if not src:
        # 구절을 글자 그대로 옮기지 않은 경우: 구절의 낱말(숫자 포함)이 거의 모두 한 문단에 있으면 인정한다
        words = re.findall(r"[가-힣A-Za-z0-9]{2,}", c.get("quote", ""))
        src = next(
            (s["id"] for s in posting["sections"] if len(words) >= 2 and sum(w in norm(s["text"]) for w in words) >= 0.7 * len(words)),
            None,
        )
    if not src:
        return None
    base = {"label": label, "src": src}
    if c.get("degree") in DEGREES and c["category"] == "학력":
        return {**base, "key": "degree", "degree": c["degree"], "label": EDU_LABEL[c["degree"]]}
    grades = [g for g in c.get("grades") or [] if 1 <= g <= 6]
    if grades:
        return {**base, "key": "grade", "grades": grades}
    status = [x for x in c.get("status") or [] if x in STATUSES]
    if status:
        return {**base, "key": "status", "status": status}
    majors = [m for m in c.get("majors") or [] if m in CATALOG["fields"]]
    if majors:
        return {**base, "key": "major", "majors": majors}
    if c.get("skill") in SCORED:
        return {**base, "key": "skill", "skill": c["skill"], **({"min": str(c["min"])[:8]} if c.get("min") else {})}
    return {**base, "key": "other", "label": f"{c['category']}: {label}" if c["category"] != "기타" else label}


def apply(posting: dict, conditions: list[dict]) -> dict:
    """검증된 조건으로 필수 조건을 바꾼다. 채택된 필수 조건이 없으면 기존 조건을 유지한다."""
    required, preferred, seen = [], [], set()
    for c in conditions[:10]:
        cond = to_condition(c, posting)
        if not cond or cond["label"] in seen:
            continue
        seen.add(cond["label"])
        (preferred if c.get("kind") == "preferred" else required).append(cond)
    if required:
        # 규칙으로 읽은 학력 조건은 AI가 학력을 따로 내지 않았을 때 유지한다
        if not any(c["key"] == "degree" for c in required):
            required = [c for c in posting["required"] if c["key"] == "degree" and c.get("degree") != "unknown"] + required
        posting["required"] = required[:7]
    if preferred:
        facts = [f for f in posting.get("facts", []) if f["label"] != "우대 사항" or not f["value"].startswith("공고 ")]
        if not any(f["label"] == "우대 사항" for f in facts):
            facts.insert(0, {"label": "우대 사항", "value": " / ".join(c["label"] for c in preferred)[:200]})
        posting["facts"] = facts
    posting["conditionsBy"] = "ai" if required else "rule"
    return posting


def tidy_batch(postings: list[dict], ask=gemini) -> list[dict]:
    items = "\n\n".join(f"[{p['id']}] {p['title']}\n{source_text(p)}" for p in postings)
    out = ask(
        PROMPT.format(statuses=", ".join(STATUSES), fields=", ".join(CATALOG["fields"]), scored=", ".join(SCORED), items=items),
        SCHEMA,
    )
    by_id = {r.get("id"): r.get("conditions") or [] for r in out if isinstance(r, dict)}
    return [apply(p, by_id.get(p["id"], [])) for p in postings]


def run(limit: int = 400) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from .main import Posting, SessionLocal

    stats = {"todo": 0, "ai": 0, "kept_rule": 0, "errors": 0}
    with SessionLocal() as db:
        rows = [
            r
            for r in db.scalars(select(Posting)).all()
            if r.data and r.id.startswith(("kst-", "w24-")) and "conditionsBy" not in r.data and source_text(r.data)
        ][:limit]
        stats["todo"] = len(rows)
        for i in range(0, len(rows), BATCH):
            batch = rows[i : i + BATCH]
            try:
                done = tidy_batch([json.loads(json.dumps(r.data)) for r in batch])
            except Exception as e:  # 실패한 묶음은 기존 조건 그대로 두고 다음 실행 때 다시 시도한다
                stats["errors"] += 1
                print(f"[조건 정리 실패] {type(e).__name__}", file=sys.stderr)
                time.sleep(INTERVAL)
                continue
            for row, data in zip(batch, done):
                row.data = data
                flag_modified(row, "data")
                stats["ai" if data["conditionsBy"] == "ai" else "kept_rule"] += 1
            db.commit()
            time.sleep(INTERVAL)
    print("tidy", json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    run()
