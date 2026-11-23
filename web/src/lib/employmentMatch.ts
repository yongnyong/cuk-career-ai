import { jobById } from "./data/catalog";
import { getDepartment } from "./data/departments";
import type { Opportunity, Profile } from "./types";

// Explicit title mappings take precedence over broad imported department clusters.
export function matchesEmploymentRole(o: Opportunity, jobId: string) {
  const job = jobById(jobId);
  const mapping = o.employmentMatch;
  if (mapping?.namedJobs.length) return mapping.namedJobs.includes(jobId);
  const ids = mapping?.reviewedJobs.length ? mapping.reviewedJobs : o.jobs;
  if (mapping && !mapping.reviewedJobs.length) return false;
  return ids.includes(jobId) || !!job?.base && ids.includes(job.base);
}

export function employmentRelevance(o: Opportunity, p: Profile) {
  const job = jobById(p.jobId);
  const dept = getDepartment(p.departmentId);
  const mapping = o.employmentMatch;
  if (matchesEmploymentRole(o, p.jobId)) return { tier: 5, reason: "목표 직무(" + job?.name + ") 연결" };
  if (p.interests.some(id => matchesEmploymentRole(o, id))) return { tier: 4, reason: "관심 직무 연결" };
  const explicit = mapping?.majorConditions?.filter(c => !c.unrestricted && c.scope === "role" && (
    c.departmentIds.includes(p.departmentId) || !!dept && c.fields.includes(dept.field)));
  if (explicit?.length) {
    const preferred = explicit.some(c => c.basis === "preferred");
    return { tier: 3, reason: preferred ? "내 전공 우대 · 모집 직무 확인" : "명시된 전공과 연결 · 모집 직무 확인" };
  }
  const departments = mapping?.departmentIds ?? [];
  if (departments.includes(p.departmentId)) return { tier: 2, reason: "학과 관련 직무 탐색 · 분류 기준" };
  const sameField = dept && dept.field !== "open" && (mapping
    ? departments.some(id => getDepartment(id)?.field === dept.field)
    : o.jobs.some(id => jobById(id)?.fields.includes(dept.field) ||
        jobById(id)?.departments?.some(d => getDepartment(d)?.field === dept.field)));
  if (sameField) return { tier: 1, reason: "같은 계열 직무 탐색 · 모집 직무 확인" };
  if (!["채용", "현장실습"].includes(o.type) && !o.jobs.length) {
    return { tier: 0, reason: "공통 학생 공지" };
  }
  return null;
}
