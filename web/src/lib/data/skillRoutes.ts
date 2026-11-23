import type { SkillRoute } from "../types";

// Shared employment work that students can start before choosing a specific posting.
export const COMMON_WORK = [
  "CW-EVIDENCE", "CW-BUDGET", "SK-PPT", "CW-JOB-INTERVIEW", "SK-RESUME", "SK-PORT",
];
export const COMMON_EXAMS = new Set(["SK-COMP", "SK-TOEIC", "SK-OPIC", "SK-TOEIC-SPEAKING"]);

// Service-authored preparation paths, distinct from employer requirements.
export const COMMON_SKILLS = new Set([
  "SK-TOEIC", "SK-TOEIC-SPEAKING", "SK-OPIC", "SK-JLPT", "SK-HSK", "SK-DELF",
  "SK-COMP", "SK-PORT", "SK-RESUME", "SK-PPT", "SK-PRESENTATION-SAMPLE",
  "SK-PROPOSAL", "SK-WRITING-SAMPLE", "SK-BRIEF", "SK-SPREADSHEET",
  "PR-TEAM-HANDOFF", "PR-SHARED-DOCS", "PR-NOTION", "PR-STAKEHOLDER", "PR-FOREIGN-CALL", "PR-EN-READING", "PR-WORD-TEMPLATE",
]);

const stage = (value: number, recommendedBefore?: string[], reason?: string): SkillRoute =>
  ({ domain: "specialist", stage: value, recommendedBefore, reason });

export const SKILL_ROUTES: Record<string, SkillRoute> = {
  "CW-EVIDENCE": { domain: "common", stage: 0 },
  "CW-BUDGET": { domain: "common", stage: 1 },
  "SK-PPT": { domain: "common", stage: 2, recommendedBefore: ["CW-BUDGET"], reason: "예산표에서 비교한 비용과 대안을 발표 자료에 활용할 수 있어요." },
  "SK-RESUME": { domain: "common", stage: 3, recommendedBefore: ["CW-EVIDENCE"], reason: "경험별 증빙에서 지원할 직무에 맞는 성과를 골라 이력서에 옮겨요." },
  "CW-JOB-INTERVIEW": { domain: "common", stage: 4, recommendedBefore: ["SK-RESUME"], reason: "이력서에 적은 경험을 바탕으로 지원 직무의 면접 질문에 답해요." },
  "SK-PORT": { domain: "common", stage: 4, recommendedBefore: ["CW-EVIDENCE", "SK-PPT", "AI-CAP", "PR-AGENT-EVAL", "PR-PSY-PROGRAM"], reason: "증빙과 발표 자료에서 대표 사례를 고르고 전문 작업물을 함께 연결해요." },
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
