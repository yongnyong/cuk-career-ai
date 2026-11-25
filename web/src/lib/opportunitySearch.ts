import type { Opportunity, OpportunitySearchResult, Profile, StartupPlan } from "./types";
import type { Recommendation } from "./engine";
import { evaluate, isOpen, latest, preparationReferences, recommend } from "./engine";
import { jobById, skillById } from "./data/catalog";
import { careerInterestOf } from "./interest";
import { employmentRelevance } from "./employmentMatch";

export function opportunityQuery(profile: Profile, plan?: StartupPlan | null) {
  if (careerInterestOf(profile) === "startup") {
    return [plan?.idea, plan?.customer, plan?.goal].filter(Boolean).join(" ").slice(0, 600);
  }
  const job = jobById(profile.jobId);
  const skills = job?.nodes.filter(node => node.required).map(node => skillById(node.skill))
    .filter(skill => skill && !["어학", "자격증"].includes(skill.kind)).slice(0, 6).map(skill => skill?.name) ?? [];
  return [job?.name, ...skills]
    .filter(Boolean).join(" ").slice(0, 600);
}

function groundedRoleMatch(profile: Profile, quotes: string[]) {
  const job = jobById(profile.jobId);
  if (!job) return false;
  const names = [job.name, ...job.nodes.filter(node => node.required)
    .map(node => skillById(node.skill)).filter(skill => skill && !["자격증", "어학"].includes(skill.kind))
    .map(skill => skill!.name)];
  const text = quotes.join(" ").toLowerCase().replace(/\s+/g, "");
  // Match concrete work in a verified original paragraph. Generic 기관 / 연구
  // and transferable tools alone cannot establish a psychological or AI role.
  let terms = names.flatMap(name => name.split(/[·/()\s]+/))
    .filter(term => term.length >= 3 && !/^(연구원|엔지니어|프로젝트|프로그래밍|포트폴리오|프로그램|데이터|기초|실습|개발|연구법)$/.test(term));
  if (/^ai-/.test(job.id)) {
    terms = ["인공지능", "머신러닝", "딥러닝", "llm", "ai모델", "ai평가", "ai개발", "모델평가", "모델학습", "에이전트평가"];
    return terms.some(term => text.includes(term)) && /개발|평가|학습|튜닝|배포|설계|검증|분석|벤치마크|데이터셋|연구|구축/.test(text);
  }
  if (job.id === "psy-counsel" || job.id === "psy-clinical") {
    terms = ["심리상담", "심리검사", "심리평가", "내담자", "상담면접", "청소년상담", "상담심리", "임상심리"];
  }
  return terms.some(term => text.includes(term.toLowerCase()));
}

export function retrievedRecommendations(
  opportunities: Opportunity[], profile: Profile, now: Date, result?: OpportunitySearchResult | null,
  mode: "recommendations" | "preparation" = "recommendations",
): Recommendation[] {
  const baseline = mode === "preparation" ? preparationReferences(opportunities, profile, now) : recommend(opportunities, profile, now);
  if (!result) return baseline;
  const byId = new Map(opportunities.map(o => [o.id, o]));
  const original = new Map(baseline.map(r => [r.opp.id, r]));
  // Preserve rule-backed candidates, including those with sparse source text.
  // Startup candidates remain controlled by the current goal's retrieval.
  const recommendations: Recommendation[] = careerInterestOf(profile) === "startup" ? [] : [...baseline];
  for (const hit of result.hits) {
    const opp = byId.get(hit.postingId);
    if (!opp || !opp.versions.length || latest(opp).version !== hit.version) continue;
    if (careerInterestOf(profile) === "startup" ? opp.type !== "창업지원" : opp.type === "창업지원") continue;
    const verdict = evaluate(opp, profile).overall;
    const ready = isOpen(opp, now) && verdict !== "fail";
    if (mode === "preparation" ? ready : !ready) continue;
    const evidence = hit.evidence.filter(source => {
      if (source.postingId !== opp.id || source.version !== hit.version || !source.quote) return false;
      const sectionId = source.sectionId.slice(0, source.sectionId.lastIndexOf(":"));
      return sectionId === "title" ? opp.title.includes(source.quote)
        : opp.sections.some(s => s.id === sectionId && s.text.includes(source.quote));
    });
    if (!evidence.length) continue;
    const existing = original.get(opp.id);
    // Preserve explicit employment mappings. Empty classifications remain searchable.
    if (!existing && careerInterestOf(profile) !== "startup" && opp.employmentMatch?.namedJobs.length
      && !employmentRelevance(opp, profile)) continue;
    if (!existing && careerInterestOf(profile) !== "startup" && !groundedRoleMatch(profile,
      evidence.filter(source => source.basis !== "metadata" && !source.sectionId.startsWith("title:"))
        .map(source => source.quote))) continue;
    const timing = opp.opensAt && Date.parse(opp.opensAt) > now.getTime() ? "접수 예정 · 준비 참고"
      : opp.deadlineStatus === "unknown" ? "모집 상태 확인 · 준비 참고"
        : !isOpen(opp, now) ? "지난 공고 · 준비 참고" : "지원 조건 준비 · 참고 공고";
    const recommendation = {
      opp, verdict, score: hit.score,
      reasons: mode === "preparation" ? [timing, "목표와 연결되는 공고 원문"]
        : existing?.reasons ?? ["업무 원문과 연결된 탐색 공고", ...(verdict === "check" ? ["일부 조건 확인 필요"] : [])],
      retrievalEvidence: evidence,
    };
    const existingIndex = recommendations.findIndex(item => item.opp.id === opp.id);
    if (existingIndex >= 0) recommendations[existingIndex] = recommendation;
    else recommendations.push(recommendation);
  }
  if (careerInterestOf(profile) !== "startup") {
    const rank = new Map(result.hits.map((hit, index) => [hit.postingId, index]));
    recommendations.sort((a, b) => (employmentRelevance(b.opp, profile)?.tier ?? -1)
      - (employmentRelevance(a.opp, profile)?.tier ?? -1)
      || (rank.get(a.opp.id) ?? Infinity) - (rank.get(b.opp.id) ?? Infinity));
  }
  return recommendations;
}

