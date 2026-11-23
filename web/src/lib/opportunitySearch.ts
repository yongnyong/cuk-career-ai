import type { Opportunity, OpportunitySearchResult, Profile, StartupPlan } from "./types";
import type { Recommendation } from "./engine";
import { evaluate, isOpen, latest, preparationReferences, recommend } from "./engine";
import { jobById, skillById } from "./data/catalog";
import { getDepartment } from "./data/departments";
import { careerInterestOf } from "./interest";
import { employmentRelevance } from "./employmentMatch";

export function opportunityQuery(profile: Profile, plan?: StartupPlan | null) {
  if (careerInterestOf(profile) === "startup") {
    return [plan?.idea, plan?.customer, plan?.goal].filter(Boolean).join(" ").slice(0, 600);
  }
  const job = jobById(profile.jobId);
  const skills = Object.entries(profile.skills).filter(([, state]) => state !== "none")
    .map(([id]) => skillById(id)?.name).filter(Boolean).slice(0, 10);
  return [job?.name, job?.summary, getDepartment(profile.departmentId)?.name, ...skills]
    .filter(Boolean).join(" ").slice(0, 600);
}

export function retrievedRecommendations(
  opportunities: Opportunity[], profile: Profile, now: Date, result?: OpportunitySearchResult | null,
  mode: "recommendations" | "preparation" = "recommendations",
): Recommendation[] {
  const baseline = mode === "preparation" ? preparationReferences(opportunities, profile, now) : recommend(opportunities, profile, now);
  if (!result) return baseline;
  const byId = new Map(opportunities.map(o => [o.id, o]));
  const original = new Map(baseline.map(r => [r.opp.id, r]));
  const recommendations: Recommendation[] = [];
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
    const timing = opp.opensAt && Date.parse(opp.opensAt) > now.getTime() ? "접수 예정 · 준비 참고"
      : opp.deadlineStatus === "unknown" ? "모집 상태 확인 · 준비 참고"
        : !isOpen(opp, now) ? "지난 공고 · 준비 참고" : "지원 조건 준비 · 참고 공고";
    recommendations.push({
      opp, verdict, score: hit.score,
      reasons: mode === "preparation" ? [timing, "목표와 연결되는 공고 원문"]
        : existing?.reasons ?? ["업무 원문과 연결된 탐색 공고", ...(verdict === "check" ? ["일부 조건 확인 필요"] : [])],
      retrievalEvidence: evidence,
    });
  }
  if (careerInterestOf(profile) !== "startup") {
    const rank = new Map(recommendations.map((r, index) => [r.opp.id, index]));
    recommendations.sort((a, b) => (employmentRelevance(b.opp, profile)?.tier ?? -1)
      - (employmentRelevance(a.opp, profile)?.tier ?? -1)
      || rank.get(a.opp.id)! - rank.get(b.opp.id)!);
  }
  return recommendations;
}

