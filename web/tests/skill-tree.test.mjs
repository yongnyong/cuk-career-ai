import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { test } from "node:test";
import { groupTreeSignals, selectRecommendedQuest } from "../src/lib/skillTree.ts";

const sql = { skill: "SK-SQL", kind: "역량", required: true, state: "none", locked: false };
const sqld = { skill: "SK-SQLD", kind: "자격증", required: false, prereq: [sql.skill], state: "none", locked: true };
const adsp = { skill: "SK-ADSP", kind: "자격증", required: false, state: "none", locked: false };
const signal = (skillId, id = "posting-1", status = "gap") => ({
  skillId, basis: "preferred", status,
  reference: { id, title: id, url: `https://example.org/${id}`, historical: true },
});

test("selects one relevant next step from the full graph and takes prerequisites first", () => {
  const signals = groupTreeSignals([signal(sqld.skill)]);
  const tree = [sql, sqld, adsp];
  const recommended = selectRecommendedQuest(tree, signals, [], new Set());
  assert.equal(recommended.skillId, sql.skill);
  assert.equal(recommended.targetSkill, sqld.skill);
  assert.equal(recommended.signals[0].reference.id, "posting-1");

  const afterSql = [{ ...sql, state: "self" }, { ...sqld, locked: false }];
  assert.equal(selectRecommendedQuest(afterSql, signals, [], new Set()).skillId, sqld.skill);

  const newSignals = groupTreeSignals([signal(adsp.skill, "posting-2")]);
  assert.equal(selectRecommendedQuest(tree, newSignals, [], new Set()).skillId, adsp.skill);
});

test("separates already matched, unconfirmed, and below-target scores", () => {
  const toeic = { ...adsp, skill: "SK-TOEIC", kind: "어학", state: "self" };
  const matched = groupTreeSignals([signal(toeic.skill, "a", "matched")]);
  assert.equal(selectRecommendedQuest([toeic], matched, [], new Set()), null);
  const unconfirmed = groupTreeSignals([signal(toeic.skill, "b", "unknown")]);
  assert.equal(selectRecommendedQuest([toeic], unconfirmed, [], new Set()).actionKind, "verify");
  assert.equal(selectRecommendedQuest([toeic], matched, [], new Set([toeic.skill])).actionKind, "improve");
  assert.equal(toeic.state, "self");
});

test("deduplicates versions and source URLs regardless of input order", () => {
  const original = signal(sqld.skill);
  const old = { ...original, reference: { ...original.reference, version: 1 } };
  const latest = { ...original, reference: { ...original.reference, version: 2 } };
  const duplicate = { ...original, reference: { ...original.reference, id: "another-id", url: original.reference.url + "#detail" } };
  for (const order of [[old, duplicate, latest], [latest, duplicate, old]]) {
    assert.deepEqual(groupTreeSignals(order).get(sqld.skill), [latest]);
  }
});

test("keeps a graduation-only posting as preparation evidence without offering it to a sophomore", async () => {
  // The app bundler resolves extensionless TypeScript imports in the engine.
  const hooks = registerHooks({
    resolve(specifier, context, nextResolve) {
      if (context.parentURL?.endsWith(".ts") && specifier.startsWith(".") && !specifier.endsWith(".ts")) {
        return nextResolve(specifier + ".ts", context);
      }
      return nextResolve(specifier, context);
    },
  });
  try {
    const { buildCareerPath, recommend } = await import("../src/lib/engine.ts");
    const now = new Date("2026-11-18T10:00:00+09:00");
    const profile = { departmentId: "ai", jobId: "data-analyst", grade: 2, status: "재학", interests: [], skills: {} };
    const posting = {
      id: "fixture", type: "채용", isVirtual: false, reviewed: true, confidence: 1,
      title: "데이터 분석 신입", org: "예시 기업", source: { url: "https://example.org/sql" },
      jobs: ["data-analyst"], required: [{ key: "degree", degree: "bachelor", label: "학사 이상", src: "§2" }],
      preferred: ["SK-SQLD"], versions: [{ version: 1, deadline: "2026-11-30T18:00:00+09:00" }],
    };
    const { tree, recommendedQuest } = buildCareerPath(profile, [posting], now, []);
    assert.equal(recommendedQuest.skillId, "SK-SQL");
    assert.equal(recommendedQuest.signals[0].reference.id, posting.id);
    assert.equal(tree.find((node) => node.skill === "SK-SQLD").opportunities.length, 0);
    assert.equal(recommend([posting], profile, now).length, 0);
    const afterSql = buildCareerPath({ ...profile, skills: { "SK-SQL": "self" } }, [posting], now, []);
    assert.equal(afterSql.recommendedQuest.skillId, "SK-SQLD");
    assert.equal(afterSql.treeProgress.exp, 60);
    const past = buildCareerPath(profile, [posting], new Date("2026-12-02T12:00:00+09:00"), []);
    assert.equal(past.recommendedQuest.signals[0].reference.historical, true);

    const sales = { ...profile, departmentId: "business", jobId: "overseas-sales" };
    const quote = "기본우대 프리젠테이션 능력우수자";
    const imported = { ...posting, id: "hist-sample", jobs: ["overseas-sales"], required: [],
      preferred: [], sections: [{ id: "역량1", text: quote }],
      skillEvidence: [{ skill: "SK-PPT", basis: "preferred", quote, src: "역량1", scope: "role" }],
    };
    const baseline = buildCareerPath(sales, [], now, []);
    const connected = buildCareerPath(sales, [imported], now, []);
    assert.equal(baseline.recommendedQuest.skillId, "SK-TOEIC");
    assert.equal(connected.recommendedQuest.skillId, "SK-PPT");
    assert(connected.tree.some((node) => node.skill === "SK-PPT"));
    assert.equal(connected.recommendedQuest.signals[0].reference.quote, quote);
    imported.sections[0].text = "다른 문장";
    assert.equal(buildCareerPath(sales, [imported], now, []).recommendedQuest.skillId, "SK-TOEIC");
  } finally {
    hooks.deregister();
  }
});
