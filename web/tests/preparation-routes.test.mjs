import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { test } from "node:test";

const hooks = registerHooks({
  resolve(specifier, context, next) {
    return next(context.parentURL?.endsWith(".ts") && specifier.startsWith(".") && !specifier.endsWith(".ts")
      ? specifier + ".ts" : specifier, context);
  },
});
const { preparationSignals, replacedPreparationSignal } = await import("../src/lib/preparationRoutes.ts");
const { buildCareerPath, evaluate, recommend } = await import("../src/lib/engine.ts");
const { PERSONAS } = await import("../src/lib/data/personas.ts");
const { jobById, skillById, SKILLS } = await import("../src/lib/data/catalog.ts");
const { POSTING_PROJECTS } = await import("../src/lib/data/postingProjects.ts");
hooks.deregister();

const ref = { id: "role-test", title: "근거 검증용 공고", url: "https://example.org/posting", historical: false };
const analyst = new Set(["SK-SQL", "SK-SQLD"]);
const fact = (key, quote, basis = "preferred") => ({ key, quote, basis, scope: "role", src: quote });
function posting(...entries) {
  return { reviewed: true, isVirtual: false, preparationEvidence: entries,
    sections: entries.map(({ quote, src }) => ({ id: src, text: quote })) };
}
const targets = (p, skills = {}, template = analyst) => preparationSignals({ skills }, p, template, ref);

test("new posting projects have distinct catalog IDs and require a role citation to enter a tree", () => {
  assert.equal(new Set(SKILLS.map(s => s.id)).size, SKILLS.length);
  const now = new Date("2026-11-19");
  const student = { ...PERSONAS[0].profile, jobId: "marketer" };
  const treeFor = opp => buildCareerPath(student, opp ? [opp] : [], now, []).tree;
  const without = treeFor(null);
  for (const project of POSTING_PROJECTS) {
    assert.equal(skillById(project.id)?.name, project.name);
    assert(!without.some(n => n.skill === project.id));
    const observed = fact(project.id, "검증된 직무 요건 문장");
    const opp = { ...posting(observed), id: project.id, title: "연결 테스트", jobs: ["marketer"], org: "테스트",
      type: "채용", source: {url: ref.url}, versions: [{version: 1, deadline: "2026-12-01"}], required: [], preferred: [] };
    const signal = treeFor(opp).find(n => n.skill === project.id)?.preparationSignals[0];
    assert.equal(signal.preparation.kind, "suggested");
    assert.equal(signal.preparation.completion, project.completion);
    assert.equal(signal.reference.quote, observed.quote);
    assert(!treeFor({ ...opp, ...posting({ ...observed, scope: "posting" }) }).some(n => n.skill === project.id));
  }
});

test("keeps the whole track alongside three distinct cited outputs and a completed skill outside the track", () => {
  const student = { ...PERSONAS[0].profile, jobId: "marketer", skills: { "SK-INFO-PE": "verified" } };
  const entries = [fact("portfolio", "포트폴리오 제출"), fact("writing_sample", "작성 원고 제출"),
    fact("spreadsheet", "엑셀 우대"), fact("credential:SK-INFO-PE", "정보처리기사 우대")];
  const opportunity = { ...posting(...entries), id: "marketing", org: "테스트 기업", title: "마케터", source: { url: ref.url },
    jobs: ["marketer"], type: "채용", versions: [{ version: 1, deadline: "2026-12-01" }], preferred: [], required: [] };
  const now = new Date("2026-11-19");
  const path = (opps) => buildCareerPath(student, opps, now, []);
  const { tree, recommendedQuest } = path([opportunity, opportunity]);
  const ids = new Set(tree.map(n => n.skill));
  for (const {skill} of jobById(student.jobId).nodes) assert(ids.has(skill));
  for (const skill of ["SK-PORT", "SK-WRITING-SAMPLE", "SK-SPREADSHEET", "SK-INFO-PE"]) {
    assert.equal(tree.find(n => n.skill === skill)?.evidence[0].reference.id, opportunity.id);
  }
  assert.equal(tree.find(n => n.skill === "SK-INFO-PE").state, "verified");
  assert.notEqual(recommendedQuest.skillId, "SK-INFO-PE");
  assert.equal(ids.size, tree.length);
  assert(!path([{ ...opportunity, jobs: ["electronics"] }]).tree.some(n => n.skill === "SK-SPREADSHEET"));
});

test("demo tracks have distinct follow-up work with stable IDs, prerequisites and completion", () => {
  // 데모 인물 중 직무 연습 과제가 정해진 세 트랙(AI 엔지니어·상담심리·사회복지)
  const minji = PERSONAS.find(({ id }) => id === "demo-minji").profile;
  const cases = [
    [{ ...minji, jobId: "ai-engineer", skills: { "SK-PY-01": "verified", "SK-DA": "self" } }, "PR-EDA"],
    [PERSONAS.find(({ id }) => id === "demo-jiwoo").profile, "PR-INTERVIEW"],
    [PERSONAS.find(({ id }) => id === "demo-haneul").profile, "PR-IMPACT"],
  ];
  const expected = cases.map(([, skill]) => skill);
  for (const [profile, skill] of cases) {
    const path = (p) => buildCareerPath(p, [], new Date("2026-11-19"), []);
    const {tree} = path(profile);
    const practice = tree.find(n => n.skill === skill);
    assert(practice?.practice.action && practice.practice.completion);
    assert(tree.filter(n => n.practice).length >= 3);
    assert(practice.prereq.every(id => tree.some(n => n.skill === id && n.depth < practice.depth)));
    assert.equal(practice.locked, false);
    assert.equal(practice.evidence, undefined);
    assert.equal(skillById(practice.skill).name, practice.name);
    const after = path({ ...profile, skills: { ...profile.skills, [practice.skill]: "self" } });
    assert.equal(after.tree.find(n => n.skill === practice.skill).state, "self");
    assert.notEqual(after.recommendedQuest?.skillId, practice.skill);
    assert(!after.tree.some(n => expected.includes(n.skill) && n.skill !== practice.skill));
  }
});

test("Minji can start AI preparation immediately and unlock deeper work by completing its prerequisite", () => {
  // 이 시나리오는 AI 엔지니어 트랙 기준이다(데모의 민지는 AI 연구원 트랙)
  const minji = { ...PERSONAS.find(({ id }) => id === "demo-minji").profile, jobId: "ai-engineer", skills: { "SK-PY-01": "verified", "SK-DA": "self" } };
  const now = new Date("2026-11-16T09:00:00+09:00");
  const treeFor = profile => buildCareerPath(profile, [], now, []).tree;
  const tree = treeFor(minji);
  const byId = new Map(tree.map(node => [node.skill, node]));
  assert.equal(byId.size, tree.length);
  const labelGuide = byId.get("PR-LABEL-GUIDE");
  assert.equal(labelGuide.locked, false);
  assert.deepEqual(labelGuide.prereq, []);
  assert.equal(byId.get("PR-TRAIN-REPLAY").locked, false);
  assert.equal(byId.get("PR-ERROR-TAXONOMY").locked, true);
  assert.equal(byId.get("PR-ERROR-TAXONOMY").evidence, undefined);
  const after = treeFor({ ...minji, skills: { ...minji.skills, "SK-ML-EVAL": "self" } });
  assert.equal(after.length, tree.length);
  assert.equal(after.find(node => node.skill === "PR-ERROR-TAXONOMY").locked, false);
  assert(!treeFor(PERSONAS[1].profile).some(node => node.skill === labelGuide.skill));
});

test("a SQL skill preference yields practice, an optional credential, or a query project by student record", () => {
  const opp = posting(fact("sql", "SQL 활용 능력 우대"));
  for (const [skills, expected] of [
    [{}, "SK-SQL"], [{ "SK-SQL": "self" }, "SK-SQLD"], [{ "SK-SQLD": "verified" }, "SK-SQL-PROJECT"],
  ]) {
    const [signal] = targets(opp, skills);
    assert.equal(signal.skillId, expected);
    assert.equal(signal.preparation.kind, "suggested");
    assert.equal(signal.reference.quote, "SQL 활용 능력 우대");
    assert(signal.preparation.action && signal.preparation.completion);
  }
  assert.equal(targets(opp, { "SK-SQL": "self" }, new Set())[0].skillId, "SK-SQL-PROJECT");
  const experience = posting(fact("sql", "SQL 활용 능력 우대"), fact("sql_project", "SQL로 데이터 분석 프로젝트를 수행한 경험"));
  const experienced = targets(experience, { "SK-SQL": "self" });
  assert(experienced.every((s) => s.skillId === "SK-SQL-PROJECT"));
  assert.equal(experienced[0].reference.quote, "SQL로 데이터 분석 프로젝트를 수행한 경험");
  assert(targets(experience, { "SK-SQL-PROJECT": "self" }).every((s) => s.status === "matched"));
});

test("explicit credentials and requested files retain a different attribution from practice samples", () => {
  const entries = [
    ["sql_certificate", "SQLD 우대", "SK-SQLD", "direct"],
    ["presentation", "자료 발표 역량", "SK-PRESENTATION-SAMPLE", "suggested"],
    ["proposal", "제안서 제출", "SK-PROPOSAL", "direct"],
    ["writing", "카피 작성 역량", "SK-WRITING-SAMPLE", "suggested"],
    ["writing_sample", "작성한 글 샘플 제출", "SK-WRITING-SAMPLE", "direct"],
    ["cad", "CAD 우대", "SK-CAD-DRAWING", "suggested"],
    ["drawing", "도면 제출", "SK-CAD-DRAWING", "direct"],
    ["portfolio", "포트폴리오 제출", "SK-PORT", "direct"],
    ["analysis", "데이터 분석 역량", "SK-ANALYSIS-REPORT", "suggested"],
    ["business_document", "문서작성 우수자", "SK-BRIEF", "suggested"],
    ["spreadsheet", "엑셀 활용 능숙자", "SK-SPREADSHEET", "suggested"],
    ["credential:SK-INFO-PE", "정보처리기사 보유", "SK-INFO-PE", "direct"],
  ];
  for (const [key, quote, target, kind] of entries) {
    const [signal] = targets(posting(fact(key, quote, "required")));
    assert.equal(signal.skillId, target);
    assert.equal(signal.preparation.kind, kind);
    assert.equal(signal.basis, "required");
    assert.equal(signal.reference.quote, quote);
  }
  assert.deepEqual(targets(posting(fact("credential:SK-SQL", "SQL 실습"))), []);
  assert.deepEqual(targets(posting(fact("credential:unknown", "미등록 자격"))), []);
});

test("only cited role-level facts can produce a route and an explicit threshold retains its status", () => {
  const quote = "컴퓨터활용능력 1급 필수";
  const basic = fact("credential:SK-COMP", quote, "required");
  const existing = { skillId: "SK-COMP", status: "gap", basis: "required", minimum: "1급",
    reference: { ...ref, quote, scope: "role" } };
  const [signal] = preparationSignals({ skills: { "SK-COMP": "self" } }, posting(basic), analyst, ref, [existing]);
  assert.equal(signal.minimum, "1급");
  assert.equal(signal.status, "gap");
  assert(replacedPreparationSignal(existing, [signal]));
  assert(!replacedPreparationSignal({ ...existing, skillId: "SK-INFO-PE" }, [signal]));
  for (const altered of [
    { ...posting(basic), sections: [] }, { ...posting(basic), reviewed: false },
    { ...posting(basic), isVirtual: true }, posting({ ...basic, scope: "posting" }),
  ]) assert.deepEqual(targets(altered), []);
  const legacy = { reviewed: true, isVirtual: false, sections: [{ id: "§1", text: "SQL 가능자 우대" }],
    skillEvidence: [{ skill: "SK-SQL", basis: "preferred", quote: "SQL 가능자 우대", src: "§1", scope: "role" }] };
  assert.equal(targets(legacy, { "SK-SQL": "self" })[0].skillId, "SK-SQLD");
  assert.deepEqual(targets({ ...legacy, skillEvidence: [], preferred: ["SK-SQL"] }), []);
});

test("first quest in the skill tree changes with SQL experience without changing application eligibility", () => {
  const now = new Date("2026-11-19T12:00:00+09:00");
  const profile = { departmentId: "data-science", jobId: "data-analyst", grade: 2, status: "재학", interests: [], skills: {} };
  const sqlFact = fact("sql", "SQL 활용 능력 우대");
  const opp = {
    ...posting(sqlFact), id: "sql-test", org: "테스트 기업", title: "데이터 분석 신입", source: { url: ref.url },
    jobs: ["data-analyst"], type: "채용", versions: [{ version: 1, deadline: "2026-11-30T18:00:00+09:00" }],
    preferred: ["SK-SQL"], required: [{ key: "grade", grades: [4], src: "§1", label: "4학년 대상" }],
    skillEvidence: [{ ...sqlFact, skill: "SK-SQL" }],
  };
  const path = (p, postings = [opp]) => buildCareerPath(p, postings, now, []);
  for (const [skills, expected] of [
    [{}, "SK-SQL"], [{ "SK-SQL": "self" }, "SK-SQLD"], [{ "SK-SQLD": "verified" }, "SK-SQL-PROJECT"],
  ]) {
    const student = { ...profile, skills };
    const { tree, recommendedQuest } = path(student);
    assert.equal(recommendedQuest.skillId, expected);
    assert.equal(recommendedQuest.signals[0].preparation.kind, "suggested");
    assert.equal(recommendedQuest.signals[0].reference.quote, sqlFact.quote);
    const node = tree.find((n) => n.skill === expected);
    assert.equal(node.preparationSignals[0].preparation.completion, recommendedQuest.signals[0].preparation.completion);
    assert.equal(node.opportunities.length, 0);
    assert.equal(evaluate(opp, student).overall, "fail");
    assert.deepEqual(recommend([opp], student, now), []);
  }
  const experienced = { ...profile, skills: { "SK-SQL": "self" } };
  const project = fact("sql_project", "SQL을 사용한 데이터 분석 프로젝트 수행 경험 우대");
  const explicit = fact("sql_certificate", "SQLD 자격증 우대");
  const projectOpportunity = { ...opp, ...posting(sqlFact, project) };
  const projectQuest = path(experienced, [projectOpportunity]).recommendedQuest;
  assert.equal(projectQuest.skillId, "SK-SQL-PROJECT");
  assert.equal(projectQuest.signals[0].reference.quote, project.quote);
  const certificateQuest = path(experienced, [{ ...opp, ...posting(explicit), preferred: ["SK-SQLD"], skillEvidence: [] }]).recommendedQuest;
  assert.equal(certificateQuest.skillId, "SK-SQLD");
  assert.equal(certificateQuest.signals[0].preparation.kind, "direct");

  const completed = { ...experienced, skills: { ...experienced.skills, "SK-SQL-PROJECT": "self" },
    completedPreparation: { "data-analyst": ["SK-SQL-PROJECT"] } };
  assert(path(completed, []).tree.some((node) => node.skill === "SK-SQL-PROJECT" && node.state === "self"));
  assert(!path({ ...completed, jobId: "designer" }, []).tree.some((node) => node.skill === "SK-SQL-PROJECT"));
  // The source vacancy never acquires a SQLD preference from our preparation advice.
  assert.deepEqual(opp.preferred, ["SK-SQL"]);
});
