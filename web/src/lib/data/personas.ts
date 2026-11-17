import type { Profile } from "../types";

// 시연용 계정 (기획서 4.8 스토리보드). 비밀번호 없이 바로 시작한다.
const base = { campus: "성심", status: "재학" as const, interests: [] as string[], weeklyHours: 5, targetTerm: "2027 하계", createdAt: "2026-11-16T00:00:00.000Z" };

export const PERSONAS: { id: string; label: string; desc: string; profile: Profile }[] = [
  {
    id: "demo-minji",
    label: "민지",
    desc: "인공지능학과 3학년 · AI 엔지니어",
    profile: { ...base, pseudoId: "demo-minji", admissionYear: 2024, departmentId: "ai", grade: 3, jobId: "ai-engineer", skills: { "SK-PY-01": "verified", "SK-DA": "self" } },
  },
  {
    id: "demo-jiwoo",
    label: "지우",
    desc: "심리학과 3학년 · 상담심리",
    profile: { ...base, pseudoId: "demo-jiwoo", admissionYear: 2024, departmentId: "psychology", grade: 3, jobId: "psy-counsel", interests: ["psy-org"], skills: { "PSY-STAT": "self", "PSY-INTERVIEW": "self" } },
  },
  {
    id: "demo-haneul",
    label: "하늘",
    desc: "사회복지학과 2학년 · 사회적경제·소셜벤처",
    profile: {
      ...base, pseudoId: "demo-haneul", admissionYear: 2025, departmentId: "social-welfare", grade: 2, jobId: "sw-social", interests: ["sw-youth"],
      skills: { "SW-SOCIAL": "self" }, startup: { stage: "pre", region: "경기", birthYear: 2006 },
    },
  },
];
