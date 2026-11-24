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
  return employmentTerms(profile).join(" ").slice(0, 600);
}

// 채용 공고 어디에나 나오는 말. 검색어·근거 판정에서 뺀다(학과명·직무 설명문도 넣지 않는다: "인공지능학과"의 "공지"·"학과"가 거의 모든 공고에 걸렸다)
const GENERIC = new Set(["연구원", "연구", "신입", "경력", "사원", "직원", "채용", "모집", "인턴", "담당", "업무", "기초", "실습", "심화",
  "자격", "자격증", "자격은", "준비", "경험", "역량", "이해", "활용", "작성", "관리", "기본", "과정", "이상", "또는", "및",
  "정리", "참여", "진학", "전문가", "평가", "개발과", "프로그램", "학회", "모델",
  // 학습 활동 이름(직무 자체가 아니어서 공고와 맞추는 데 쓰지 않는다)
  "글쓰기", "기술적", "논문", "학부연구생", "캡스톤디자인", "대학원", "석사", "합성", "연구법", "포트폴리오"]);

// 목표 직무 이름 + 직무 기본 스킬 + 내가 가진 스킬 이름(순서 유지, 중복 제거)
function employmentTerms(profile: Profile) {
  const job = jobById(profile.jobId);
  const ids = [...(job?.nodes.map(n => n.skill) ?? []),
    ...Object.entries(profile.skills).filter(([, state]) => state !== "none").map(([id]) => id)];
  const names = [job?.name, ...ids.map(id => skillById(id)?.name)].filter((x): x is string => !!x);
  const words = names.flatMap(name => name.split(/[^0-9A-Za-z가-힣+#]+/)).filter(w => w.length >= 2 && !/^\d+급$/.test(w) && !GENERIC.has(w.toLowerCase()));
  return [...new Set(words)].slice(0, 40);
}

// 탐색 공고(규칙 엔진 목록 밖)는 근거 원문에 목표 직무·스킬 단어가 서로 다른 것으로 2개 이상 있어야 보여준다
// (하나만 보면 "AI"·"글쓰기" 한 단어로 영업직·디자이너 공고가 걸렸다)
function mentionsGoal(quotes: string[], terms: string[]) {
  const text = quotes.join(" ").toLowerCase();
  return terms.filter(term => {
    const t = term.toLowerCase();
    if (!/^[a-z0-9+#]+$/.test(t)) return text.includes(t);
    // 영문은 낱말로만 본다("ai"가 "email" 안에서 걸리지 않게)
    return new RegExp(`(^|[^a-z0-9])${t.replace(/[+#]/g, "\$&")}($|[^a-z0-9])`).test(text);
  }).length >= 2;
}

// 규칙 엔진 목록 밖에서 검색으로 더 보여줄 공고 수
export const EXPLORE_LIMIT = 3;

export function retrievedRecommendations(
  opportunities: Opportunity[], profile: Profile, now: Date, result?: OpportunitySearchResult | null,
  mode: "recommendations" | "preparation" = "recommendations",
): Recommendation[] {
  const baseline = mode === "preparation" ? preparationReferences(opportunities, profile, now) : recommend(opportunities, profile, now);
  if (!result) return baseline;
  const byId = new Map(opportunities.map(o => [o.id, o]));
  const original = new Set(baseline.map(r => r.opp.id));
  const startup = careerInterestOf(profile) === "startup";
  const terms = startup ? [] : employmentTerms(profile);
  const matched = new Map<string, Recommendation["retrievalEvidence"]>();
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
    if (original.has(opp.id)) {
      matched.set(opp.id, evidence);  // 규칙 엔진도 고른 공고: 순서·이유는 그대로 두고 근거만 붙인다
      continue;
    }
    if (recommendations.length >= EXPLORE_LIMIT) continue;
    // 단어 검색만 돈 경우(임베딩 없음)는 목표 단어가 원문에 있어야 한다. 의미 검색(hybrid)은 서버 유사도 기준을 따른다
    if (!startup && result.mode !== "hybrid" && !mentionsGoal(evidence.map(e => e.quote), terms)) continue;
    // Preserve explicit employment mappings. Empty classifications remain searchable.
    if (!startup && opp.employmentMatch?.namedJobs.length
      && !employmentRelevance(opp, profile)) continue;
    const timing = opp.opensAt && Date.parse(opp.opensAt) > now.getTime() ? "접수 예정 · 준비 참고"
      : opp.deadlineStatus === "unknown" ? "모집 상태 확인 · 준비 참고"
        : !isOpen(opp, now) ? "지난 공고 · 준비 참고" : "지원 조건 준비 · 참고 공고";
    recommendations.push({
      opp, verdict, score: hit.score,
      reasons: mode === "preparation" ? [timing, "목표와 연결되는 공고 원문"]
        : ["업무 원문과 연결된 탐색 공고", ...(verdict === "check" ? ["일부 조건 확인 필요"] : [])],
      retrievalEvidence: evidence,
    });
  }
  if (!startup) {
    const rank = new Map(recommendations.map((r, index) => [r.opp.id, index]));
    recommendations.sort((a, b) => (employmentRelevance(b.opp, profile)?.tier ?? -1)
      - (employmentRelevance(a.opp, profile)?.tier ?? -1)
      || rank.get(a.opp.id)! - rank.get(b.opp.id)!);
  }
  // 규칙 엔진 목록이 기본이다(가상 공고 포함, 검색이 비거나 실패해도 그대로). 검색은 근거를 붙이고 탐색 공고를 뒤에 조금 더한다
  const base = baseline.map(r => matched.has(r.opp.id) ? { ...r, retrievalEvidence: matched.get(r.opp.id) } : r);
  return [...base, ...recommendations];
}

