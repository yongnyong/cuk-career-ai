// 프론트·백엔드 공통 데이터 계약. FastAPI 스키마도 이 구조를 따른다.
import type { Field } from "./data/departments";

export type SkillKind = "어학" | "자격증" | "프로젝트" | "교육" | "경험" | "역량";

export interface Skill {
  id: string; // 예: SK-PY-01
  name: string;
  kind: SkillKind;
  verifiable: boolean; // 증빙으로 검증 가능한 자격(어학 점수·자격증)인지
  officialUrl?: string; // 시험·자격 공식 확인 경로
  from?: "학과"; // 학과 홈페이지에 근거가 있는 항목
  srcUrl?: string; // 근거 페이지
}

export interface Job {
  id: string;
  name: string;
  summary: string;
  fields: Field[]; // 우선 추천 계열(전공은 출발점일 뿐, 모든 직무 선택 가능)
  // 스킬트리 노드: 순서대로 선행 관계, prereq로 분기
  // target: 학과가 권장한 점수·등급(예: "2급", "700")
  nodes: { skill: string; prereq?: string[]; required: boolean; target?: string }[];
  departments?: string[]; // 학과 전용 테크(해당 학과 id). 없으면 모든 학과 공통 직무
  base?: string; // 공고 연결에 쓰는 공통 직무 id
  srcUrl?: string; // 학과 진로 페이지
}

export type OppType = "현장실습" | "창업지원" | "채용" | "장학" | "학사" | "비교과";

export interface Condition {
  key: "status" | "grade" | "major" | "skill" | "degree" | "startup" | "age" | "region" | "other";
  label: string; // 화면 표시용
  // 규칙 엔진이 검사할 값(명시적 조건만). other는 자동 판정하지 않고 "확인 필요"
  status?: ("재학" | "휴학" | "졸업예정")[];
  grades?: number[];
  majors?: Field[];
  skill?: string;
  stages?: string[]; // 창업 단계: 예비창업자, 1년미만 … (K-Startup 공식 값)
  ages?: string[]; // 대상 연령대: u20, 20-39, 40+
  regions?: string[]; // 거주·사업장 시·도
  min?: string; // 어학·자격의 최소 점수·등급(예: "700", "IM2")
  degree?: "none" | "high" | "associate" | "bachelor" | "master" | "unknown"; // 채용 공고의 최소 학력
  src: string; // 근거 문단 ID (예: §2)
}

export interface Section {
  id: string; // §1 ...
  title: string;
  text: string;
}

export interface OppVersion {
  version: number;
  checkedAt: string; // 확인 시각 ISO
  deadline: string; // ISO
  changes?: { field: string; before: string; after: string }[];
}

export interface Opportunity {
  id: string;
  type: OppType;
  title: string;
  org: string;
  source: { name: string; url: string };
  isVirtual: boolean; // 가상 테스트 공고 여부 — 화면·통계에서 반드시 구분
  jobs: string[]; // 연결 직무
  required: Condition[];
  preferred: string[]; // 우대 역량(skill id)
  documents: string[];
  applyUrl: string; // 공식 신청처
  period?: string; // 활동 기간
  sections: Section[]; // 원문 의미 단위 청크
  conditionsBy?: "ai" | "rule"; // 필수 조건을 AI가 정리했는지
  facts?: { label: string; value: string }[]; // 핵심 정보(지원금·우대 사항·창업 단계 등). 원문에 적힌 것만
  versions: OppVersion[]; // 최신 버전이 마지막
  confidence: number; // AI 구조화 신뢰도 (0.8 미만이면 검수 대기)
  reviewed: boolean;
}

export type Verdict = "pass" | "fail" | "check";

export interface ConditionResult {
  condition: Condition;
  verdict: Verdict;
  reason: string;
}

export type SkillState = "none" | "self" | "verified";

export interface Profile {
  pseudoId: string; // 로그인 아이디(가명) — 이름·연락처·학번 전체는 받지 않는다
  admissionYear: number; // 학번 = 입학년도(예: 2021 → 21학번). 개인 식별이 되는 학번 전체는 저장하지 않는다
  campus: string;
  departmentId: string;
  grade: number;
  status: "재학" | "휴학" | "졸업예정";
  jobId: string;
  interests: string[];
  weeklyHours: number;
  targetTerm: string;
  skills: Record<string, SkillState>;
  scores?: Record<string, string>;
  // 창업 공고 판정에만 쓰는 선택 정보. stage: none(계획 없음) | pre(예비창업자) | 1·3·7·10(창업 n년 미만)
  startup?: { stage?: string; region?: string; birthYear?: number }; // 점수제·등급제 자격의 내 점수·등급(자기 보고)
  createdAt: string;
}

export interface Notice {
  id: string;
  oppId: string;
  version: number;
  kind: "D-7" | "D-3" | "D-1" | "정정" | "새 기회";
  fireAt: string; // ISO
  message: string;
  status: "scheduled" | "sent" | "cancelled";
  idempotencyKey: string; // oppId:version:kind — 중복 발송 방지
}

export interface ChatAnswer {
  text: string;
  citations: { sectionId: string; version: number }[];
  held: boolean; // 근거 부족으로 답변 보류
}
