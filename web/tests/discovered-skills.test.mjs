import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { test } from "node:test";

registerHooks({ resolve(s, c, next) {
  return next(c.parentURL?.endsWith(".ts") && s.startsWith(".") && !s.endsWith(".ts") ? s + ".ts" : s, c);
} });
const { buildCareerPath } = await import("../src/lib/engine.ts");
const { questOutcome } = await import("../src/lib/questOutcome.ts");
const { routeFor } = await import("../src/lib/treeProgression.ts");
const { PERSONAS } = await import("../src/lib/data/personas.ts");
const p = { ...PERSONAS[0].profile, jobId: "marketer", skills: {} };
const now = new Date("2026-11-23T12:00:00+09:00");
function post(id, org, job = "marketer", kind = "tool", term = "FluxDraw") {
  const quote = term + (kind === "tool" ? " 활용 경험 우대" : kind === "artifact" ? " 제출 필수" : " 자격증 보유자 우대");
  return { id, org, title: id, jobs: [job], employmentMatch: { namedJobs: [job], reviewedJobs: [] },
    type: "채용", reviewed: true, isVirtual: false, required: [], preferred: [], sections: [{ id: "s", text: quote }],
    discoveryEvidence: [{ kind, term, quote, basis: kind === "artifact" ? "required" : "preferred", src: "s", scope: "role" }],
    versions: [{ version: 1, checkedAt: "2026-11-20", deadline: "2026-12-01" }], source: { url: "https://example.org/" + id } };
}
const automatic = (posts, student = p) => buildCareerPath(student, posts, now, []).tree.filter(n => n.skill.startsWith("AUTO-"));

test("two independent employers generate one optional work sample with citations and a durable completion id", () => {
  const a = post("a", "(주)봄");
  const b = post("b", "가을");
  const [node] = automatic([a, b]);
  assert.equal(node.name, "FluxDraw 실무 예제 제작");
  assert.equal(node.required, false);
  assert.deepEqual(node.evidence.map(s => s.reference.quote), [a.sections[0].text, b.sections[0].text]);
  assert.equal(questOutcome(node).label, "추천 작업물");
  assert.equal(routeFor(node).domain, "specialist");
  assert.equal(buildCareerPath(p, [a, b], now, []).recommendedQuest.skillId, node.skill);
  const student = { ...p, skills: { [node.skill]: "self" }, completedPreparation: { marketer: [node.skill] } };
  const [saved] = automatic([], student);
  assert.equal(saved.state, "self");
  assert.ok(questOutcome(saved).completion);
  assert.notEqual(buildCareerPath(student, [a, b], now, []).recommendedQuest?.skillId, node.skill);
});

test("reposts, broad role links, invalid quotations and superseded posting versions cannot qualify", () => {
  const a = post("a", "(주)봄");
  const b = post("b", "가을");
  for (const second of [
    post("b", "주식회사 봄"), post("b", "가을", "cs-dev"),
    { ...b, source: { url: a.source.url + "?utm_source=copy#mirror" } },
    { ...b, reviewed: false }, { ...b, isVirtual: true }, { ...b, sections: [] },
    { ...b, employmentMatch: { namedJobs: [], reviewedJobs: [] } },
    { ...b, discoveryEvidence: [{ ...b.discoveryEvidence[0], scope: "posting" }] },
    { ...b, discoveryEvidence: [{ ...b.discoveryEvidence[0], term: "Invented" }] },
  ]) assert.equal(automatic([a, second]).length, 0);
  assert.equal(automatic([a, b, { ...b, versions: [{ ...b.versions[0], version: 2 }], discoveryEvidence: [] }]).length, 0);
});

test("common requires a second occupation with independently corroborated demand", () => {
  const local = [post("a", "기업A"), post("b", "기업B")];
  const other = [post("c", "기업C", "cs-dev"), post("d", "기업D", "cs-dev")];
  assert.equal(routeFor(automatic([...local, other[0]])[0]).domain, "specialist");
  assert.equal(routeFor(automatic([...local, ...other])[0]).domain, "common");
  assert.equal(routeFor(automatic([...local, ...other.map(o => ({ ...o, org: "기업A" }))])[0]).domain, "specialist");
});

test("repeated word-processing and presentation evidence gives a concrete pair of deliverables", () => {
  const posts = ["a", "b"].map(id => {
    const p = post(id, id, "marketer", "tool", "Example Suite");
    const quote = id === "a" ? "워드 및 파워포인트 등 Example Suite 활용 가능자" : "Example Suite 능숙자 (Word, PowerPoint)";
    return { ...p, discoveryEvidence: [{ ...p.discoveryEvidence[0], quote }], sections: [{ id: "s", text: quote }] };
  });
  const [n] = automatic(posts);
  assert.equal(questOutcome(n).title, "Example Suite 기획 문서·발표자료 제작");
  assert.equal(questOutcome(n).label, "추천 작업물");
});

test("a named credential and an explicitly requested artifact produce distinct direct outcomes", () => {
  for (const [kind, term, expected] of [["credential", "패턴제작기능사", "패턴제작기능사 취득"], ["artifact", "배선 설계서", "배선 설계서 완성"]]) {
    const [node] = automatic(["a", "b"].map(id => post(id, id, "marketer", kind, term)));
    assert.equal(questOutcome(node).title, expected);
    assert.ok(node.evidence.every(e => e.preparation.kind === "direct"));
  }
});
