import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { test } from "node:test";
registerHooks({ resolve(s,c,next) {
  return next(c.parentURL?.endsWith(".ts") && s.startsWith(".") && !s.endsWith(".ts") ? s + ".ts" : s, c);
}});
const { assessCredential, credentialProfileKey } = await import("../src/lib/credentialEligibility.ts");
const { buildCareerPath } = await import("../src/lib/engine.ts");
const { PERSONAS } = await import("../src/lib/data/personas.ts");
const base = PERSONAS.find(p => p.id === "demo-minji").profile;
const now = new Date("2026-11-24T09:00:00+09:00");

test("engineer academic path changes at final year without assuming major recognition", () => {
  assert.equal(assessCredential("SK-ELEC-PE", { ...base, grade: 3 }).status, "prepare");
  assert.equal(assessCredential("SK-ELEC-PE", { ...base, grade: 4 }).status, "check");
  assert.equal(assessCredential("CERT-BIGDATA", { ...base, departmentId: "psychology", grade: 4 }).status, "check");
  assert.equal(assessCredential("SK-SQLD", { ...base, grade: 1 }).status, "ready");
  assert.equal(assessCredential("SK-SQLD", { ...base, grade: 4 }).status, "ready");
});
test("clinical practice is an additional requirement and unknown history stays unknown", () => {
  const student = { ...base, grade: 4 };
  assert.equal(assessCredential("PSY-C-CLIN", student).status, "check");
  const facts = clinicalPractice => ({ ...student, credentialFacts: { "PSY-C-CLIN": { clinicalPractice } } });
  assert.equal(assessCredential("PSY-C-CLIN", facts("none")).status, "prepare");
  assert.equal(assessCredential("PSY-C-CLIN", facts("training_year")).status, "check");
  assert.equal(assessCredential("PSY-C-CLIN", facts("work_two_years")).status, "check");
});
test("official self-check supports other paths and expires when academic facts change", () => {
  const student = { ...base, grade: 3 };
  const checked = { ...student, credentialFacts: { "SK-ELEC-PE": {
    eligibility: "confirmed", profileKey: credentialProfileKey(student),
  } } };
  assert.equal(assessCredential("SK-ELEC-PE", checked).status, "ready");
  assert.equal(assessCredential("SK-ELEC-PE", { ...checked, grade: 4 }).status, "check");
  assert.equal(assessCredential("SK-ELEC-PE", { ...checked, status: "휴학" }).status, "prepare");
  assert.equal(assessCredential("SK-ELEC-PE", { ...checked, departmentId: "psychology" }).status, "prepare");
});
test("an unfinished engineer credential cannot lead the quest until eligibility is confirmed", () => {
  const profile = { ...base, departmentId: "ice", jobId: "ice-analog", grade: 4 };
  const before = buildCareerPath(profile, [], now, []);
  assert.notEqual(before.recommendedQuest?.skillId, "SK-ELEC-PE");
  assert.notEqual(before.recommendedQuest?.skillId, "ICE-C-ELECTRIC");
  const ready = { ...profile, credentialFacts: { "SK-ELEC-PE": {
    eligibility: "confirmed", profileKey: credentialProfileKey(profile),
  } } };
  const after = buildCareerPath(ready, [], now, []);
  // Main added circuit prerequisites. Confirmed eligibility does not bypass them.
  const credential = after.tree.find(n => n.skill === "SK-ELEC-PE");
  if (credential.locked) assert.notEqual(after.recommendedQuest?.skillId, credential.skill);
  assert(after.tree.some(n => n.skill === "SK-ELEC-PE" && n.credentialEligibility.status === "ready"));
  assert.deepEqual(before.tree.map(n => n.skill), after.tree.map(n => n.skill));
  const completed = buildCareerPath({ ...profile, skills: { ...profile.skills, "SK-ELEC-PE": "self" } }, [], now, []);
  assert.equal(completed.tree.find(n => n.skill === "SK-ELEC-PE").state, "self");
});
test("AI research stays project-led and unknown certificates never inherit engineer rules", () => {
  for (const grade of [3, 4]) {
    const path = buildCareerPath({ ...base, grade }, [], now, []);
    assert(!["SK-ELEC-PE", "CERT-BIGDATA", "PSY-C-CLIN"].includes(path.recommendedQuest?.skillId));
  }
  assert.equal(assessCredential("UNKNOWN-CREDENTIAL", base), undefined);
});
