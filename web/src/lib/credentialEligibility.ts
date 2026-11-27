import type { Profile } from "./types";

const QNET = "https://www.q-net.or.kr/crf006.do?gSite=Q&gradeType=30&id=crf00603s10";
const CLINICAL = "https://www.q-net.or.kr/crf006.do?gId=&gSite=Q&gradeType=32&id=crf00603s10";
const DATAQ = "https://www.dataq.or.kr/www/dataq_brochure_2022.pdf";

// Scope is explicit. Similar certificate names never inherit an exam's rules.
const RULES: Record<string, { route: "engineer" | "clinical" | "open" | "manual"; url: string; detail: string }> = {
  "PSY-C-YOUTH": { route: "manual", url: "https://www.q-net.or.kr/qnet/html/guide67/guide_01.html", detail: "상담 관련 학위 등 응시요건과 합격 후 자격연수 요건을 확인하세요." },
  "CERT-YOUTH-2": { route: "manual", url: "https://www.q-net.or.kr/qnet/html/guide67/guide_01.html", detail: "학위·경력에 따른 응시 경로와 자격연수 요건을 확인하세요." },
  "PSY-C-COUNSEL": { route: "manual", url: "https://www.koreanpsychology.or.kr/psychology/license.html", detail: "한국상담심리학회의 학력·수련·시험·심사 요건을 확인하세요." },
  "CERT-PSY-COUNSELOR": { route: "manual", url: "https://www.counselors.or.kr/portal/service/kca_qualification_rule", detail: "한국상담학회의 수련자격·수련충족심사·시험 등 요건을 확인하세요." },
  "PSY-C-MH": { route: "manual", url: "https://www.ncmh.go.kr/", detail: "정신건강임상심리사 학위·과목과 지정기관 수련 요건을 확인하세요." },
  "CERT-PSY-CLINICAL-1": { route: "manual", url: QNET, detail: "임상심리사 1급의 학위·수련·경력별 응시 경로를 확인하세요." },
  "CERT-PSY-SURVEY-1": { route: "manual", url: QNET, detail: "사회조사분석사 1급의 경력 등 응시요건을 확인하세요." },
  "SK-INFO-PE": { route: "engineer", url: QNET, detail: "대학 졸업·졸업예정 등 응시 경로와 시험일 기준 학적을 공식 자가진단에서 확인하세요. 다른 자격·경력 경로도 있어요." },
  "SK-ELEC-PE": { route: "engineer", url: QNET,
    detail: "관련학과 대학 졸업·졸업예정 경로가 있어요. 관련학과 인정과 시험일 기준 학적을 확인하세요. 경력·기존 자격 등 다른 경로도 있어요." },
  "ICE-C-ELECTRIC": { route: "engineer", url: QNET,
    detail: "전기기사의 관련학과 대학 졸업·졸업예정 경로를 확인하세요. 학과 인정과 시험일 기준 학적을 대조하고, 경력·기존 자격 등 다른 경로도 확인할 수 있어요." },
  "CERT-BIGDATA": { route: "engineer", url: DATAQ,
    detail: "대학 졸업·졸업예정 경로는 전공 무관이에요. 시험일 기준 최종학년 여부를 확인하세요. 경력·기존 자격 등 다른 경로도 있어요." },
  "PSY-C-CLIN": { route: "clinical", url: CLINICAL,
    detail: "대학 졸업·졸업예정과 임상심리 실습수련 1년 또는 실무 2년을 함께 확인하세요. 외국 동일종목 자격 경로도 있어요." },
  "SK-SQLD": { route: "open", url: DATAQ,
    detail: "SQLD는 학력·학년 응시 제한이 없어요. 출제 범위와 목표 회차를 확인하고 준비하세요." },
};

export interface CredentialEligibility {
  status: "prepare" | "check" | "ready";
  label: string;
  reason: string;
  officialUrl: string;
  checkedAt: string;
  clinical: boolean;
}

export function credentialProfileKey(profile: Profile) {
  return JSON.stringify([profile.departmentId, profile.grade, profile.status]);
}

export function assessCredential(skill: string, profile: Profile): CredentialEligibility | undefined {
  const rule = RULES[skill];
  if (!rule) return undefined;
  const base = { reason: rule.detail, officialUrl: rule.url, checkedAt: "2026-11-24", clinical: rule.route === "clinical" };
  if (rule.route === "open") return { ...base, status: "ready", label: "학년 응시 제한 없음" };
  const facts = profile.credentialFacts?.[skill];
  if (facts?.profileKey === credentialProfileKey(profile)) {
    if (facts.eligibility === "confirmed") return { ...base, status: "ready", label: "응시요건 자기확인" };
    if (facts.eligibility === "not_met") return { ...base, status: "prepare", label: "응시요건 준비 중" };
  }
  if (rule.route === "manual") return { ...base, status: "check", label: "공식 취득요건 확인" };
  const finalYear = profile.grade >= 4 || profile.status === "졸업예정";
  if (!finalYear) return { ...base, status: "prepare", label: "학력 경로는 최종학년부터",
    reason: rule.detail + " 현재 학년은 학력 경로의 최종학년 전이에요. 다른 경로를 충족했다면 아래에서 자기확인 결과를 기록하세요." };
  if (rule.route === "clinical" && facts?.clinicalPractice === "none") {
    return { ...base, status: "prepare", label: "임상심리 수련·경력 준비",
      reason: "입력한 이력에 실습수련 1년·실무 2년이 없어요. 인정되는 수련·실무기관의 모집공고와 증빙 기준을 확인하세요." };
  }
  return { ...base, status: "check", label: rule.route === "clinical" ? "학력·수련 요건 확인" : "최종학년 응시요건 확인" };
}
