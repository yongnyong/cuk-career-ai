import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { test } from "node:test";

registerHooks({ resolve(s, c, next) {
  return next(c.parentURL?.endsWith(".ts") && s.startsWith(".") && !s.endsWith(".ts") ? s + ".ts" : s, c);
} });
const { recommend, evaluate, buildCareerPath, preparationReferences, isOpen } = await import("../src/lib/engine.ts");
const { PERSONAS } = await import("../src/lib/data/personas.ts");
const now = new Date("2026-11-22T12:00:00+09:00");
const student = PERSONAS.find(p => p.id === "demo-yuna").profile;
const notice = (id, patch = {}) => ({
  id, title: id, org: "검증용 기업", type: "채용", jobs: [], required: [], preferred: [],
  reviewed: true, isVirtual: false, sections: [], source: { url: "https://example.org/jobs/" + id },
  versions: [{ version: 1, deadline: "2026-12-20T23:59:00+09:00" }], ...patch,
});
const mapping = (namedJobs, departmentIds) => ({ namedJobs, reviewedJobs: [], departmentIds });

test("preparation references retain past, upcoming and ineligible role postings with their original verdict", () => {
  const exact = { employmentMatch: mapping(["mtc-video"], ["media-tech"]) };
  const available = notice("available", exact);
  const upcoming = notice("upcoming", { ...exact, opensAt: "2026-12-03T09:00:00+09:00" });
  const expired = notice("expired", { ...exact, versions: [{ version: 1, checkedAt: "2026-11-22", deadline: "2026-10-01" }] });
  const ineligible = notice("ineligible", { ...exact, required: [{ key: "degree", degree: "master", src: "§1" }] });
  for (const o of [available, upcoming, ineligible]) o.versions[0].checkedAt = "2026-11-22";
  const postings = [available, upcoming, expired, ineligible, notice("unclassified")];
  assert.equal(isOpen(upcoming, now), false);
  assert.deepEqual(recommend(postings, student, now).map(r => r.opp.id), ["available"]);
  const references = preparationReferences(postings, student, now);
  assert.deepEqual(new Set(references.map(r => r.opp.id)), new Set(["upcoming", "expired", "ineligible"]));
  assert.equal(references.find(r => r.opp.id === "ineligible").verdict, "fail");
  assert.match(references.find(r => r.opp.id === "expired").reasons[0], /지난 공고/);
});

test("unclassified hiring is excluded and adjacent opportunities cannot outrank the goal occupation", () => {
  const exact = notice("video", { employmentMatch: mapping(["mtc-video"], ["media-tech"]) });
  const adjacent = notice("software", { jobs: ["mtc-video"], employmentMatch: mapping(["cs-dev"], ["cs"]),
    preferred: Object.keys(student.skills), versions: [{ version: 1, deadline: "2026-11-23" }] });
  const result = recommend([notice("unknown"), adjacent, exact], student, now);
  assert.deepEqual(result.map(r => r.opp.id), ["video", "software"]);
  assert.match(result[1].reasons[0], /같은 계열/);
  assert.equal(recommend([notice("intern", { type: "현장실습" })], student, now).length, 0);
  assert.equal(recommend([notice("scholarship", { type: "장학" })], student, now).length, 1);
});

test("mandatory exact majors exclude different majors while related and multi-role conditions stay unresolved", () => {
  const condition = { key: "department", departmentIds: ["cs"], majors: [], src: "§1", label: "컴퓨터공학 전공 필수", scope: "role" };
  const opp = notice("restricted", { required: [condition], employmentMatch: mapping(["cs-dev"], ["cs"]) });
  assert.equal(evaluate(opp, student).overall, "fail");
  assert.deepEqual(recommend([opp], student, now), []);
  for (const change of [{ related: true }, { scope: "posting" }, { departmentIds: [] }]) {
    assert.equal(evaluate({ ...opp, required: [{ ...condition, ...change }] }, student).overall, "check");
  }
  assert.equal(evaluate(opp, { ...student, departmentId: "cs" }).overall, "pass");
});

test("a preferred major supports discovery without becoming a mandatory filter or a goal-role signal", () => {
  const quote = "미디어기술콘텐츠학과 전공 우대";
  const opp = notice("major-preference", {
    employmentMatch: { ...mapping([], []), majorConditions: [{
      basis: "preferred", departmentIds: ["media-tech"], fields: [], related: false,
      unrestricted: false, scope: "role", src: "§1", quote,
    }] },
    sections: [{ id: "§1", text: "SQLD 보유 우대" }],
    preparationEvidence: [{ key: "sql_certificate", basis: "preferred", scope: "role", src: "§1", quote: "SQLD 보유 우대" }],
  });
  assert.match(recommend([opp], student, now)[0].reasons[0], /내 전공 우대/);
  assert.equal(evaluate(opp, student).overall, "pass");
  assert(!buildCareerPath(student, [opp], now, []).tree.some(n => n.skill === "SK-SQLD"));
});
