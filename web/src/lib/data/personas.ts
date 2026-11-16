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
    id: "demo-seoyeon",
    label: "서연",
    desc: "프랑스어문화학과 2학년 · 문화 창업",
    profile: { ...base, pseudoId: "demo-seoyeon", admissionYear: 2025, departmentId: "french", grade: 2, jobId: "founder", interests: ["content-planner"], skills: { "SK-IDEA": "self" } },
  },
  {
    id: "demo-doyun",
    label: "도윤",
    desc: "영어영문학부 3학년 · 해외영업",
    profile: { ...base, pseudoId: "demo-doyun", admissionYear: 2024, departmentId: "english", grade: 3, jobId: "overseas-sales", interests: ["marketer"], skills: { "SK-TOEIC": "verified" } },
  },
];
