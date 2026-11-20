"""M7 근거 대조 통과율: 저장된 공고 전체를 조건 정리 에이전트에 다시 보내, AI가 낸 조건 중 원문 대조를 통과한 비율을 잰다.
저장된 공고는 바꾸지 않는다. 서버에서 실행한다(Gemini 키와 DB 필요).

실행: python -m eval.passrate [결과 파일]
"""
import json
import sys
import time
from collections import Counter

from sqlalchemy import select

from app.collect import CATALOG, INTERVAL, STATUSES, gemini
from app.main import Posting, SessionLocal
from app.tidy import BATCH, PROMPT, SCHEMA, SCORED, SIDO, source_text, to_condition


def main(out_path: str | None) -> None:
    with SessionLocal() as db:
        postings = [r.data for r in db.scalars(select(Posting)).all() if r.data and source_text(r.data)]
    stats = Counter()
    drops, kinds = [], Counter()
    errors = 0
    for i in range(0, len(postings), BATCH):
        batch = postings[i : i + BATCH]
        items = "\n\n".join(f"[{p['id']}] {p['title']}\n{source_text(p)}" for p in batch)
        try:
            out = gemini(
                PROMPT.format(statuses=", ".join(STATUSES), fields=", ".join(CATALOG["fields"]), scored=", ".join(SCORED), sido=", ".join(SIDO), items=items),
                SCHEMA,
            )
        except Exception as e:
            errors += 1
            print(f"[실패] {type(e).__name__}", file=sys.stderr)
            time.sleep(INTERVAL)
            continue
        by_id = {r.get("id"): r.get("conditions") or [] for r in out if isinstance(r, dict)}
        for p in batch:
            stats["postings"] += 1
            for c in by_id.get(p["id"], [])[:10]:
                ok = to_condition(c, p) is not None
                stats["conditions"] += 1
                stats["kept" if ok else "dropped"] += 1
                kinds[(c.get("category"), ok)] += 1
                if not ok:
                    drops.append({"id": p["id"], "title": p["title"][:40], "category": c.get("category"), "label": c.get("label"), "quote": c.get("quote")})
        time.sleep(INTERVAL)
    result = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
        "postings": stats["postings"],
        "conditions": stats["conditions"],
        "kept": stats["kept"],
        "dropped": stats["dropped"],
        "pass_rate": round(stats["kept"] / stats["conditions"], 4) if stats["conditions"] else None,
        "batch_errors": errors,
        "by_category": {f"{k[0]}|{'통과' if k[1] else '탈락'}": v for k, v in sorted(kinds.items(), key=lambda x: str(x[0]))},
        "dropped_examples": drops,
    }
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if out_path:
        open(out_path, "w", encoding="utf-8").write(text)
    print(json.dumps({k: v for k, v in result.items() if k not in ("dropped_examples", "by_category")}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
