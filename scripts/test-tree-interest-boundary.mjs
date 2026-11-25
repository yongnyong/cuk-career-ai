import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

registerHooks({ resolve(s, c, next) {
  return next(c.parentURL?.endsWith(".ts") && s.startsWith(".") && !s.endsWith(".ts") ? s + ".ts" : s, c);
}});
const lib = resolve(import.meta.dirname, "../web/src/lib");
const load = name => import(pathToFileURL(resolve(lib, name + ".ts")).href);
const { buildCareerPath, buildTree } = await load("engine");
const { PERSONAS } = await load("data/personas");
const { SEED_OPPORTUNITIES } = await load("data/opportunities");
const { CAMPUS_NODES } = await load("data/campusNodes");
const { JOBS } = await load("data/catalog");
const catalog = JSON.parse(readFileSync(resolve(lib, "data/startupCatalog.json"), "utf8"));
const now = new Date("2026-11-22T09:00:00+09:00");
const blocked = ["SK-BMC", "SK-IR", "SK-BIZPLAN", "SK-IDEA", "SK-MVP", "PR-ASSUMPTION",
  ...CAMPUS_NODES.filter(n => /창업|사업화/.test(n.name)).map(n => n.id)];
const stale = blocked.map(skillId => ({ skillId, basis: "activity", status: "gap",
  reference: { id: "old-startup-event", title: "창업경진대회", scope: "campus", historical: false } }));
for (const id of ["demo-minji", "demo-jiwoo"]) {
  const persona = PERSONAS.find(p => p.id === id);
  const profile = { ...persona.profile, completedPreparation: { [persona.profile.jobId]: blocked },
    skills: { ...persona.profile.skills, ...Object.fromEntries(blocked.map(id => [id, "self"])) } };
  const path = buildCareerPath(profile, SEED_OPPORTUNITIES, now, stale, catalog);
  assert(path.tree.length > 0);
  assert(!path.tree.some(n => blocked.includes(n.skill)));
  assert(!blocked.includes(path.recommendedQuest?.skillId));
  assert(path.tree.every(n => n.prereq.every(id => path.tree.some(parent => parent.skill === id))));
  console.log(id, path.tree.length, "employment nodes, no startup leakage");
}
// Template nodes, old completion records and extra skills all pass the same boundary.
for (const job of JOBS) {
  // Main's explicit startup/business templates take precedence over inferred additions.
  if (job.nodes.some(n => blocked.includes(n.skill))) continue;
  const profile = { ...PERSONAS[0].profile, jobId: job.id, careerInterest: "employment" };
  assert(!buildTree(profile, [], now, blocked).some(n => blocked.includes(n.skill)), job.id);
}
const founder = PERSONAS.find(p => p.id === "demo-seojun").profile;
const startup = buildCareerPath(founder, SEED_OPPORTUNITIES, now, [], catalog);
assert(startup.tree.some(n => n.skill === "SU-DOC-pitch-deck"));
console.log("Startup presentation node preserved; all employment templates checked.");
