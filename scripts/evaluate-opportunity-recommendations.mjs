import { registerHooks } from "node:module";
import { spawnSync, execFileSync } from "node:child_process";
import { writeFileSync, unlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { dirname, resolve } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

registerHooks({ resolve(s, c, next) {
  return next(c.parentURL?.endsWith(".ts") && s.startsWith(".") && !s.endsWith(".ts") ? s + ".ts" : s, c);
}});
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const lib = resolve(root, "web/src/lib");
const beforeRef = "84e1de7";
const baselinePath = resolve(tmpdir(), "cuk-retrieval-baseline-" + randomUUID() + ".ts");
const original = execFileSync("git", ["show", beforeRef + ":web/src/lib/opportunitySearch.ts"], { cwd: root, encoding: "utf8" });
writeFileSync(baselinePath, original.replace(/from "\.\/([^"]+)"/g,
  (_, name) => 'from "' + pathToFileURL(resolve(lib, name + ".ts")).href + '"'));

try {
  const before = await import(pathToFileURL(baselinePath).href);
  const current = await import(pathToFileURL(resolve(lib, "opportunitySearch.ts")).href);
  const { PERSONAS } = await import(pathToFileURL(resolve(lib, "data/personas.ts")).href);
  const { recommend, preparationReferences } = await import(pathToFileURL(resolve(lib, "engine.ts")).href);
  const cases = ["demo-minji", "demo-jiwoo"].flatMap(id => [3, 4].map(grade => ({
    id: id + "-" + grade, profile: { ...PERSONAS.find(p => p.id === id).profile, grade },
    kind: "employment", focus: "",
  })));
  for (const goal of ["시제품 제작비", "판로 상담"]) cases.push({
    id: "startup-" + goal, profile: PERSONAS.find(p => p.id === "demo-seojun").profile,
    plan: { idea: "학원 상담 요약 AI", customer: "학원장", goal }, kind: "startup", focus: goal,
  });
  const queries = cases.map(c => ({
    ...c, beforeQuery: before.opportunityQuery(c.profile, c.plan),
    query: current.opportunityQuery(c.profile, c.plan),
  }));
  const python = String.raw`
import json, os, sqlite3, sys
from pathlib import Path
os.environ["CAREER_DATABASE_URL"]="sqlite:///:memory:"
from app.career_db import CareerBase
from app.career.opportunity_search import OpportunitySearch, current_postings
from app.career.evaluate_retrieval import baseline_search
from app.startup_catalog import catalog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
with sqlite3.connect(Path("career.db").resolve().as_uri()+"?mode=ro",uri=True) as db:
    rows=[json.loads(r[0]) for r in db.execute("select data from postings where data is not null")]
if Path("startup.db").is_file():
    with sqlite3.connect(Path("startup.db").resolve().as_uri()+"?mode=ro",uri=True) as db:
        db.row_factory=sqlite3.Row
        rows.extend(catalog(db)["opportunities"])
rows=current_postings(rows)
queries=json.load(sys.stdin)
results=[]
for search_type,field in [(baseline_search("84e1de7"),"beforeQuery"),(OpportunitySearch,"query")]:
    engine=create_engine("sqlite://")
    CareerBase.metadata.create_all(engine)
    search=search_type(sessionmaker(engine,expire_on_commit=False),lambda:rows)
    results.append([search.search(q[field],q["kind"],focus=q["focus"],limit=500) for q in queries])
    engine.dispose()
print(json.dumps(dict(rows=rows,results=results)))
`;
  const process = spawnSync(resolve(root, "api/.venv/Scripts/python.exe"), ["-X", "utf8", "-c", python], {
    cwd: resolve(root, "api"), input: JSON.stringify(queries), encoding: "utf8", maxBuffer: 40e6,
  });
  if (process.status !== 0) throw new Error(process.stderr);
  const { rows, results } = JSON.parse(process.stdout);
  const now = new Date("2026-11-24T09:00:00+09:00");
  const summary = recommendations => ({
    count: recommendations.length,
    top3: recommendations.slice(0, 3).map(r => ({ id: r.opp.id, title: r.opp.title,
      verdict: r.verdict, sources: r.retrievalEvidence ?? [] })),
  });
  const report = {
    baselineRef: beforeRef, asOf: now.toISOString(), postings: rows.length,
    note: "실제 로컬 공개 공고의 동작 비교. 독립적인 적합성 정답표가 없어 추천 개선율을 계산하지 않음.",
    cases: cases.map((c, i) => ({
      id: c.id, beforeQuery: queries[i].beforeQuery, currentQuery: queries[i].query,
      rules: summary(recommend(rows, c.profile, now)),
      rulesPreparation: summary(preparationReferences(rows, c.profile, now)),
      before: summary(before.retrievedRecommendations(rows, c.profile, now, results[0][i])),
      current: summary(current.retrievedRecommendations(rows, c.profile, now, results[1][i])),
      beforePreparation: summary(before.retrievedRecommendations(rows, c.profile, now, results[0][i], "preparation")),
      currentPreparation: summary(current.retrievedRecommendations(rows, c.profile, now, results[1][i], "preparation")),
    })),
  };
  const output = resolve(root, "docs/eval/real-recommendation-v1-results.json");
  writeFileSync(output, JSON.stringify(report, null, 2) + "\n");
  const compact = result => ({ count: result.count, top3: result.top3.map(item => item.title) });
  for (const c of report.cases) console.log(JSON.stringify({ id: c.id, before: compact(c.before), current: compact(c.current),
    prepBefore: c.beforePreparation.count, prepCurrent: c.currentPreparation.count }));
} finally {
  unlinkSync(baselinePath);
}
