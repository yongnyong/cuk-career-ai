"""Offline relevance comparison on a frozen, explicitly labelled public/synthetic corpus."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import types

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..career_db import CareerBase
from .opportunity_search import OpportunitySearch


def baseline_search(ref):
    root = Path(__file__).resolve().parents[3]
    code = subprocess.check_output(
        ["git", "show", f"{ref}:api/app/career/opportunity_search.py"], cwd=root, text=True, encoding="utf-8")
    module = types.ModuleType("app.career._evaluation_baseline")
    module.__package__ = "app.career"
    sys.modules[module.__name__] = module
    exec(compile(code, "<git-baseline>", "exec"), module.__dict__)
    return module.OpportunitySearch


def evaluate(fixture, search_type):
    engine = create_engine("sqlite://")
    CareerBase.metadata.create_all(engine)
    search = search_type(sessionmaker(engine, expire_on_commit=False), lambda: fixture["postings"])
    cases = []
    try:
        for case in fixture["cases"]:
            start = time.perf_counter()
            result = search.search(case["query"], case["kind"], focus=case.get("focus", ""), limit=20)
            ids = [hit["postingId"] for hit in result["hits"]]
            grades = case["relevance"]
            relevant = {key for key, grade in grades.items() if grade > 0}
            dcg = sum((2 ** grades.get(key, 0) - 1) / math.log2(i + 2) for i, key in enumerate(ids[:3]))
            ideal = sum((2 ** grade - 1) / math.log2(i + 2)
                        for i, grade in enumerate(sorted(grades.values(), reverse=True)[:3]))
            cases.append(dict(id=case["id"], query=case["query"], top3=ids[:3],
                precision3=sum(key in relevant for key in ids[:3]) / 3,
                recall20=len(set(ids) & relevant) / len(relevant) if relevant else None,
                ndcg3=dcg / ideal if ideal else None,
                falsePositiveCount=sum(key not in relevant for key in ids[:3]),
                milliseconds=round((time.perf_counter() - start) * 1000, 2)))
    finally:
        engine.dispose()
    positive = [case for case in cases if case["recall20"] is not None]
    negative = [case for case in cases if case["recall20"] is None]
    return dict(metrics={
        "positiveCases": len(positive), "emptyAnswerCases": len(negative),
        "precision3": round(sum(case["precision3"] for case in positive) / len(positive), 4),
        "recall20": round(sum(case["recall20"] for case in positive) / len(positive), 4),
        "ndcg3": round(sum(case["ndcg3"] for case in positive) / len(positive), 4),
        "top3Unrelated": sum(case["falsePositiveCount"] for case in cases),
        "emptyAnswerFalsePositives": sum(case["falsePositiveCount"] for case in negative),
    }, cases=cases)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--baseline-ref", default="84e1de7")
    parser.add_argument("--output")
    args = parser.parse_args()
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    report = dict(labelProvenance=fixture["labelProvenance"],
        baselineRef=args.baseline_ref, baseline=evaluate(fixture, baseline_search(args.baseline_ref)),
        current=evaluate(fixture, OpportunitySearch))
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value["metrics"] for key, value in report.items()
                      if key in {"baseline", "current"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
