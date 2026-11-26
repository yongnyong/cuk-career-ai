import type { SkillRoute } from "../types";

// Shared employment work that students can start before choosing a specific posting.
export const COMMON_WORK = ["SK-RESUME"];
export const LANGUAGE_EXAMS = ["SK-TOEIC", "SK-TOEIC-SPEAKING", "SK-OPIC", "SK-JLPT", "SK-HSK", "SK-DELF"];
export const COMMON_EXAMS = new Set(["SK-COMP", ...LANGUAGE_EXAMS]);
export const COMMON_SKILLS = new Set(["SK-RESUME", "SK-COMP", "COMMON-LANGUAGE", ...LANGUAGE_EXAMS]);

const stage = (value: number, recommendedBefore?: string[], reason?: string): SkillRoute =>
  ({ domain: "specialist", stage: value, recommendedBefore, reason });

export const SKILL_ROUTES: Record<string, SkillRoute> = {
  "CW-EVIDENCE": { domain: "specialist", stage: 0 },
  "CW-BUDGET": { domain: "specialist", stage: 1 },
  "SK-PPT": { domain: "specialist", stage: 2, recommendedBefore: ["CW-BUDGET"], reason: "예산표에서 비교한 비용과 대안을 발표 자료에 활용할 수 있어요." },
  "SK-RESUME": { domain: "common", stage: 0 },
  "CW-JOB-INTERVIEW": { domain: "specialist", stage: 4, recommendedBefore: ["SK-RESUME"], reason: "이력서에 적은 경험을 바탕으로 지원 직무의 면접 질문에 답해요." },
  "SK-PORT": { domain: "specialist", stage: 4, recommendedBefore: ["CW-EVIDENCE", "SK-PPT", "AI-CAP", "PR-AGENT-EVAL", "PR-PSY-PROGRAM"], reason: "증빙과 발표 자료에서 대표 사례를 고르고 전문 작업물을 함께 연결해요." },
  "SK-PY-01": stage(0), "SK-SQL": stage(0),
  "AI-ML": stage(1), "AI-NLP": stage(2), "AI-CV": stage(2), "AI-SPEECH": stage(2),
  "AI-CAP": stage(3), "AI-FIELD": stage(4), "SK-SCI-PAPER": stage(4),
  "PR-EVAL-DATASET": stage(1),
  "PR-AGENT-EVAL": stage(3, ["PR-EVAL-DATASET"], "평가 데이터를 준비하고 평가 시스템에 통합해요."),
  "PR-JUDGE-AUDIT": stage(3, ["PR-EVAL-DATASET"], "같은 평가 데이터로 사람과 LLM의 판정을 비교해요."),
  "PSY-STAT": stage(0), "PSY-INTERVIEW": stage(1), "PSY-GROUP": stage(2),
  "PSY-COMM": stage(2), "PSY-CAREER": stage(2), "PSY-TEST": stage(1),
  "PSY-CLIN-PRACT": stage(3), "PSY-GRAD": stage(4),
  "PSY-C-YOUTH": stage(3), "PSY-C-COUNSEL": stage(4), "PSY-C-JOB": stage(3),
  "PSY-C-CLIN": stage(3), "PSY-C-MH": stage(4), "PSY-C-SURVEY": stage(2),
  "PR-PSY-PROGRAM": stage(3, ["PR-SESSION"], "회기별 진행안을 바탕으로 운영 자료를 완성해요."),
  "SK-DEPLOY": stage(3), "SK-DL": stage(3),
};
