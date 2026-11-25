// 직무·역량 사전 (설명용 초안). 시험·자격 정보는 등록 시 공식 안내를 다시 확인한다.
import type { Job, Skill } from "../types";
import { DEPT_JOBS, DEPT_SKILLS } from "./deptTracks";
import { DEPT_JOBS_2, DEPT_SKILLS_2 } from "./deptTracks2";
import { PRACTICE } from "./practice";
import { POSTING_PROJECTS } from "./postingProjects";
import { CAMPUS_NODES } from "./campusNodes";
import { CAREER_CREDENTIALS } from "./careerCredentials";

const s = (id: string, name: string, kind: Skill["kind"], verifiable = false, officialUrl?: string): Skill => ({
  id,
  name,
  kind,
  verifiable,
  officialUrl,
});

const QNET = "https://www.q-net.or.kr/";
const DATAQ = "https://www.dataq.or.kr/";

export const SKILLS: Skill[] = [
  ...DEPT_SKILLS,
  ...DEPT_SKILLS_2,
  ...CAREER_CREDENTIALS.map(({ id, name, officialUrl }) => s(id, name, "자격증", true, officialUrl)),
  ...PRACTICE.map(({ id, name }) => s(id, name, "프로젝트")),
  ...POSTING_PROJECTS.map(({ id, name }) => s(id, name, "프로젝트")),
  ...CAMPUS_NODES.map(({ id, name, url }) => s(id, name, "경험", false, url)),
  // 공통
  s("SK-TOEIC", "TOEIC", "어학", true, "https://exam.toeic.co.kr/"),
  s("SK-TOEIC-SPEAKING", "TOEIC Speaking", "어학", true),
  s("SK-FINANCE-MANAGER", "재경관리사", "자격증", true),
  s("SK-NURSING-LICENSE", "간호사 면허", "자격증", true),
  s("SK-CHILDCARE-2", "보육교사 2급", "자격증", true),
  s("SK-KOREAN-TEACHER-2", "한국어교원 2급", "자격증", true),
  s("SK-OPIC", "OPIc", "어학", true, "https://www.opic.or.kr/"),
  s("SK-JLPT", "JLPT", "어학", true, "https://www.jlpt.or.kr/"),
  s("SK-HSK", "HSK", "어학", true, "https://www.hsk.or.kr/"),
  s("SK-DELF", "DELF", "어학", true),
  s("SK-COMP", "컴퓨터활용능력", "자격증", true, "https://license.korcham.net/"),
  s("SK-PORT", "포트폴리오 정리", "프로젝트"),
  s("SK-RESUME", "이력서·자기소개서", "역량"),
  s("SK-PPT", "기획서·발표", "역량"),
  // 직무 공고에 근거가 있을 때 스킬트리에 추가하는 결과물
  s("SK-SQL-PROJECT", "SQL 분석 쿼리와 결과표", "프로젝트"),
  s("SK-ANALYSIS-REPORT", "데이터 분석 보고서", "프로젝트"),
  s("SK-PRESENTATION-SAMPLE", "발표 자료", "프로젝트"),
  s("SK-PROPOSAL", "기획서·제안서 작성", "프로젝트"),
  s("SK-WRITING-SAMPLE", "글쓰기 작업물", "프로젝트"),
  s("SK-CAD-DRAWING", "CAD 도면", "프로젝트"),
  s("SK-BRIEF", "업무 보고서", "프로젝트"),
  s("SK-SPREADSHEET", "엑셀 분석표", "프로젝트"),
  s("SK-HYGIENIST", "위생사", "자격증", true),
  s("SK-FOOD-ENGINEER", "식품기사", "자격증", true, QNET),
  s("SK-FOOD-INDUSTRIAL", "식품산업기사", "자격증", true, QNET),
  // ICT
  s("SK-PY-01", "Python 기초", "교육"),
  s("SK-DA", "데이터 분석(pandas)", "프로젝트"),
  s("SK-SQL", "SQL 실습", "교육"),
  s("SK-SQLD", "SQLD", "자격증", true, DATAQ),
  s("SK-ADSP", "ADsP", "자격증", true, DATAQ),
  s("SK-ML-EVAL", "모델 평가", "프로젝트"),
  s("SK-DL", "딥러닝 프로젝트", "프로젝트"),
  s("SK-DEPLOY", "모델·서비스 배포", "프로젝트"),
  s("SK-ALGO", "알고리즘·코딩테스트", "역량"),
  s("SK-WEB", "웹 개발 프로젝트", "프로젝트"),
  s("SK-INFO-PE", "정보처리기사", "자격증", true, QNET),
  s("SK-CIRCUIT", "회로 설계 기초", "교육"),
  s("SK-EMB", "임베디드 프로젝트", "프로젝트"),
  s("SK-ELEC-PE", "전자기사", "자격증", true, QNET),
  // 바이오·약학·의료
  s("SK-BIO-LAB", "세포배양·실험 기본기", "교육"),
  s("SK-BIOINFO", "바이오인포매틱스 프로젝트", "프로젝트"),
  s("SK-SCI-PAPER", "학부연구생·논문 참여", "경험"),
  s("SK-GMP", "GMP 교육 이수", "교육"),
  s("SK-BIO-QC", "품질관리(QC/QA) 실무", "교육"),
  s("SK-BIO-PE", "바이오화학제품제조기사", "자격증", true, QNET),
  s("SK-PHARM-INTERN", "제약·약국 실무실습", "경험"),
  s("SK-RA", "인허가(RA) 교육", "교육"),
  s("SK-CLIN", "임상실습", "경험"),
  s("SK-BLS", "BLS 자격", "자격증", true),
  s("SK-RESEARCH", "임상 연구 참여", "경험"),
  // 경영·공공·법
  s("SK-ACC", "전산회계 1급", "자격증", true),
  s("SK-FIN", "재무분석 프로젝트", "프로젝트"),
  s("SK-MKT", "마케팅 기획 프로젝트", "프로젝트"),
  s("SK-TRADE", "국제무역사", "자격증", true),
  s("SK-NCS", "NCS 직업기초능력", "역량"),
  s("SK-KHIST", "한국사능력검정", "자격증", true),
  s("SK-POLICY", "정책 리서치 프로젝트", "프로젝트"),
  s("SK-LAW-DOC", "법률 문서 작성", "역량"),
  s("SK-STAT", "통계 분석(R)", "교육"),
  // 사회·교육
  s("SK-SW-CERT", "사회복지사 2급(교과 이수)", "자격증", true),
  s("SK-COUNSEL", "상담 실습", "경험"),
  s("SK-VOL", "봉사·현장 활동", "경험"),
  s("SK-SPED", "특수교사 자격(교직 이수)", "자격증", true),
  s("SK-KOR-TEACH", "한국어교원 자격", "자격증", true),
  // 생활과학·환경
  s("SK-DESIGN-TOOL", "CAD·3D 툴", "교육"),
  s("SK-INTERIOR", "실내건축기사", "자격증", true, QNET),
  s("SK-FASHION", "패션 MD 프로젝트", "프로젝트"),
  s("SK-DIET", "영양사 면허", "자격증", true),
  s("SK-HACCP", "식품위생·HACCP 교육", "교육"),
  s("SK-ENV-PE", "수질·대기환경기사", "자격증", true, QNET),
  s("SK-LAB-ANAL", "기기분석 실습", "교육"),
  // 콘텐츠·예술
  s("SK-CONTENT", "콘텐츠 기획 프로젝트", "프로젝트"),
  s("SK-WRITE", "글쓰기·카피라이팅", "역량"),
  s("SK-SNS", "SNS 채널 운영", "경험"),
  s("SK-VIDEO", "영상 편집", "교육"),
  s("SK-PERF", "공연·무대 경험", "경험"),
  s("SK-ARTS-PLAN", "공연 기획", "프로젝트"),
  // 신학·비영리
  s("SK-PASTORAL", "사목 실습", "경험"),
  s("SK-NPO", "비영리 프로그램 기획", "프로젝트"),
  // 창업
  s("SK-IDEA", "고객 인터뷰·아이디어 검증", "경험"),
  s("SK-BMC", "비즈니스 모델 캔버스", "교육"),
  s("SK-BIZPLAN", "사업계획서 작성", "역량"),
  s("SK-MVP", "시제품(MVP) 제작", "프로젝트"),
  s("SK-IR", "IR 피칭", "경험"),
  // 주요 공통 직무 보강(2026-11-25): 입문 → 핵심 → 실전 → 지원 단계가 이어지도록 더한 준비 노드
  s("SK-GIT", "Git·GitHub 협업", "역량"),
  s("SK-CSBASIC", "CS 기초 정리(자료구조·운영체제·네트워크)", "역량"),
  s("SK-API", "REST API 서버 만들기", "프로젝트"),
  s("SK-TEAMPROJ", "팀 프로젝트(협업 개발)", "프로젝트"),
  s("SK-CLOUD", "클라우드에 서비스 배포", "프로젝트"),
  s("SK-INTERN-DEV", "개발 인턴·현장실습", "경험"),
  s("SK-TECH-INTERVIEW", "기술 면접 준비", "역량"),
  s("SK-MARKET-RESEARCH", "시장·경쟁사 조사 보고서", "프로젝트"),
  s("SK-GA4", "웹 로그 분석(GA4) 실습", "역량"),
  s("SK-ADS", "소액 광고 집행·성과 분석", "프로젝트"),
  s("SK-CONTEST-MKT", "마케팅 공모전 출품", "경험"),
  s("SK-INTERN-MKT", "마케팅 인턴·대외활동", "경험"),
  s("SK-PUBLIC-TARGET", "목표 기관·직렬 정하기", "역량"),
  s("SK-NCS-MOCK", "NCS 실전 모의고사", "역량"),
  s("SK-PUBLIC-INTERN", "공공기관 체험형 인턴", "경험"),
  s("SK-PUBLIC-INTERVIEW", "경험·상황 면접 준비", "역량"),
  s("NUR-BASIC", "핵심기본간호술 실습", "경험"),
  s("NUR-CASE", "임상실습 사례 보고서", "프로젝트"),
  s("NUR-HOSPITAL", "목표 병원 정하기", "역량"),
  s("NUR-APPLY", "병원 지원서·면접 준비", "프로젝트"),
  s("NUR-EXAM", "간호사 국가시험(면허)", "자격증", true),
];

export const JOBS: Job[] = [
  ...DEPT_JOBS,
  ...DEPT_JOBS_2,
  {
    id: "ai-engineer",
    name: "AI 엔지니어",
    summary: "모델을 만들고 평가해 서비스로 배포한다",
    fields: ["ict", "bio", "science"],
    nodes: [
      { skill: "SK-PY-01", required: true },
      { skill: "SK-DA", prereq: ["SK-PY-01"], required: true },
      { skill: "SK-ML-EVAL", prereq: ["SK-DA"], required: true },
      { skill: "SK-SQLD", prereq: ["SK-PY-01"], required: false },
      { skill: "SK-DL", prereq: ["SK-ML-EVAL"], required: false },
      { skill: "SK-DEPLOY", prereq: ["SK-DL"], required: false },
      { skill: "SK-OPIC", required: false },
    ],
  },
  {
    id: "data-analyst",
    name: "데이터 분석가",
    summary: "데이터로 문제를 정의하고 의사결정을 돕는다",
    fields: ["ict", "science", "business", "law_econ", "social"],
    nodes: [
      { skill: "SK-PY-01", required: true },
      { skill: "SK-SQL", required: true },
      { skill: "SK-DA", prereq: ["SK-PY-01", "SK-SQL"], required: true },
      { skill: "SK-SQLD", prereq: ["SK-SQL"], required: false },
      { skill: "SK-ADSP", prereq: ["SK-DA"], required: false },
      { skill: "SK-STAT", required: false },
    ],
  },
  {
    id: "sw-developer",
    name: "소프트웨어 개발자",
    summary: "웹·앱·서버를 설계하고 만든다",
    fields: ["ict"],
    nodes: [
      { skill: "SK-ALGO", required: true },
      { skill: "SK-GIT", required: false },
      { skill: "SK-SQL", required: false },
      { skill: "SK-CSBASIC", prereq: ["SK-ALGO"], required: false },
      { skill: "SK-WEB", prereq: ["SK-ALGO", "SK-GIT"], required: true },
      { skill: "SK-API", prereq: ["SK-WEB", "SK-SQL"], required: false },
      { skill: "SK-TEAMPROJ", prereq: ["SK-WEB"], required: false },
      { skill: "SK-INFO-PE", prereq: ["SK-CSBASIC"], required: false },
      { skill: "SK-SQLD", prereq: ["SK-SQL"], required: false },
      { skill: "SK-CLOUD", prereq: ["SK-API"], required: false },
      { skill: "SK-INTERN-DEV", prereq: ["SK-TEAMPROJ"], required: false },
      { skill: "SK-PORT", prereq: ["SK-TEAMPROJ"], required: true },
      { skill: "SK-TECH-INTERVIEW", prereq: ["SK-CSBASIC", "SK-PORT"], required: false },
    ],
  },
  {
    id: "electronics",
    name: "전자·통신 엔지니어",
    summary: "회로·임베디드·통신 시스템을 설계한다",
    fields: ["ict", "engineering", "science"],
    nodes: [
      { skill: "SK-CIRCUIT", required: true },
      { skill: "SK-EMB", prereq: ["SK-CIRCUIT"], required: true },
      { skill: "SK-ELEC-PE", prereq: ["SK-CIRCUIT"], required: false },
      { skill: "SK-TOEIC", required: false },
    ],
  },
  {
    id: "bio-researcher",
    name: "바이오 연구원",
    summary: "실험과 데이터로 생명과학 문제를 연구한다",
    fields: ["bio", "science"],
    nodes: [
      { skill: "SK-BIO-LAB", required: true },
      { skill: "SK-SCI-PAPER", prereq: ["SK-BIO-LAB"], required: true },
      { skill: "SK-BIOINFO", prereq: ["SK-BIO-LAB"], required: false },
      { skill: "SK-TOEIC", required: false },
    ],
  },
  {
    id: "bio-qa",
    name: "바이오의약 생산·품질",
    summary: "GMP 환경에서 의약품 생산과 품질을 관리한다",
    fields: ["bio", "pharmacy", "science"],
    nodes: [
      { skill: "SK-BIO-LAB", required: true },
      { skill: "SK-GMP", prereq: ["SK-BIO-LAB"], required: true },
      { skill: "SK-BIO-QC", prereq: ["SK-GMP"], required: true },
      { skill: "SK-BIO-PE", required: false },
    ],
  },
  {
    id: "pharma",
    name: "제약·약무",
    summary: "제약사·약국·인허가 분야에서 일한다",
    fields: ["pharmacy"],
    nodes: [
      { skill: "SK-PHARM-INTERN", required: true },
      { skill: "SK-GMP", required: false },
      { skill: "SK-RA", prereq: ["SK-PHARM-INTERN"], required: false },
      { skill: "SK-TOEIC", required: false },
    ],
  },
  {
    id: "nurse",
    name: "간호사",
    summary: "병원과 지역사회에서 환자를 간호한다",
    fields: ["nursing"],
    nodes: [
      { skill: "SK-BLS", required: true },
      { skill: "NUR-BASIC", required: false },
      { skill: "SK-TOEIC", required: false },
      { skill: "SK-VOL", required: false },
      { skill: "SK-CLIN", prereq: ["SK-BLS", "NUR-BASIC"], required: true },
      { skill: "NUR-CASE", prereq: ["SK-CLIN"], required: false },
      { skill: "NUR-HOSPITAL", required: false },
      { skill: "SK-RESEARCH", prereq: ["SK-CLIN"], required: false },
      { skill: "NUR-APPLY", prereq: ["NUR-HOSPITAL", "NUR-CASE"], required: false },
      { skill: "NUR-EXAM", prereq: ["SK-CLIN"], required: true },
    ],
  },
  {
    id: "clinical",
    name: "의료·간호 전문인",
    summary: "임상 현장과 연구에서 환자를 돌본다",
    fields: ["medicine", "nursing"],
    nodes: [
      { skill: "SK-BLS", required: true },
      { skill: "SK-CLIN", prereq: ["SK-BLS"], required: true },
      { skill: "SK-RESEARCH", prereq: ["SK-CLIN"], required: false },
      { skill: "SK-TOEIC", required: false },
    ],
  },
  {
    id: "content-planner",
    name: "콘텐츠 기획자",
    summary: "문화·미디어 콘텐츠를 기획하고 만든다",
    fields: ["language", "humanities", "arts", "ict"],
    nodes: [
      { skill: "SK-WRITE", required: true },
      { skill: "SK-CONTENT", prereq: ["SK-WRITE"], required: true },
      { skill: "SK-VIDEO", required: false },
      { skill: "SK-SNS", prereq: ["SK-CONTENT"], required: false },
      { skill: "SK-PORT", prereq: ["SK-CONTENT"], required: true },
    ],
  },
  {
    id: "overseas-sales",
    name: "해외영업·무역",
    summary: "외국어와 비즈니스로 해외 시장을 연다",
    fields: ["language", "business", "law_econ"],
    nodes: [
      { skill: "SK-TOEIC", required: true },
      { skill: "SK-OPIC", required: false },
      { skill: "SK-TRADE", prereq: ["SK-TOEIC"], required: false },
      { skill: "SK-PPT", required: true },
      { skill: "SK-JLPT", required: false },
      { skill: "SK-HSK", required: false },
      { skill: "SK-DELF", required: false },
    ],
  },
  {
    id: "finance",
    name: "경영기획·재무회계",
    summary: "숫자로 회사의 방향과 성과를 관리한다",
    fields: ["business", "law_econ"],
    nodes: [
      { skill: "SK-ACC", required: true },
      { skill: "SK-FIN", prereq: ["SK-ACC"], required: true },
      { skill: "SK-COMP", required: false },
      { skill: "SK-PPT", required: false },
    ],
  },
  {
    id: "marketer",
    name: "마케터",
    summary: "고객을 이해하고 브랜드·상품을 알린다",
    fields: ["business", "living", "social", "language"],
    nodes: [
      { skill: "SK-MARKET-RESEARCH", required: false },
      { skill: "SK-WRITE", required: false },
      { skill: "SK-COMP", required: false },
      { skill: "SK-TOEIC", required: false },
      { skill: "SK-MKT", prereq: ["SK-MARKET-RESEARCH"], required: true },
      { skill: "SK-SNS", prereq: ["SK-WRITE"], required: false },
      { skill: "SK-DA", required: false },
      { skill: "SK-GA4", prereq: ["SK-SNS"], required: false },
      { skill: "SK-PPT", prereq: ["SK-MKT"], required: true },
      { skill: "SK-CONTEST-MKT", prereq: ["SK-MKT"], required: false },
      { skill: "SK-ADS", prereq: ["SK-SNS", "SK-MKT"], required: false },
      { skill: "SK-INTERN-MKT", prereq: ["SK-CONTEST-MKT"], required: false },
      { skill: "SK-PORT", prereq: ["SK-ADS", "SK-PPT"], required: false },
    ],
  },
  {
    id: "public-sector",
    name: "공공기관·행정",
    summary: "공공기관·지자체에서 정책과 행정을 맡는다",
    fields: ["law_econ", "humanities", "social"],
    nodes: [
      { skill: "SK-PUBLIC-TARGET", required: false },
      { skill: "SK-NCS", required: true },
      { skill: "SK-KHIST", prereq: ["SK-PUBLIC-TARGET"], required: false },
      { skill: "SK-COMP", prereq: ["SK-PUBLIC-TARGET"], required: false },
      { skill: "SK-TOEIC", prereq: ["SK-PUBLIC-TARGET"], required: false },
      { skill: "SK-VOL", required: false },
      { skill: "SK-POLICY", prereq: ["SK-PUBLIC-TARGET"], required: false },
      { skill: "SK-NCS-MOCK", prereq: ["SK-NCS"], required: false },
      { skill: "SK-PUBLIC-INTERN", prereq: ["SK-NCS", "SK-COMP"], required: false },
      { skill: "SK-RESUME", prereq: ["SK-PUBLIC-TARGET", "SK-PUBLIC-INTERN"], required: false },
      { skill: "SK-PUBLIC-INTERVIEW", prereq: ["SK-RESUME", "SK-NCS-MOCK"], required: false },
    ],
  },
  {
    id: "legal",
    name: "법무·컴플라이언스",
    summary: "기업·기관의 법률 리스크를 관리한다",
    fields: ["law_econ"],
    nodes: [
      { skill: "SK-LAW-DOC", required: true },
      { skill: "SK-POLICY", required: false },
      { skill: "SK-TOEIC", required: false },
    ],
  },
  {
    id: "welfare",
    name: "사회복지·상담",
    summary: "현장에서 사람과 지역사회를 돕는다",
    fields: ["social", "theology"],
    nodes: [
      { skill: "SK-VOL", required: true },
      { skill: "SK-SW-CERT", required: true },
      { skill: "SK-COUNSEL", prereq: ["SK-VOL"], required: false },
    ],
  },
  {
    id: "educator",
    name: "교육 전문가",
    summary: "특수교육·한국어교육·아동교육 현장에서 가르친다",
    fields: ["social", "language"],
    nodes: [
      { skill: "SK-VOL", required: true },
      { skill: "SK-SPED", required: false },
      { skill: "SK-KOR-TEACH", required: false },
      { skill: "SK-PPT", required: false },
    ],
  },
  {
    id: "designer",
    name: "공간·패션 디자이너",
    summary: "공간·제품·패션을 디자인하고 기획한다",
    fields: ["living", "arts"],
    nodes: [
      { skill: "SK-DESIGN-TOOL", required: true },
      { skill: "SK-PORT", prereq: ["SK-DESIGN-TOOL"], required: true },
      { skill: "SK-INTERIOR", required: false },
      { skill: "SK-FASHION", required: false },
    ],
  },
  {
    id: "food",
    name: "식품·영양 전문가",
    summary: "식품 개발·급식·영양 관리를 맡는다",
    fields: ["living", "bio"],
    nodes: [
      { skill: "SK-HACCP", required: true },
      { skill: "SK-DIET", required: false },
      { skill: "SK-BIO-QC", required: false },
    ],
  },
  {
    id: "env-engineer",
    name: "에너지·환경 엔지니어",
    summary: "에너지·환경 문제를 측정하고 해결한다",
    fields: ["engineering", "science"],
    nodes: [
      { skill: "SK-LAB-ANAL", required: true },
      { skill: "SK-ENV-PE", prereq: ["SK-LAB-ANAL"], required: false },
      { skill: "SK-STAT", required: false },
    ],
  },
  {
    id: "arts-planner",
    name: "공연예술·문화기획",
    summary: "무대에 서거나 공연·문화 행사를 만든다",
    fields: ["arts", "humanities"],
    nodes: [
      { skill: "SK-PERF", required: true },
      { skill: "SK-ARTS-PLAN", prereq: ["SK-PERF"], required: false },
      { skill: "SK-VIDEO", required: false },
      { skill: "SK-PORT", required: true },
    ],
  },
  {
    id: "npo",
    name: "사목·비영리",
    summary: "교회와 비영리 현장에서 공동체를 섬긴다",
    fields: ["theology", "social"],
    nodes: [
      { skill: "SK-VOL", required: true },
      { skill: "SK-PASTORAL", required: false },
      { skill: "SK-NPO", prereq: ["SK-VOL"], required: false },
    ],
  },
  {
    id: "founder",
    name: "창업가",
    summary: "아이디어를 검증해 사업으로 만든다 — 모든 전공 가능",
    fields: [
      "humanities", "language", "social", "law_econ", "business", "science", "engineering",
      "living", "bio", "ict", "arts", "pharmacy", "medicine", "nursing", "theology", "open",
    ],
    nodes: [
      { skill: "SK-IDEA", required: true },
      { skill: "SK-BMC", prereq: ["SK-IDEA"], required: true },
      { skill: "SK-BIZPLAN", prereq: ["SK-BMC"], required: true },
      { skill: "SK-MVP", prereq: ["SK-BMC"], required: false },
      { skill: "SK-IR", prereq: ["SK-BIZPLAN"], required: false },
    ],
  },
];

// ───────── 점수제·등급제 자격
// 여기에 없는 자격은 합격/불합격으로만 기록한다(기사·산업기사, 면허, SQLD·ADsP 등).
export type Scale = { unit: string; min: number; max: number } | { grades: string[] }; // grades는 낮은 등급 → 높은 등급
export const SCALES: Record<string, Scale> = {
  "SK-TOEIC": { unit: "점", min: 10, max: 990 },
  "SK-TOEIC-SPEAKING": { grades: ["NL", "NM", "NH", "IL", "IM1", "IM2", "IM3", "IH", "AL", "AM", "AH"] },
  "SK-OPIC": { grades: ["NL", "NM", "NH", "IL", "IM1", "IM2", "IM3", "IH", "AL"] },
  "SK-JLPT": { grades: ["N5", "N4", "N3", "N2", "N1"] },
  "SK-HSK": { grades: ["1급", "2급", "3급", "4급", "5급", "6급"] },
  "SK-DELF": { grades: ["A1", "A2", "B1", "B2", "C1", "C2"] },
  "SK-COMP": { grades: ["2급", "1급"] },
  "CERT-TAX": { grades: ["2급", "1급"] },
  "SK-KHIST": { grades: ["6급", "5급", "4급", "3급", "2급", "1급"] },
  "HIS-C-HANJA": { grades: ["8급", "7급", "6급", "5급", "4급", "3급", "2급", "1급"] },
  "CLO-C-GTQ": { grades: ["3급", "2급", "1급"] },
};
export const scaleOf = (skillId: string): Scale | undefined => SCALES[skillId];
export const formatScore = (skillId: string, value?: string) => {
  const sc = SCALES[skillId];
  return !sc || !value ? "" : "grades" in sc ? value : `${value}${sc.unit}`;
};
// 내 점수·등급이 권장 기준 이상인지. 기준이나 점수가 없으면 null(판단하지 않음)
export function meetsTarget(skillId: string, value?: string, target?: string): boolean | null {
  const sc = SCALES[skillId];
  if (!sc || !value || !target) return null;
  if ("grades" in sc) {
    const [v, t] = [sc.grades.indexOf(value), sc.grades.indexOf(target)];
    return v < 0 || t < 0 ? null : v >= t;
  }
  return Number(value) >= Number(target);
}

// ───────── 관리자 수정본 적용
// 서버에 저장된 수정본(직무·스킬)을 기본 사전 위에 덮어쓴다. 배열을 제자리에서 바꾸므로 모든 화면에 바로 반영된다.
export interface CatalogOverrides {
  skills: Record<string, Skill>;
  jobs: Record<string, Job>;
}
const BASE_SKILLS = [...SKILLS];
const BASE_JOBS = [...JOBS];
export const isBaseJob = (id: string) => BASE_JOBS.some((j) => j.id === id);

// 잘못된 수정본이 화면을 멈추지 않게 한다: 없는 스킬·트랙 밖 선행·순환 선행을 걸러낸다
export function sanitizeJob(job: Job, known: Set<string>): Job {
  const seen = new Set<string>();
  const nodes = (Array.isArray(job.nodes) ? job.nodes : [])
    .filter((n) => n && known.has(n.skill) && !seen.has(n.skill) && seen.add(n.skill))
    .map((n) => ({ skill: n.skill, required: !!n.required, prereq: (n.prereq ?? []).filter((q) => q !== n.skill), ...(n.target && { target: String(n.target) }) }));
  const own = new Set(nodes.map((n) => n.skill));
  for (const n of nodes) n.prereq = n.prereq.filter((q) => own.has(q));
  const byId = new Map(nodes.map((n) => [n.skill, n]));
  const state = new Map<string, 1 | 2>(); // 1 방문 중, 2 완료
  const visit = (id: string) => {
    state.set(id, 1);
    const n = byId.get(id)!;
    n.prereq = n.prereq.filter((q) => {
      if (state.get(q) === 1) return false; // 순환을 만드는 선행은 버린다
      if (!state.has(q)) visit(q);
      return true;
    });
    state.set(id, 2);
  };
  for (const n of nodes) if (!state.has(n.skill)) visit(n.skill);
  return { ...job, name: String(job.name ?? ""), summary: String(job.summary ?? ""), fields: job.fields ?? [], nodes };
}

export function applyOverrides(ov: Partial<CatalogOverrides> | null) {
  const skills = new Map(BASE_SKILLS.map((x) => [x.id, x]));
  for (const [id, x] of Object.entries(ov?.skills ?? {})) if (x?.name) skills.set(id, { ...x, id, verifiable: x.verifiable ?? false, kind: x.kind ?? "역량" });
  SKILLS.length = 0;
  SKILLS.push(...skills.values());
  const known = new Set(skills.keys());
  const jobs = new Map(BASE_JOBS.map((x) => [x.id, x]));
  for (const [id, x] of Object.entries(ov?.jobs ?? {})) if (x?.name) jobs.set(id, sanitizeJob({ ...x, id }, known));
  JOBS.length = 0;
  JOBS.push(...jobs.values());
}

const startupSkills = new Map<string, Skill>();
export function registerStartupSkills(skills: Skill[]) {
  startupSkills.clear();
  for (const skill of skills) startupSkills.set(skill.id, skill);
}
export const skillById = (id: string) => SKILLS.find((x) => x.id === id) ?? startupSkills.get(id);
export const jobById = (id: string) => JOBS.find((x) => x.id === id);
