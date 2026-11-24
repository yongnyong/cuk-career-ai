import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { test } from "node:test";
registerHooks({ resolve(s,c,next) {
  return next(c.parentURL?.endsWith(".ts") && s.startsWith(".") && !s.endsWith(".ts") ? s + ".ts" : s, c);
}});
const { retrievedRecommendations, opportunityQuery, EXPLORE_LIMIT } = await import("../src/lib/opportunitySearch.ts");
const { PERSONAS } = await import("../src/lib/data/personas.ts");
const { recommend } = await import("../src/lib/engine.ts");
const profile = { ...PERSONAS.find(p => p.profile.departmentId === "ai").profile,
  pseudoId: "private-person-id", grade: 3 };
const now = new Date("2026-11-24T09:00:00+09:00");
function posting(id, required = []) {
  return {
    id, title: "응답 품질 검수 담당", org: "테스트", type: "채용", jobs: [], required, preferred: [],
    source: { name: "테스트", url: "https://example.edu/" + id }, applyUrl: "https://example.edu/" + id,
    isVirtual: false, documents: [], sections: [{ id: "duties", title: "업무", text: "LLM 답변 비교 평가와 SQL 활용 우대" }],
    versions: [{ version: 1, checkedAt: now.toISOString(), deadline: "2026-12-31T23:59:00+09:00" }],
    confidence: 1, reviewed: true,
  };
}
function hit(o) {
  return { postingId: o.id, version: 1, score: 1, evidence: [{
    postingId: o.id, version: 1, sectionId: "duties:0",
    quote: o.sections[0].text, sourceUrl: o.source.url,
  }] };
}
function result(hits, mode = "hybrid") {
  return { query: "LLM 답변 비교", mode, indexVersion: "fixture", total: hits.length, nextOffset: null, hits };
}
test("retrieval can discover unclassified work while preserving qualification checks", () => {
  const unknown = posting("unknown");
  const ineligible = posting("fourth-year", [{ key: "grade", label: "4학년", grades: [4], src: "duties" }]);
  assert.equal(recommend([unknown], profile, now).length, 0);
  const recommendations = retrievedRecommendations([ineligible, unknown], profile, now, result([hit(ineligible), hit(unknown)]));
  assert.deepEqual(recommendations.map(r => r.opp.id), [unknown.id]);
  assert.equal(recommendations[0].verdict, "pass");
  assert.ok(recommendations[0].reasons[0].includes("탐색"));
});
test("filtering refills beyond the former top-eight boundary and retains server rank", () => {
  const rows = Array.from({ length: 12 }, (_, i) => posting("posting-" + i,
    i < 10 ? [{ key: "grade", label: "4학년", grades: [4], src: "duties" }] : []));
  const recommendations = retrievedRecommendations(rows, profile, now, result(rows.map(hit)));
  assert.deepEqual(recommendations.map(r => r.opp.id), ["posting-10", "posting-11"]);
});
test("zero results and retrieval failure both keep the rule-engine recommendation", () => {
  const rows = [posting("one")];
  assert.deepEqual(retrievedRecommendations(rows, profile, now, result([])), recommend(rows, profile, now));
  assert.deepEqual(retrievedRecommendations(rows, profile, now, null), recommend(rows, profile, now));
});
test("rule-engine picks (virtual demo postings too) stay first; search only appends a few explorations", () => {
  const target = { ...posting("ai-intern"), title: "AI 연구 인턴", jobs: ["ai-research"], isVirtual: true };
  const base = recommend([target], profile, now);
  assert.equal(base.length, 1);
  const extras = Array.from({ length: 6 }, (_, i) => posting("extra-" + i));
  const out = retrievedRecommendations([target, ...extras], profile, now, result(extras.map(hit)));
  assert.equal(out[0].opp.id, "ai-intern");
  assert.equal(out.length, 1 + EXPLORE_LIMIT);
  assert.ok(out.slice(1).every(r => r.reasons[0].includes("탐색")));
});
test("keyword-only search cannot add postings whose evidence never names the student's goal", () => {
  const nurse = { ...posting("nurse"), title: "간호사 및 입시연구원 모집",
    sections: [{ id: "duties", title: "업무", text: "병동 간호 업무, 신입 연구원 우대" }] };
  const ml = { ...posting("ml"), sections: [{ id: "duties", title: "업무", text: "머신러닝 모델 학습과 Python 데이터 정리" }] };
  const out = retrievedRecommendations([nurse, ml], profile, now, result([hit(nurse), hit(ml)], "keyword"));
  assert.deepEqual(out.map(r => r.opp.id), ["ml"]);
});
test("employment query uses the goal job and skill names, not the department or job description", () => {
  const query = opportunityQuery(profile);
  assert.ok(query.includes("Python") && query.includes("머신러닝"));
  assert.ok(!query.includes("학과") && !query.includes("연구원"));
});
test("stale versions and invented quotations cannot enter the recommended list", () => {
  const row = posting("one");
  const stale = { ...hit(row), version: 2 };
  const forged = hit(row);
  forged.evidence[0].quote = "SQLD 필수";
  assert.equal(retrievedRecommendations([row], profile, now, result([stale, forged])).length, 0);
});
test("expired results remain preparation references with their original qualification verdict", () => {
  const expired = posting("past");
  expired.versions[0].deadline = "2026-11-01T23:59:00+09:00";
  const ineligible = posting("fourth-year", [{ key: "grade", label: "4학년", grades: [4], src: "duties" }]);
  const references = retrievedRecommendations([expired, ineligible], profile, now,
    result([hit(expired), hit(ineligible)]), "preparation");
  assert.deepEqual(references.map(r => r.opp.id), ["past", "fourth-year"]);
  assert.equal(references[1].verdict, "fail");
  assert.ok(references[0].reasons[0].includes("지난 공고"));
  assert.ok(references[1].reasons[0].includes("지원 조건 준비"));
});
test("employment and startup query construction excludes personal identifiers and scores", () => {
  assert.ok(!opportunityQuery(profile).includes("private-person-id"));
  const startup = { ...profile, careerInterest: "startup", startup: { region: "부산", birthYear: 2003 } };
  const query = opportunityQuery(startup, { idea: "학원 상담 요약 AI", customer: "학원장", goal: "판로 상담" });
  assert.equal(query, "학원 상담 요약 AI 학원장 판로 상담");
  assert.ok(!query.includes("2003") && !query.includes("부산"));
});


test("each demo persona keeps its own field and drops unrelated keyword matches", () => {
  const job = (id, text) => ({ ...posting(id), title: text, sections: [{ id: "duties", title: "업무", text }] });
  const rows = [
    job("ml", "머신러닝 모델 학습과 Python 데이터 처리"),
    job("counsel", "청소년 진로상담 보조, 청소년상담사 우대"),
    job("social", "사회적경제 기업 고객 인터뷰와 사업계획서 작성 지원"),
    job("nurse", "병동 간호사 신입 모집, 연구원 우대"),
    job("accounting", "회계 계약직원 채용, 연구행정 업무"),
    job("email", "email 응대 및 training 일정 관리"),
    job("sales", "AI 영상 솔루션 영업, 문서 글쓰기 능숙자"),
  ];
  const expected = { "demo-minji": ["ml"], "demo-jiwoo": ["counsel"], "demo-haneul": ["social"] };
  for (const [id, want] of Object.entries(expected)) {
    const persona = { ...PERSONAS.find(p => p.profile.pseudoId === id).profile, grade: 3 };
    const out = retrievedRecommendations(rows, persona, now, result(rows.map(hit), "keyword"));
    const extra = out.filter(r => r.reasons[0]?.includes("탐색")).map(r => r.opp.id);
    assert.deepEqual(extra, want, id);
  }
});
