import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { test } from "node:test";
import { readFileSync } from "node:fs";
registerHooks({ resolve(s,c,n) { return n(c.parentURL?.endsWith(".ts") && s.startsWith(".") && !s.endsWith(".ts") ? s+".ts" : s,c); } });
const { buildStartupPath } = await import("../src/lib/startup.ts");
const { PERSONAS } = await import("../src/lib/data/personas.ts");
const { questOutcome } = await import("../src/lib/questOutcome.ts");
const { layoutTree } = await import("../src/lib/treeLayout.ts");
const cat = JSON.parse(readFileSync(new URL("../src/lib/data/startupCatalog.json", import.meta.url)));
const profile = PERSONAS.find(x => x.profile.careerInterest === "startup").profile;

test("Seojun demo exposes fourteen personalized nodes and four completed implementations", () => {
 const plan = JSON.parse(readFileSync(new URL("../src/lib/data/startupDemo.json", import.meta.url)));
 const path = buildStartupPath(profile, cat.opportunities, new Date("2026-11-27"), cat, plan);
 assert.equal(path.tree.length, 14);
 assert.equal(path.tree.filter(n => n.state !== "none").length, 4);
 assert.equal(path.tree.filter(n => n.route.domain === "common").length, 3);
 assert.equal(new Set(path.tree.map(n => n.startupSection)).size, 4);
 assert.equal(path.recommendedQuest.skillId, "SUP-DEMO-tree_test");
 assert(new Set(path.tree.map(n => n.depth)).size >= 3);
 const byId = new Map(path.tree.map(n => [n.skill, n]));
 for (const node of path.tree) for (const parent of [...node.prereq, ...node.sequence]) {
   assert(byId.get(parent).depth < node.depth);
 }
 assert.equal(byId.get('SUP-DEMO-tree_test').locked, false);
 assert(byId.get('SUP-DEMO-slides').depth > byId.get('SUP-DEMO-application').depth);
});
test("personal work is recommended in its own domain and completed work survives a goal change", () => {
 const old = { id:"SUP-demo",title:"학원장 미팅용 시연본",completion:"가상 입력과 수정 화면 저장",reason:"고객 미팅",action:"demo",completed:true,active:false,reuse:[] };
 const next = { ...old,id:"SUP-next",title:"우리 팀이 지원할 창업 공고 선택",completed:false,active:true,reuse:[old.id] };
 const plan = { idea:"AI",customer:"학원장",artifacts:"시제품",goal:"창업대회",action:"competition",turns:2,nodes:[next,old] };
 const path = buildStartupPath(profile,cat.opportunities,new Date("2026-11-23"),cat,plan);
 assert.equal(path.recommendedQuest.skillId,next.id);
 assert.equal(path.tree.find(n=>n.skill===old.id).state,"self");
 assert.equal(path.tree.find(n=>n.skill===next.id).route.domain,"specialist");
 assert.ok(path.tree.filter(n=>n.route.domain==="common").every(n=>["SU-PREP-problem", "SU-PREP-item", "SU-PREP-team-capability"].includes(n.skill)));
 assert.equal(questOutcome(path.tree.find(n=>n.skill===old.id)).completion,old.completion);
 assert.equal(path.tree.filter(n=>n.skill===old.id).length,1);
});

test("personal prerequisite and reused work appear above the dependent task", async () => {
  const first = { id: "SUP-first", title: "핵심 사용 흐름 시제품", action: "prototype",
    completion: "시제품 파일", reason: "시연에 필요", completed: false, active: true,
    reuse: [], requires: [], stage: 2 };
  const next = { ...first, id: "SUP-demo", title: "고객 시연본", action: "demo",
    reuse: [first.id], requires: [first.id], stage: 3 };
  const plan = { idea: "재고 예측", customer: "서점주", artifacts: "", goal: "시연", action: "demo", turns: 1, nodes: [first, next] };
  const path = buildStartupPath(profile, cat.opportunities, new Date("2026-11-23"), cat, plan);
  const tree = path.tree.filter(n => n.personalCompletion);
  assert.equal(path.recommendedQuest.skillId, first.id);
  assert.ok(tree.find(n => n.skill === next.id).locked);
  const layout = await layoutTree(tree);
  assert.ok(layout.positions.get(first.id).y < layout.positions.get(next.id).y);
  first.completed = true;
  next.requires = [];
  const updated = buildStartupPath(profile, cat.opportunities, new Date("2026-11-23"), cat, plan);
  assert.equal(updated.recommendedQuest.skillId, next.id);
  assert.equal(updated.tree.find(n => n.skill === next.id).locked, false);
  next.completed = true;
  assert.equal(buildStartupPath(profile, cat.opportunities, new Date("2026-11-23"), cat, plan).recommendedQuest, null);
});

test("personal submission retains exact source evidence and completed snapshots", () => {
  const posting = cat.opportunities[0];
  const node = { id: "SUP-submission", action: "submission", title: "사업계획서 준비",
    completion: "지정 양식에 작성", reason: "선택한 공고", active: true, completed: false,
    reuse: [], stage: 4, evidence: [{ posting_id: posting.id, version: 1, title: "사업계획서",
      quote: "원문 제출 문구", source_url: "https://example.edu/notice" }] };
  const plan = { idea: "AI", customer: "학원장", artifacts: "시제품", goal: "대회", action: "competition", turns: 1, nodes: [node] };
  const tree = buildStartupPath(profile, cat.opportunities, new Date("2026-11-23"), cat, plan).tree;
  const submission = tree.find(n => n.skill === node.id);
  assert.equal(submission.evidence[0].reference.quote, "원문 제출 문구");
  assert.equal(submission.opportunities[0].id, posting.id);
});
