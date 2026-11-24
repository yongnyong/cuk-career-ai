import { JOBS, jobById } from "./data/catalog";

// 하양이: 가톨릭대학교 공식 캐릭터. 직업군 착장은 학교 허락을 받은 2차 창작이다(docs/HAYANG_OUTFITS.md).
export type Outfit =
  | "medical" | "dev" | "research" | "engineer" | "business" | "global" | "public"
  | "law" | "care" | "edu" | "creative" | "ministry" | "startup";

// 공통 직무 → 직업군. 학과 직무는 base(연결 공통 직무)를 따라간다
const BY_JOB: Record<string, Outfit> = {
  "ai-engineer": "dev", "data-analyst": "dev", "sw-developer": "dev", electronics: "dev",
  "bio-researcher": "research", "bio-qa": "research", pharma: "research", food: "research",
  clinical: "medical", "env-engineer": "engineer",
  finance: "business", marketer: "global", "overseas-sales": "global",
  "public-sector": "public", legal: "law", welfare: "care", educator: "edu",
  "content-planner": "creative", designer: "creative", "arts-planner": "creative",
  npo: "ministry", founder: "startup",
  // base가 없는 학과 직무
  "psy-org": "business", "his-translate": "creative", "sw-research": "research",
};

export const OUTFIT_LABEL: Record<Outfit, string> = {
  medical: "의료인", dev: "개발자", research: "연구원", engineer: "엔지니어", business: "회사원",
  global: "글로벌 비즈니스맨", public: "공무원", law: "법조인", care: "상담가", edu: "선생님",
  creative: "크리에이터", ministry: "사목자", startup: "창업가",
};

export function outfitFor(jobId: string, startup = false): Outfit {
  if (startup) return "startup";
  const job = jobById(jobId);
  return BY_JOB[jobId] ?? (job?.base ? BY_JOB[job.base] : undefined) ?? "business";
}

/** 진화 단계: 1 과잠 학생 → 2 직업 착장 → 3 + 자동차 → 4 + 아파트. 스킬트리 EXP %로 정한다 */
export type HayangStage = 1 | 2 | 3 | 4;
export const STAGE_FROM = [0, 30, 60, 90] as const;

export function hayangStage(pct: number): HayangStage {
  return pct >= STAGE_FROM[3] ? 4 : pct >= STAGE_FROM[2] ? 3 : pct >= STAGE_FROM[1] ? 2 : 1;
}

export function stageTitle(stage: HayangStage, outfit: Outfit) {
  return stage === 1 ? "새내기 하양이" : stage === 2 ? `${OUTFIT_LABEL[outfit]} 하양이` : stage === 3 ? `차 뽑은 ${OUTFIT_LABEL[outfit]} 하양이` : `내 집 마련 ${OUTFIT_LABEL[outfit]} 하양이`;
}

export const hayangImage = (stage: HayangStage, outfit: Outfit) => `/hayang/${stage === 1 ? "student" : outfit}.webp`;

export const OUTFITS = Object.keys(OUTFIT_LABEL) as Outfit[];

/** 도감 설명용: 이 착장을 입는 공통 직무 이름 */
export const jobsWearing = (outfit: Outfit) => JOBS.filter((j) => j.fields.length && BY_JOB[j.id] === outfit).map((j) => j.name);
