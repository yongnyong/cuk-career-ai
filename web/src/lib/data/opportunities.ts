// 시연·개발용 가상 테스트 공고. 실제 모집이 아니며 화면·통계·평가에서 반드시 "가상"으로 구분한다.
// 실제 공개 공고는 수집 파이프라인(api/)에서 들어오며 isVirtual=false로 저장된다.
import type { Condition, OppType, Opportunity, Section } from "../types";
import type { Field } from "./departments";
import { skillById } from "./catalog";

const CUK_NOTICE = "https://www.catholic.ac.kr/ko/campuslife/notice.do";
const KSTARTUP = "https://www.k-startup.go.kr/";

interface Seed {
  id: string;
  type: OppType;
  title: string;
  org: string;
  jobs: string[];
  deadline: string; // YYYY-MM-DD HH:mm (KST)
  grades?: number[];
  status?: ("재학" | "휴학" | "졸업예정")[];
  majors?: Field[];
  requiredSkill?: string;
  other?: string; // 자동 판정 불가 조건 → 확인 필요
  preferred?: string[];
  documents: string[];
  period?: string;
  summary: string;
  confidence?: number;
  extra?: string;
}

const iso = (kst: string) => kst.replace(" ", "T") + ":00+09:00";

function build(x: Seed): Opportunity {
  const required: Condition[] = [];
  const quals: string[] = [];
  if (x.status) {
    required.push({ key: "status", label: x.status.join("·") + "생", status: x.status, src: "§2" });
    quals.push(`${x.status.join(" 또는 ")} 중인 학생`);
  }
  if (x.grades) {
    required.push({ key: "grade", label: `${x.grades.join("·")}학년`, grades: x.grades, src: "§2" });
    quals.push(`${x.grades.join("·")}학년`);
  }
  if (x.majors) {
    required.push({ key: "major", label: "지정 계열 전공", majors: x.majors, src: "§2" });
    quals.push("공고에서 지정한 계열 전공자");
  }
  if (x.requiredSkill) {
    const sk = skillById(x.requiredSkill);
    required.push({ key: "skill", label: `${sk?.name ?? x.requiredSkill} 보유`, skill: x.requiredSkill, src: "§2" });
    quals.push(`${sk?.name} 보유자`);
  }
  if (x.other) {
    required.push({ key: "other", label: x.other, src: "§2" });
    quals.push(x.other);
  }
  const deadline = iso(x.deadline);
  const [date, time] = x.deadline.split(" ");
  const sections: Section[] = [
    { id: "§1", title: "모집 개요", text: `${x.org}에서 ${x.title} 참여자를 모집합니다. ${x.summary}` },
    { id: "§2", title: "지원 자격", text: quals.length ? `지원 자격: ${quals.join(", ")}.` : "지원 자격: 본교 학부생 누구나." },
    {
      id: "§3",
      title: "우대 사항",
      text: x.preferred?.length
        ? `우대 사항: ${x.preferred.map((p) => skillById(p)?.name ?? p).join(", ")} 경험.`
        : "우대 사항: 별도 없음.",
    },
    { id: "§4", title: "제출 서류", text: `제출 서류: ${x.documents.join(", ")}. ${x.extra ?? ""}`.trim() },
    {
      id: "§5",
      title: "일정",
      text: `접수 마감: ${date} ${time}까지.${x.period ? ` 활동 기간: ${x.period}.` : ""}`,
    },
    {
      id: "§6",
      title: "신청 방법",
      text: "신청은 공식 신청처에서만 접수합니다. 본 서비스의 이동 버튼은 신청 완료를 의미하지 않습니다.",
    },
    { id: "§7", title: "문의", text: "문의: 공고 담당 부서(가상)." },
  ];
  return {
    id: x.id,
    type: x.type,
    title: x.title,
    org: x.org,
    source: { name: "가상 테스트 공고", url: x.type === "창업지원" ? KSTARTUP : CUK_NOTICE },
    isVirtual: true,
    jobs: x.jobs,
    required,
    preferred: x.preferred ?? [],
    documents: x.documents,
    applyUrl: x.type === "창업지원" ? KSTARTUP : CUK_NOTICE,
    period: x.period,
    sections,
    versions: [{ version: 1, checkedAt: "2026-11-12T09:00:00+09:00", deadline }],
    confidence: x.confidence ?? 0.93,
    reviewed: (x.confidence ?? 0.93) >= 0.8,
  };
}

const SEEDS: Seed[] = [
  // ── 현장실습 (골든 공고: 시연 장면 1·2·5)
  {
    id: "opp-ai-winter",
    type: "현장실습",
    title: "○○AI 2027 동계 인턴",
    org: "○○AI(가상)",
    jobs: ["ai-engineer", "data-analyst"],
    deadline: "2026-11-20 17:00",
    status: ["재학"],
    grades: [3, 4],
    preferred: ["SK-PY-01", "SK-ML-EVAL"],
    documents: ["이력서", "자기소개서"],
    period: "2026.12.22 ~ 2027.02.13",
    summary: "AI 모델 평가·데이터 처리 업무를 함께할 현장실습생을 모집합니다.",
    extra: "자기소개서는 A4 2매 이내.",
  },
  {
    id: "opp-data-lab",
    type: "현장실습",
    title: "△△데이터랩 데이터 분석 현장실습",
    org: "△△데이터랩(가상)",
    jobs: ["data-analyst", "ai-engineer"],
    deadline: "2026-11-27 18:00",
    status: ["재학", "휴학"],
    grades: [2, 3, 4],
    requiredSkill: "SK-SQL",
    preferred: ["SK-SQLD", "SK-DA"],
    documents: ["이력서", "분석 포트폴리오"],
    period: "2027.01.05 ~ 2027.02.27",
    summary: "공공 데이터 분석과 대시보드 제작을 지원합니다.",
  },
  {
    id: "opp-web-dev",
    type: "현장실습",
    title: "□□소프트 웹 개발 현장실습",
    org: "□□소프트(가상)",
    jobs: ["sw-developer"],
    deadline: "2026-12-04 17:00",
    status: ["재학"],
    grades: [3, 4],
    preferred: ["SK-WEB", "SK-ALGO"],
    documents: ["이력서", "GitHub 링크"],
    period: "2027.01.05 ~ 2027.02.27",
    summary: "사내 웹 서비스 프론트엔드·백엔드 개발에 참여합니다.",
  },
  {
    id: "opp-embedded",
    type: "현장실습",
    title: "◇◇전자 임베디드 현장실습",
    org: "◇◇전자(가상)",
    jobs: ["electronics"],
    deadline: "2026-12-08 17:00",
    status: ["재학"],
    grades: [3, 4],
    majors: ["ict", "engineering", "science"],
    preferred: ["SK-CIRCUIT", "SK-EMB"],
    documents: ["이력서", "자기소개서"],
    summary: "센서 펌웨어 개발과 시험 평가를 지원합니다.",
  },
  {
    id: "opp-bio-qc",
    type: "현장실습",
    title: "▽▽바이오 QC 현장실습",
    org: "▽▽바이오(가상)",
    jobs: ["bio-qa", "bio-researcher"],
    deadline: "2026-11-25 17:00",
    status: ["재학"],
    grades: [3, 4],
    majors: ["bio", "science", "pharmacy"],
    preferred: ["SK-GMP", "SK-BIO-LAB"],
    documents: ["이력서", "자기소개서", "성적증명서"],
    period: "2027.01.05 ~ 2027.02.27",
    summary: "바이오의약품 품질관리 시험을 보조합니다.",
  },
  {
    id: "opp-bio-lab",
    type: "현장실습",
    title: "○○연구소 학부 연구 인턴",
    org: "○○생명과학연구소(가상)",
    jobs: ["bio-researcher"],
    deadline: "2026-12-11 17:00",
    status: ["재학"],
    grades: [2, 3, 4],
    preferred: ["SK-BIO-LAB", "SK-BIOINFO"],
    documents: ["이력서", "연구계획서(1매)"],
    summary: "세포 실험과 데이터 정리를 함께할 연구 인턴을 모집합니다.",
  },
  {
    id: "opp-pharma",
    type: "현장실습",
    title: "□□제약 인허가(RA) 실습",
    org: "□□제약(가상)",
    jobs: ["pharma", "bio-qa"],
    deadline: "2026-12-02 17:00",
    status: ["재학"],
    majors: ["pharmacy", "bio"],
    preferred: ["SK-RA", "SK-GMP"],
    documents: ["이력서", "자기소개서"],
    summary: "의약품 허가 문서 작성 보조 업무를 경험합니다.",
  },
  {
    id: "opp-hospital",
    type: "비교과",
    title: "임상 연구 코디네이터 체험 프로그램",
    org: "○○병원 임상연구센터(가상)",
    jobs: ["clinical"],
    deadline: "2026-12-05 17:00",
    status: ["재학"],
    majors: ["medicine", "nursing"],
    preferred: ["SK-BLS"],
    documents: ["신청서"],
    summary: "임상 연구 진행 과정과 코디네이터 업무를 체험합니다.",
  },
  {
    id: "opp-overseas",
    type: "현장실습",
    title: "해외영업 실습 (영어권)",
    org: "△△무역(가상)",
    jobs: ["overseas-sales"],
    deadline: "2026-11-30 18:00",
    status: ["재학"],
    grades: [3, 4],
    other: "TOEIC 750점 이상 또는 이에 준하는 어학 성적",
    preferred: ["SK-OPIC", "SK-TRADE"],
    documents: ["영문 이력서", "어학 성적표"],
    summary: "해외 바이어 응대와 영문 제안서 작성을 지원합니다.",
    confidence: 0.76,
  },
  {
    id: "opp-japan",
    type: "현장실습",
    title: "일본 현지 마케팅 실습",
    org: "◇◇재팬(가상)",
    jobs: ["overseas-sales", "marketer"],
    deadline: "2026-12-09 17:00",
    status: ["재학"],
    other: "JLPT N2 이상",
    preferred: ["SK-JLPT", "SK-SNS"],
    documents: ["이력서", "일본어 자기소개서"],
    summary: "일본 현지 SNS 마케팅과 시장 조사를 지원합니다.",
  },
  {
    id: "opp-content",
    type: "현장실습",
    title: "문화콘텐츠 기획 실습",
    org: "○○콘텐츠랩(가상)",
    jobs: ["content-planner", "arts-planner"],
    deadline: "2026-11-28 17:00",
    status: ["재학", "휴학"],
    preferred: ["SK-CONTENT", "SK-WRITE"],
    documents: ["이력서", "기획안 1편"],
    summary: "전시·관광 콘텐츠 기획과 카피 작성을 함께합니다.",
  },
  {
    id: "opp-france",
    type: "비교과",
    title: "프랑스 문화행사 기획단",
    org: "교내 국제교류 프로그램(가상)",
    jobs: ["content-planner", "arts-planner", "overseas-sales"],
    deadline: "2026-12-03 17:00",
    preferred: ["SK-DELF", "SK-CONTENT"],
    documents: ["신청서"],
    summary: "프랑스 문화 주간 행사를 학생 기획단이 직접 꾸립니다.",
  },
  {
    id: "opp-finance",
    type: "현장실습",
    title: "회계법인 동계 실습",
    org: "△△회계법인(가상)",
    jobs: ["finance"],
    deadline: "2026-12-01 17:00",
    status: ["재학"],
    grades: [3, 4],
    requiredSkill: "SK-ACC",
    preferred: ["SK-COMP"],
    documents: ["이력서", "성적증명서"],
    summary: "감사 보조와 재무제표 분석을 경험합니다.",
  },
  {
    id: "opp-marketing",
    type: "현장실습",
    title: "브랜드 마케팅 실습",
    org: "□□브랜드(가상)",
    jobs: ["marketer", "content-planner"],
    deadline: "2026-12-06 17:00",
    status: ["재학", "휴학"],
    preferred: ["SK-MKT", "SK-SNS"],
    documents: ["이력서", "포트폴리오(선택)"],
    summary: "신제품 캠페인 기획과 소비자 조사를 지원합니다.",
  },
  {
    id: "opp-public",
    type: "현장실습",
    title: "지자체 정책 현장실습",
    org: "○○시청(가상)",
    jobs: ["public-sector", "legal"],
    deadline: "2026-11-26 18:00",
    status: ["재학"],
    preferred: ["SK-POLICY", "SK-KHIST"],
    documents: ["신청서", "재학증명서"],
    summary: "청년 정책 자료 조사와 민원 분석을 지원합니다.",
  },
  {
    id: "opp-law",
    type: "현장실습",
    title: "기업 법무팀 실습",
    org: "◇◇그룹 법무팀(가상)",
    jobs: ["legal"],
    deadline: "2026-12-10 17:00",
    status: ["재학"],
    grades: [3, 4],
    majors: ["law_econ"],
    preferred: ["SK-LAW-DOC"],
    documents: ["이력서", "자기소개서"],
    summary: "계약서 검토 보조와 법령 리서치를 경험합니다.",
  },
  {
    id: "opp-welfare",
    type: "현장실습",
    title: "지역 복지관 현장실습",
    org: "○○종합사회복지관(가상)",
    jobs: ["welfare", "npo"],
    deadline: "2026-12-12 17:00",
    status: ["재학"],
    other: "사회복지현장실습 교과 수강 예정자",
    preferred: ["SK-VOL", "SK-COUNSEL"],
    documents: ["실습 신청서"],
    summary: "사례관리와 지역사회 프로그램 운영을 실습합니다.",
  },
  {
    id: "opp-edu",
    type: "비교과",
    title: "다문화 아동 학습 멘토링",
    org: "교내 사회봉사 프로그램(가상)",
    jobs: ["educator", "welfare"],
    deadline: "2026-11-29 17:00",
    preferred: ["SK-VOL", "SK-KOR-TEACH"],
    documents: ["신청서"],
    summary: "다문화 가정 아동의 한국어·학습을 돕는 멘토를 모집합니다.",
  },
  {
    id: "opp-design",
    type: "현장실습",
    title: "공간디자인 스튜디오 실습",
    org: "△△디자인(가상)",
    jobs: ["designer"],
    deadline: "2026-12-07 17:00",
    status: ["재학"],
    preferred: ["SK-DESIGN-TOOL", "SK-INTERIOR"],
    documents: ["포트폴리오", "이력서"],
    summary: "상업 공간 설계와 소비자 동선 조사를 지원합니다.",
  },
  {
    id: "opp-fashion",
    type: "현장실습",
    title: "패션 MD 실습",
    org: "○○패션(가상)",
    jobs: ["designer", "marketer"],
    deadline: "2026-12-13 17:00",
    status: ["재학"],
    preferred: ["SK-FASHION"],
    documents: ["이력서"],
    summary: "시즌 상품 기획과 판매 데이터 분석을 경험합니다.",
  },
  {
    id: "opp-food",
    type: "현장실습",
    title: "식품 R&D 실습",
    org: "□□푸드(가상)",
    jobs: ["food", "bio-qa"],
    deadline: "2026-12-04 17:00",
    status: ["재학"],
    majors: ["living", "bio"],
    preferred: ["SK-HACCP"],
    documents: ["이력서", "자기소개서"],
    summary: "신제품 개발과 위생 관리 기록을 지원합니다.",
  },
  {
    id: "opp-env",
    type: "현장실습",
    title: "환경 분석 기관 실습",
    org: "◇◇환경연구원(가상)",
    jobs: ["env-engineer"],
    deadline: "2026-12-11 17:00",
    status: ["재학"],
    grades: [3, 4],
    preferred: ["SK-LAB-ANAL", "SK-ENV-PE"],
    documents: ["이력서"],
    summary: "수질·대기 시료 분석과 보고서 작성을 실습합니다.",
  },
  {
    id: "opp-arts",
    type: "비교과",
    title: "교내 정기 공연 기획·출연자 모집",
    org: "교내 문화예술 프로그램(가상)",
    jobs: ["arts-planner", "content-planner"],
    deadline: "2026-11-24 17:00",
    preferred: ["SK-PERF", "SK-ARTS-PLAN"],
    documents: ["신청서", "공연 영상 링크(출연자)"],
    summary: "연말 정기 공연의 기획단과 출연자를 모집합니다.",
  },
  {
    id: "opp-npo",
    type: "비교과",
    title: "본당 청년 사목 봉사단",
    org: "○○본당(가상)",
    jobs: ["npo", "welfare"],
    deadline: "2026-12-14 17:00",
    preferred: ["SK-VOL", "SK-PASTORAL"],
    documents: ["신청서"],
    summary: "청년 신앙 프로그램과 지역 나눔 활동을 함께합니다.",
  },
  // ── 창업지원 (시연 장면 3)
  {
    id: "opp-startup-camp",
    type: "창업지원",
    title: "AI 창업 캠프",
    org: "교내 창업지원단(가상)",
    jobs: ["founder", "ai-engineer"],
    deadline: "2026-11-23 18:00",
    status: ["재학", "휴학"],
    other: "예비창업 단계(사업자 미등록) 팀",
    preferred: ["SK-IDEA", "SK-BMC"],
    documents: ["참가 신청서", "아이디어 요약서"],
    summary: "아이디어 검증부터 시제품까지 4주 집중 캠프를 운영합니다.",
  },
  {
    id: "opp-startup-culture",
    type: "창업지원",
    title: "문화관광 창업 아이디어 경진",
    org: "교내 창업지원단(가상)",
    jobs: ["founder", "content-planner"],
    deadline: "2026-12-05 18:00",
    preferred: ["SK-IDEA", "SK-BIZPLAN"],
    documents: ["사업계획서", "팀 구성표"],
    summary: "문화·관광 분야 창업 아이디어를 공모하고 사업화를 지원합니다.",
  },
  {
    id: "opp-startup-seed",
    type: "창업지원",
    title: "예비창업 시제품 제작 지원",
    org: "K-Startup 연계 프로그램(가상)",
    jobs: ["founder"],
    deadline: "2026-12-18 18:00",
    other: "만 39세 이하 예비창업자",
    preferred: ["SK-BIZPLAN", "SK-MVP"],
    documents: ["사업계획서", "증빙서류"],
    summary: "시제품 제작비와 멘토링을 지원합니다.",
    confidence: 0.72,
  },
  // ── 장학·학사 (모든 학과 공통 알림)
  {
    id: "opp-scholar",
    type: "장학",
    title: "2027-1 교내 ○○장학 신청",
    org: "학생지원팀(가상)",
    jobs: [],
    deadline: "2026-11-21 17:00",
    status: ["재학"],
    other: "직전 학기 성적 기준 충족 여부는 원문에서 직접 확인",
    documents: ["장학 신청서"],
    summary: "다음 학기 교내 장학생을 선발합니다.",
  },
  {
    id: "opp-academic",
    type: "학사",
    title: "2026-2 수강 철회 기간 안내",
    org: "학사지원팀(가상)",
    jobs: [],
    deadline: "2026-11-19 23:59",
    documents: [],
    summary: "수강 철회 신청 기간을 안내합니다.",
  },
];

export const SEED_OPPORTUNITIES: Opportunity[] = SEEDS.map(build);

// 시연 장면 5용 정정 데이터: ○○AI 동계 인턴 마감 11/20 → 11/24
export const DEMO_CORRECTION = {
  oppId: "opp-ai-winter",
  newDeadline: "2026-11-24T17:00:00+09:00",
};

// 시연 장면 4용 새 공고 원문 (관리자 화면에 미리 채워 두는 예시)
export const DEMO_NEW_POSTING = `[현장실습] ◎◎글로벌 해외마케팅 실습생 모집 (가상)
지원 대상: 재학생(2~4학년)
우대 사항: OPIc IM2 이상, SNS 채널 운영 경험
제출 서류: 영문 이력서, 자기소개서
접수 기간: ~ 2026.12.10(목) 17:00
신청: 대학일자리플러스센터 시스템`;

export { build as buildOpportunity };
export type { Seed as OpportunitySeed };
