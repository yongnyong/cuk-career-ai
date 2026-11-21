import { scaleOf, skillById } from "./data/catalog";
import { postingProjectById } from "./data/postingProjects";
import type { CareerCredential } from "./data/careerCredentials";
import type { Opportunity, Profile, TreeSignal } from "./types";

type Observation = NonNullable<Opportunity["preparationEvidence"]>[number];
type Route = NonNullable<TreeSignal["preparation"]> & { skillId: string };
type Student = Pick<Profile, "skills">;

const routes = {
  sqlPractice: {
    skillId: "SK-SQL", kind: "suggested",
    action: "예제 테이블에서 조건별 집계를 작성하고 두 테이블을 연결하는 쿼리를 실행해 보세요.",
    completion: "실행한 쿼리와 각 결과를 설명한 메모를 함께 저장하면 연습 완료예요.",
  },
  sqlProject: {
    skillId: "SK-SQL-PROJECT", kind: "suggested",
    action: "공개 데이터에서 질문 하나를 정하고 SQL로 답을 구해 보세요.",
    completion: "다시 실행할 수 있는 SQL 파일, 결과표, 결과 해석을 담은 분석 노트를 남기세요.",
  },
  sqlCertificate: {
    skillId: "SK-SQLD", kind: "suggested",
    action: "SQL 기본기를 자격으로 기록하고 싶다면 SQLD의 공식 출제 범위를 확인하고 예제 문제로 보완할 단원을 골라 보세요.",
    completion: "학습 기록을 남기며 준비하고, SQLD를 실제 취득했을 때 이 자격 노드를 완료로 표시하세요.",
  },
  presentation: {
    skillId: "SK-PRESENTATION-SAMPLE", kind: "suggested",
    action: "목표 직무에서 설명할 주제 하나를 골라 청중, 핵심 주장, 뒷받침할 자료를 담은 발표 슬라이드를 만드세요.",
    completion: "발표 자료와 발표할 때 전달할 핵심 문장을 함께 저장하세요.",
  },
  proposal: {
    skillId: "SK-PROPOSAL", kind: "direct",
    action: "원문이 요청한 제안서의 주제와 양식을 확인하고 문제, 제안, 판단 근거를 담은 초안을 작성하세요.",
    completion: "원문의 요구 항목을 확인한 제안서 파일을 준비하세요.",
  },
  writing: {
    skillId: "SK-WRITING-SAMPLE", kind: "suggested",
    action: "공고의 업무를 참고해 독자와 목적을 정하고 글 한 편을 작성하세요.",
    completion: "최종 원고와 누구에게 어떤 메시지를 전달하려 했는지 적은 메모를 남기세요.",
  },
  writing_sample: {
    skillId: "SK-WRITING-SAMPLE", kind: "direct",
    action: "공고에서 지정한 형식·분량을 확인하고 해당 업무에 맞는 글 샘플을 골라 다듬으세요.",
    completion: "요청한 형식으로 원고를 저장하고 원문의 제출 항목과 대조하세요.",
  },
  cad: {
    skillId: "SK-CAD-DRAWING", kind: "suggested",
    action: "간단한 부품이나 공간 하나를 정하고 CAD로 치수와 형상을 표현해 보세요.",
    completion: "다시 편집할 수 있는 도면 원본과 미리보기 파일을 남기세요.",
  },
  drawing: {
    skillId: "SK-CAD-DRAWING", kind: "direct",
    action: "공고가 요청한 도면의 주제와 파일 형식을 확인하고 해당하는 작업물을 준비하세요.",
    completion: "제출 형식으로 내보낸 도면 파일을 열어 치수와 주석을 확인하세요.",
  },
  portfolio: {
    skillId: "SK-PORT", kind: "direct",
    action: "공고의 제출 안내를 확인하고 관련 작업물에 본인의 역할과 결과를 설명해 포트폴리오로 묶으세요.",
    completion: "제출용 파일이나 링크를 준비하고 다른 기기에서도 열리는지 확인하세요.",
  },
  analysis: {
    skillId: "SK-ANALYSIS-REPORT", kind: "suggested",
    action: "공개 데이터로 업무와 관련된 질문 하나를 분석하고 결과를 한 장으로 정리하세요.",
    completion: "질문, 사용한 데이터, 결과표 또는 차트, 해석을 담은 보고서를 남기세요.",
  },
  business_document: {
    skillId: "SK-BRIEF", kind: "suggested",
    action: "지원 직무에서 다룰 이슈 하나를 골라 현황, 확인한 근거, 제안할 조치를 담은 업무 보고서를 작성하세요.",
    completion: "읽는 사람이 다음 행동을 결정할 수 있도록 요약과 근거 출처를 넣은 보고서 한 장을 남기세요.",
  },
  spreadsheet: {
    skillId: "SK-SPREADSHEET", kind: "suggested",
    action: "공개 표 데이터를 스프레드시트로 정리하고 함수나 피벗 테이블로 업무 질문 하나를 집계해 보세요.",
    completion: "원자료, 계산식, 결과표가 함께 있는 파일을 저장하고 집계 결과를 원자료와 대조하세요.",
  },
} satisfies Record<string, Route>;

// Completed posting projects keep their deliverable when a source is refreshed.
export const preparationCompletionBySkill = new Map<string, string>(
  Object.values(routes).map(route => [route.skillId, route.completion]),
);

function held(profile: Student, skill: string) {
  return (profile.skills[skill] ?? "none") !== "none";
}

function chooseRoute(key: string, profile: Student, template: ReadonlySet<string>, analysisRequested: boolean): Route | undefined {
  const project = postingProjectById.get(key);
  if (project) return { skillId: project.id, kind: "suggested", action: project.action, completion: project.completion };
  if (key === "sql_certificate" || key.startsWith("credential:")) {
    const skillId = key === "sql_certificate" ? "SK-SQLD" : key.slice("credential:".length);
    const skill = skillById(skillId);
    if (!skill || (skill.kind !== "자격증" && skill.kind !== "어학")) return;
    return {
      skillId, kind: "direct",
      action: `공고가 명시한 ${skill.name}의 인정 조건을 확인하고 내 취득 기록과 대조하세요.`,
      completion: "공고의 인정 기준을 확인하고, 실제 취득한 자격이나 점수·등급을 기록하세요.",
    };
  }
  if (key === "sql_project") return routes.sqlProject;
  if (key === "sql") {
    if (analysisRequested || held(profile, "SK-SQLD")) return routes.sqlProject;
    if (!held(profile, "SK-SQL") && !held(profile, "SK-SQL-PROJECT")) return routes.sqlPractice;
    return template.has("SK-SQLD") ? routes.sqlCertificate : routes.sqlProject;
  }
  switch (key) {
    case "presentation": case "proposal": case "writing": case "writing_sample":
    case "cad": case "drawing": case "portfolio": case "analysis": case "business_document": case "spreadsheet":
      return routes[key];
  }
}

// Older imports can establish the SQL/SQLD distinction via an exact, cited skill.
// An uncited preferred-skill tag does not identify a source sentence.
function observations(opp: Opportunity): Observation[] {
  if (opp.preparationEvidence) return opp.preparationEvidence;
  return (opp.skillEvidence ?? []).flatMap((entry) => {
    const key = entry.skill === "SK-SQL" ? "sql" : entry.skill === "SK-SQLD" ? "sql_certificate" : undefined;
    return key ? [{ ...entry, key }] : [];
  });
}

/** Called only for postings already matched to the student's goal occupation. */
export function preparationSignals(
  profile: Student, opportunity: Opportunity, templateSkills: ReadonlySet<string>,
  reference: TreeSignal["reference"], directSignals: readonly TreeSignal[] = [],
  credentialOptions: readonly CareerCredential[] = [],
): TreeSignal[] {
  if (!opportunity.reviewed || opportunity.isVirtual) return [];
  const verified = observations(opportunity).filter((entry) =>
    entry.scope === "role" && (entry.basis === "required" || entry.basis === "preferred") &&
    entry.quote.trim() && opportunity.sections?.some((section) => section.id === entry.src && section.text.includes(entry.quote)));
  const analysisRequested = verified.some((entry) => entry.key === "analysis" || entry.key === "sql_project");
  const signals: TreeSignal[] = [];
  for (const option of credentialOptions) {
    if (!option.observation || held(profile, option.id) ||
        verified.some(e => e.key === "credential:" + option.id)) continue;
    for (const entry of verified.filter(e => e.key === option.observation)) {
      signals.push({
        skillId: option.id, basis: entry.basis, status: "gap",
        reference: { ...reference, sectionId: entry.src, quote: entry.quote, scope: entry.scope },
        preparation: { kind: "suggested", action: option.reason,
          completion: "발급기관의 자격증 또는 취득 확인서에서 실제 취득 결과를 확인하세요." },
      });
    }
  }
  // On a citation tie, keep the more specific experience clause ahead of a generic SQL mention.
  for (const entry of verified.sort((a, b) => Number(b.key === "sql_project") - Number(a.key === "sql_project"))) {
    if (entry.key === "analysis" && verified.some((item) =>
      (item.key === "sql" || item.key === "sql_project") && item.quote === entry.quote)) continue;
    const route = chooseRoute(entry.key, profile, templateSkills, analysisRequested);
    if (!route) continue;
    const { skillId, ...preparation } = route;
    const existing = directSignals.find((item) => item.skillId === skillId && item.basis === entry.basis &&
      item.reference.id === reference.id && item.reference.quote === entry.quote && item.reference.scope === "role");
    // A grade or test name on its own does not establish that a recorded result meets the posting's cutoff.
    const status = existing?.status ?? (held(profile, skillId)
      ? preparation.kind === "direct" && scaleOf(skillId) ? "unknown" : "matched"
      : "gap");
    signals.push({
      skillId, basis: entry.basis, status, minimum: existing?.minimum, preparation,
      reference: { ...reference, sectionId: entry.src, quote: entry.quote, scope: entry.scope },
    });
  }
  return signals;
}

const correspondingRoutes: Record<string, readonly string[]> = {
  "SK-SQL": ["SK-SQL", "SK-SQLD", "SK-SQL-PROJECT"],
  "SK-PPT": ["SK-PRESENTATION-SAMPLE", "SK-PROPOSAL"],
  "SK-WRITE": ["SK-WRITING-SAMPLE"],
  "SK-DESIGN-TOOL": ["SK-CAD-DRAWING"],
};

/** Replace only the older representation of the same cited observation. */
export function replacedPreparationSignal(direct: TreeSignal, routes: readonly TreeSignal[]) {
  if (!direct.reference.quote || direct.reference.scope !== "role") return false;
  return routes.some((route) => {
    if (!route.preparation || route.reference.id !== direct.reference.id || route.basis !== direct.basis ||
        route.reference.scope !== direct.reference.scope || route.reference.quote !== direct.reference.quote) return false;
    if (direct.skillId === route.skillId) {
      // An explicit credential mention must keep its own threshold and status.
      return route.preparation.kind === "direct" || direct.skillId === "SK-SQL";
    }
    if (direct.skillId === "SK-SQL" && route.preparation.kind === "direct") return false;
    return correspondingRoutes[direct.skillId]?.includes(route.skillId) ?? false;
  });
}
