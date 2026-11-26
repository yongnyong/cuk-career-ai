"""AI 처리 과정 보기와 붙여넣기 등록.

1) GET /api/process/{id}: 공고 한 건을 조건 정리 에이전트가 다시 읽는 과정을 단계별로 돌려준다.
   원문 문단 → AI가 낸 조건과 근거 구절 → 서버의 근거 대조(통과·탈락과 이유) → 최종 조건.
   저장된 공고는 바꾸지 않는다. 결과는 한 번 만들면 보관해 두고 다시 보여준다(AI를 반복 호출하지 않음).

2) POST /api/admin/postings: 관리자가 직접 확인한 공고 본문을 붙여넣으면 AI가 구조화해 저장한다.
   로그인 뒤에만 보이는 공고처럼 자동 수집하면 안 되는 자료를 사람이 옮길 때 쓴다.
"""
import copy
import hashlib
import json
import re
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .chat import limited
from .collect import GEMINI_MODEL, KST, build, gemini, prompt, scrub
from .tidy import PROMPT, SCHEMA, SCORED, SIDO, apply, norm, source_text, to_condition
from .collect import CATALOG, STATUSES

router = APIRouter()


def explain(posting: dict, ask=gemini) -> dict:
    """조건 정리 에이전트의 한 건 처리 과정을 기록해 돌려준다."""
    started = time.time()
    items = f"[{posting['id']}] {posting['title']}\n{source_text(posting)}"
    out = ask(
        PROMPT.format(statuses=", ".join(STATUSES), fields=", ".join(CATALOG["fields"]), scored=", ".join(SCORED), sido=", ".join(SIDO), items=items),
        SCHEMA,
    )
    raw = next((r.get("conditions") or [] for r in out if isinstance(r, dict) and r.get("id") == posting["id"]), [])
    used = {s["id"] for s in posting["sections"] if re.search(r"자격|대상|모집 분야|원문", s["title"])}
    checks = []
    for c in raw[:10]:
        cond = to_condition(c, posting)
        quote = str(c.get("quote", ""))
        if cond:
            section = next(s for s in posting["sections"] if s["id"] == cond["src"])
            exact = norm(quote) in norm(section["text"])
            reason = "근거 구절이 원문에 그대로 있어요" if exact else "구절의 낱말이 원문 한 문단에 대부분 있어 인정했어요"
        else:
            exact = False
            reason = "근거 구절이 너무 짧거나 없어요" if len(norm(quote)) < 4 else "근거 구절을 원문에서 찾지 못해 버렸어요"
        checks.append(
            {
                "category": c.get("category"),
                "label": scrub(str(c.get("label", "")))[:40],
                "kind": c.get("kind"),
                "quote": scrub(quote)[:80],
                "ok": bool(cond),
                "exact": exact,
                "section": cond["src"] if cond else None,
                "reason": reason,
                "becomes": {"key": cond["key"], "label": cond["label"]} if cond else None,
            }
        )
    final = apply(copy.deepcopy(posting), raw)
    return {
        "id": posting["id"],
        "model": GEMINI_MODEL,
        "ms": int((time.time() - started) * 1000),
        "at": datetime.now(KST).isoformat(timespec="seconds"),
        "sections": [{**s, "used": s["id"] in used} for s in posting["sections"]],
        "checks": checks,
        "kept": sum(c["ok"] for c in checks),
        "dropped": sum(not c["ok"] for c in checks),
        "final": final["required"],
        "usedAi": final.get("conditionsBy") == "ai",
    }


class ManualPosting(BaseModel):
    text: str = Field(min_length=30, max_length=8000)
    sourceName: str = Field(min_length=2, max_length=60)
    sourceUrl: str = Field(default="", max_length=300)


def manual_posting(body: ManualPosting, now: datetime, ask=gemini) -> dict | None:
    """붙여넣은 본문을 구조화한다. 첫 줄을 제목으로 쓴다. 모집 공고가 아니거나 마감일을 못 찾으면 None."""
    text = scrub(body.text.strip())
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    title = lines[0][:80]
    key = hashlib.sha256(text.encode()).hexdigest()[:10]
    item = {"no": key, "title": title, "date": now.strftime("%Y.%m.%d"), "writer": body.sourceName}
    data = build(item, text, ask(prompt(item, text)), now)
    if not data:
        return None
    url = body.sourceUrl if re.match(r"^https://", body.sourceUrl) else ""
    data.update(
        id=f"man-{key}",
        # 사람이 직접 확인하고 옮긴 자료임을 출처에 밝힌다
        source={"name": f"{body.sourceName} · 담당자가 직접 확인해 등록", "url": url},
        applyUrl=url,
    )
    return data


IMPORT_TYPES = {"채용", "현장실습", "창업지원", "장학", "학사", "비교과"}


class PostingRow(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    raw_hash: str = Field(min_length=1, max_length=64)
    data: dict | None = None  # None이면 내린 공고(목록에서 숨김)


class PostingImport(BaseModel):
    rows: list[PostingRow] = Field(min_length=1, max_length=200)


def make_router(get_db, get_career_db, current_user, admin_ids, Posting, Setting):
    def require_admin(user=Depends(current_user)):
        if user.id not in admin_ids():
            raise HTTPException(403, "관리자만 할 수 있어요.")
        return user

    @router.get("/api/process/{posting_id}")
    def process(posting_id: str, request: Request, db: Session = Depends(get_db), career: Session = Depends(get_career_db)):
        row = career.get(Posting, posting_id)
        if not row or not row.data:
            raise HTTPException(404, "공고를 찾지 못했어요.")
        key = f"trace:{posting_id}"[:40]
        saved = db.get(Setting, key)
        if saved and saved.value.get("hash") == row.raw_hash:
            return saved.value["trace"]
        ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
        if limited(ip):
            raise HTTPException(429, "요청이 너무 많아요. 1분 뒤에 다시 시도해 주세요.")
        try:
            trace = explain(json.loads(json.dumps(row.data)))
        except Exception:
            raise HTTPException(503, "지금은 AI 처리 과정을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요.") from None
        db.merge(Setting(key=key, value={"hash": row.raw_hash, "trace": trace}))
        db.commit()
        return trace

    @router.post("/api/admin/postings")
    def add_posting(body: ManualPosting, user=Depends(require_admin), db: Session = Depends(get_career_db)):
        now = datetime.now(KST)
        try:
            data = manual_posting(body, now)
        except Exception:
            raise HTTPException(503, "AI 구조화에 실패했어요. 잠시 뒤 다시 시도해 주세요.") from None
        if not data:
            raise HTTPException(422, "모집 공고로 보기 어렵거나 신청 마감일을 찾지 못했어요. 본문에 마감일이 있는지 확인해 주세요.")
        digest = hashlib.sha256(body.text.encode()).hexdigest()
        db.merge(Posting(id=data["id"], raw_hash=digest, data=data, checked_at=int(now.timestamp())))
        db.commit()
        return data

    @router.post("/api/admin/postings/import")
    def import_postings(body: PostingImport, user=Depends(require_admin), db: Session = Depends(get_career_db)):
        """로컬 career.db에서 만든 공고 행을 운영 공고 DB에 그대로 반영한다(app.push_postings가 호출)."""
        result = {"added": 0, "updated": 0, "unchanged": 0, "rejected": []}
        now = int(datetime.now(KST).timestamp())
        for row in body.rows:
            data = row.data
            ok = data is None or (
                data.get("id") == row.id and data.get("type") in IMPORT_TYPES and isinstance(data.get("title"), str)
                and data["title"].strip() and isinstance(data.get("versions"), list) and data["versions"])
            if not ok:
                result["rejected"].append(row.id)
                continue
            old = db.get(Posting, row.id)
            if old and old.raw_hash == row.raw_hash and (old.data is None) == (data is None):
                result["unchanged"] += 1
                continue
            result["updated" if old else "added"] += 1
            db.merge(Posting(id=row.id, raw_hash=row.raw_hash, data=data, checked_at=now))
        db.commit()
        return result

    @router.delete("/api/admin/postings/{posting_id}")
    def remove_posting(posting_id: str, user=Depends(require_admin), db: Session = Depends(get_career_db)):
        if not posting_id.startswith("man-"):
            raise HTTPException(400, "직접 등록한 공고만 지울 수 있어요.")
        row = db.get(Posting, posting_id)
        if row:
            db.delete(row)
            db.commit()
        return {"ok": True}

    return router
