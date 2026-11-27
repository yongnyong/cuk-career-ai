import type { Profile } from "../types";

// 시연용 계정 (기획서 4.8 스토리보드). 비밀번호 없이 바로 시작한다.
// 민지·지우는 프로젝트 두 개를 완료해 둔다: AI·심리 트랙의 진행률(EXP)은 프로젝트·포트폴리오·자기소개서만 세므로, 없으면 EXP 0%로 시작한다.
const base = { careerInterest: "employment" as const, campus: "성심", status: "재학" as const, interests: [] as string[], weeklyHours: 5, targetTerm: "2027 하계", createdAt: "2026-11-16T00:00:00.000Z" };

export const PERSONAS: { id: string; label: string; desc: string; profile: Profile }[] = [
  {
    id: "demo-minji",
    label: "민지",
    desc: "인공지능학과 3학년 · AI 연구원",
    profile: { ...base, pseudoId: "demo-minji", admissionYear: 2024, departmentId: "ai", grade: 3, jobId: "ai-research", interests: ["ai-data"], skills: { "SK-PY-01": "verified", "AI-ML": "self", "AI-PROJECT-DATA": "self", "AI-PROJECT-MODELS": "self" } },
  },
  {
    id: "demo-jiwoo",
    label: "지우",
    desc: "심리학과 3학년 · 상담심리",
    profile: { ...base, pseudoId: "demo-jiwoo", admissionYear: 2024, departmentId: "psychology", grade: 3, jobId: "psy-counsel", interests: ["psy-org"], skills: { "PSY-STAT": "self", "PSY-INTERVIEW": "self", "PSY-PROJECT-SURVEY": "self", "PSY-PROJECT-DATA": "self" } },
  },
  {
    id: "demo-yuna",
    label: "유나",
    desc: "미디어기술콘텐츠학과 3학년 · 영상 기획·연출",
    profile: {
      ...base, pseudoId: "demo-yuna", admissionYear: 2024, departmentId: "media-tech", grade: 3, jobId: "mtc-video", interests: ["mtc-startup"],
      skills: { "MTC-PLAN": "self", "SK-VIDEO": "self" },
    },
  },
  {
    id: "demo-haneul",
    label: "하늘",
    desc: "사회복지학과 2학년 · 사회적경제·소셜벤처",
    profile: {
      ...base, pseudoId: "demo-haneul", admissionYear: 2025, departmentId: "social-welfare", grade: 2, jobId: "sw-social", interests: ["sw-youth"],
      skills: { "SW-SOCIAL": "self" },
    },
  },
  {
    id: "demo-seojun",
    label: "서준",
    desc: "경영학과 4학년 · 대학생 취업·창업 AI 서비스",
    profile: {
      ...base, careerInterest: "startup", pseudoId: "demo-seojun", admissionYear: 2023, departmentId: "business", grade: 4, jobId: "founder",
      weeklyHours: 10, startup: { stage: "pre" },
      skills: {},
    },
  },
];

export function restoreDemoProfile(scenario: Profile, saved?: Profile | null): Profile {
  let profile = { ...(saved ?? scenario), careerInterest: saved?.careerInterest ?? scenario.careerInterest };
  // 시나리오에 나중에 더한 완료 노드는 예전에 저장된 시연 프로필에도 채운다. 직접 취소한 노드("none")는 저장값이 이긴다
  if (saved && saved.jobId === scenario.jobId) profile = { ...profile, skills: { ...scenario.skills, ...saved.skills } };
  // Restore Haneul's employment scenario from the earlier startup demo assignment.
  if (scenario.pseudoId === "demo-haneul" && profile.jobId === "founder" && profile.careerInterest === "startup") {
    return { ...profile, careerInterest: scenario.careerInterest, jobId: scenario.jobId, interests: scenario.interests };
  }
  return profile;
}
