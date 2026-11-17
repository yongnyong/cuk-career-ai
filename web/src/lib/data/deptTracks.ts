// 학과별 테크(진로 갈래)와 고유 스킬. 근거: 각 학과 홈페이지의 취업 및 진로·취득 자격증·전공로드맵 페이지(2026-11-17 확인).
// 여기에는 학과 페이지에 적힌 항목만 넣는다. 조사 방법과 전체 학과 설계안은 docs/DEPT_TECH_TREES.md.
import type { Job, Skill } from "../types";

type Node = Job["nodes"][number];
const n = (skill: string, required = false, prereq?: string[]): Node => ({ skill, required, prereq });

const PAGES = {
  psy: "https://psychology.catholic.ac.kr/psychology/info/",
  env: "https://envi.catholic.ac.kr/envi/info/",
  clo: "https://clothing.catholic.ac.kr/clothing/info/",
  ice: "https://ice.catholic.ac.kr/ice/info/",
  acc: "https://accounting.catholic.ac.kr/accounting/info/",
  sp: "https://sped.catholic.ac.kr/sped/info/",
  his: "https://koreanhistory.catholic.ac.kr/koreanhistory/info/",
  sw: "https://socialwelfare.catholic.ac.kr/socialwelfare/info/",
};
const ROADMAP = (site: keyof typeof PAGES) => PAGES[site].replace("/info/", "/course/roadmap.do");

// 학과 페이지에 근거가 있는 스킬
const d = (id: string, name: string, kind: Skill["kind"], srcUrl: string): Skill => ({
  id,
  name,
  kind,
  verifiable: kind === "자격증",
  from: "학과",
  srcUrl,
});
const track = (id: string, name: string, summary: string, dept: string, srcUrl: string, nodes: Node[], base?: string): Job => ({
  id,
  name,
  summary,
  fields: [],
  departments: [dept],
  base,
  srcUrl,
  nodes,
});

const psyQ = PAGES.psy + "qualifications.do";
const envQ = PAGES.env + "qualification.do";
const cloQ = PAGES.clo + "qualifications.do";
const cloC = PAGES.clo + "career.do";
const iceQ = PAGES.ice + "license.do";
const iceC = PAGES.ice + "career001.do";
const accQ = PAGES.acc + "qualification.do";
const spQ = PAGES.sp + "qualification.do";
const spC = PAGES.sp + "career.do";
const hisC = PAGES.his + "career.do";
const swC = PAGES.sw + "career001.do";

export const DEPT_SKILLS: Skill[] = [
  // 심리학과
  d("PSY-STAT", "심리통계·연구법", "교육", ROADMAP("psy")),
  d("PSY-TEST", "심리검사·평가 실습", "교육", ROADMAP("psy")),
  d("PSY-INTERVIEW", "상담면접 실습", "경험", ROADMAP("psy")),
  d("PSY-COMM", "지역사회상담 사례실습", "경험", ROADMAP("psy")),
  d("PSY-PLAY", "놀이치료 실습·슈퍼비전", "경험", ROADMAP("psy")),
  d("PSY-HRD", "인적자원개발 실습", "교육", ROADMAP("psy")),
  d("PSY-CRIME", "범죄심리학 수강", "교육", ROADMAP("psy")),
  d("PSY-C-YOUTH", "청소년상담사 3급", "자격증", psyQ),
  d("PSY-C-COUNSEL", "상담심리사 2급(학회)", "자격증", psyQ),
  d("PSY-C-JOB", "직업상담사", "자격증", psyQ),
  d("PSY-C-CLIN", "임상심리사 2급", "자격증", psyQ),
  d("PSY-C-MH", "정신건강임상심리사 2급", "자격증", psyQ),
  d("PSY-C-DEV", "발달심리사 2급(학회)", "자격증", psyQ),
  d("PSY-C-PLAY", "놀이심리재활사", "자격증", psyQ),
  d("PSY-C-ORG", "인사조직심리사(학회)", "자격증", psyQ),
  d("PSY-C-CRIME", "범죄심리사 2급(학회)", "자격증", psyQ),
  d("PSY-GRAD", "대학원 진학(1급·전문가 자격은 석사 이상)", "경험", psyQ),
  // 에너지환경공학과
  d("ENV-AIR", "대기오염 제어·방지 실습", "교육", ROADMAP("env")),
  d("ENV-WATER", "수질·폐수처리 공학", "교육", ROADMAP("env")),
  d("ENV-WASTE", "에너지·자원순환 공학", "교육", ROADMAP("env")),
  d("ENV-RENEW", "신재생에너지 공학·실습", "교육", ROADMAP("env")),
  d("ENV-DATA", "환경빅데이터", "교육", ROADMAP("env")),
  d("ENV-C-AIR", "대기환경기사 (학과 지정 중요)", "자격증", envQ),
  d("ENV-C-WATER", "수질환경기사 (학과 지정 중요)", "자격증", envQ),
  d("ENV-C-SAFE", "산업안전기사 (학과 지정 중요)", "자격증", envQ),
  d("ENV-C-WASTE", "폐기물처리기사", "자격증", envQ),
  d("ENV-C-SOIL", "토양환경기사", "자격증", envQ),
  d("ENV-C-GHG", "온실가스관리기사", "자격증", envQ),
  d("ENV-C-MEAS", "환경측정분석사", "자격증", envQ),
  d("ENV-C-RENEW", "신재생에너지발전설비기사", "자격증", envQ),
  d("ENV-C-ENERGY", "에너지관리기사", "자격증", envQ),
  d("ENV-C-CHE", "화공기사", "자격증", envQ),
  d("ENV-C-CHEM", "화학분석기사", "자격증", envQ),
  // 의류학과
  d("CLO-ILLUST", "패션일러스트레이션", "교육", ROADMAP("clo")),
  d("CLO-PATTERN", "의복 제작·패턴 CAD", "교육", ROADMAP("clo")),
  d("CLO-FABRIC", "의류소재 분석", "교육", ROADMAP("clo")),
  d("CLO-3D", "3D CLO 가상의류", "교육", cloQ),
  d("CLO-BIGDATA", "패션 빅데이터·트렌드 분석", "교육", ROADMAP("clo")),
  d("CLO-SHOW", "패션쇼·패션화보", "경험", cloC),
  d("CLO-CONTEST", "패션상품기획콘테스트·공모전", "경험", cloC),
  d("CLO-FIELD", "현장실습·패션매장 실무", "경험", cloC),
  d("CLO-C-GTQ", "GTQ(Photoshop)·GTQi(Illustrator)", "자격증", cloQ),
  d("CLO-C-COLOR", "컬러리스트산업기사", "자격증", cloQ),
  d("CLO-C-CG", "컴퓨터그래픽스운용기능사", "자격증", cloQ),
  d("CLO-C-TECH", "의류기사", "자격증", cloC),
  d("CLO-C-MD", "패션머천다이징산업기사", "자격증", cloQ),
  d("CLO-C-DIST", "유통관리사", "자격증", cloQ),
  d("CLO-C-GA", "Google Analytics 자격", "자격증", cloQ),
  d("CLO-C-TRADE", "패션의류 무역 마스터과정", "교육", cloQ),
  // 정보통신전자공학부
  d("ICE-PROG", "자료구조·프로그래밍응용", "교육", iceC),
  d("ICE-LOGIC", "논리회로·디지털 설계 실험", "교육", iceC),
  d("ICE-SIGNAL", "신호 및 시스템", "교육", iceC),
  d("ICE-CRYPTO", "정보암호화", "교육", iceC),
  d("ICE-SEMI", "반도체 소자·공정", "교육", iceC),
  d("ICE-C-COMM", "정보통신기사", "자격증", iceQ),
  d("ICE-C-RADIO", "무선설비기사", "자격증", iceQ),
  d("ICE-C-SEMI", "반도체설계기사", "자격증", iceQ),
  d("ICE-C-ELECTRIC", "전기기사", "자격증", iceQ),
  d("ICE-C-CCNA", "CCNA", "자격증", iceQ),
  // 회계학과
  d("ACC-FIN", "재무회계(중급회계)", "교육", ROADMAP("acc")),
  d("ACC-COST", "원가·관리회계", "교육", ROADMAP("acc")),
  d("ACC-TAX", "세무회계(소득세·법인세)", "교육", ROADMAP("acc")),
  d("ACC-AUDIT", "회계감사", "교육", ROADMAP("acc")),
  d("ACC-IT", "IT 활용 회계(ERP)", "교육", ROADMAP("acc")),
  d("ACC-HYUN", "고시반 '현양제' 참여", "경험", accQ),
  d("ACC-C-CPA", "공인회계사", "자격증", accQ),
  d("ACC-C-CTA", "세무사", "자격증", accQ),
  // 특수교육과
  d("SP-TYPES", "장애 유형별 교육", "교육", ROADMAP("sp")),
  d("SP-TEACH", "특수교육 실습", "경험", ROADMAP("sp")),
  d("SP-COUNSEL", "재활상담·사례관리", "교육", spQ),
  d("SP-ASSESS", "직업평가", "교육", spQ),
  d("SP-PRACT", "재활실습 150시간", "경험", spQ),
  d("SP-C-REHAB", "장애인재활상담사", "자격증", spQ),
  d("SP-C-EVAL", "직업능력평가사(민간)", "자격증", spC),
  // 국사학과
  d("HIS-SOURCE", "사료 읽기(한문 강독)", "교육", hisC),
  d("HIS-ARCHIVE", "기록관리학의 이해", "교육", hisC),
  d("HIS-HERITAGE", "한국의 문화유산·예술사", "교육", hisC),
  d("HIS-CONTENT", "역사콘텐츠 캡스톤디자인", "프로젝트", hisC),
  d("HIS-CONTEST", "역사콘텐츠공모전", "경험", hisC),
  d("HIS-TRIP", "답사준비위원회·학술제", "경험", hisC),
  d("HIS-C-HANJA", "한자능력검정", "자격증", hisC),
  // 사회복지학과
  d("SW-SKILL", "사회복지 실천기술", "교육", ROADMAP("sw")),
  d("SW-PRACT", "사회복지현장실습 1·2", "경험", ROADMAP("sw")),
  d("SW-RESEARCH", "사회복지조사·자료분석", "교육", ROADMAP("sw")),
  d("SW-PROGRAM", "프로그램 개발과 평가", "교육", ROADMAP("sw")),
  d("SW-C-1", "사회복지사 1급", "자격증", swC),
  d("SW-C-YOUTH", "청소년지도사", "자격증", swC),
  d("SW-GRAD", "대학원 진학", "경험", swC),
];

const psyC = PAGES.psy + "career.do";
const envC = PAGES.env + "career.do";
const accC = PAGES.acc + "roadmap.do";

export const DEPT_JOBS: Job[] = [
  // 심리학과 — 학과 자격증 페이지의 분야 구분
  track("psy-counsel", "상담심리", "상담기관·학교에서 내담자를 만난다", "psychology", psyC, [
    n("PSY-STAT", true), n("PSY-INTERVIEW", true, ["PSY-STAT"]), n("PSY-COMM", false, ["PSY-INTERVIEW"]),
    n("PSY-C-YOUTH", false, ["PSY-INTERVIEW"]), n("PSY-C-COUNSEL", false, ["PSY-COMM"]), n("PSY-C-JOB"), n("PSY-GRAD", false, ["PSY-C-COUNSEL"]),
  ], "welfare"),
  track("psy-clinical", "임상심리", "병원·정신건강 기관에서 심리평가를 한다", "psychology", psyC, [
    n("PSY-STAT", true), n("PSY-TEST", true, ["PSY-STAT"]), n("PSY-C-CLIN", true, ["PSY-TEST"]),
    n("PSY-C-MH", false, ["PSY-C-CLIN"]), n("PSY-GRAD", false, ["PSY-C-CLIN"]),
  ], "welfare"),
  track("psy-develop", "발달·놀이치료", "아동·청소년의 발달을 평가하고 지원한다", "psychology", psyC, [
    n("PSY-STAT", true), n("PSY-TEST", true, ["PSY-STAT"]), n("PSY-PLAY", false, ["PSY-TEST"]),
    n("PSY-C-PLAY", false, ["PSY-PLAY"]), n("PSY-C-DEV"),
  ], "welfare"),
  track("psy-org", "산업·조직(인사)", "기업에서 채용·교육·조직문화를 다룬다", "psychology", psyC, [
    n("PSY-STAT", true), n("PSY-HRD", true), n("PSY-TEST"), n("PSY-C-ORG", false, ["PSY-HRD"]), n("PSY-C-JOB"), n("SK-TOEIC"),
  ]),
  track("psy-crime", "범죄·교정", "보호직·교정직, 경찰 등에서 일한다", "psychology", psyC, [
    n("PSY-STAT", true), n("PSY-CRIME", true), n("PSY-C-CRIME", false, ["PSY-CRIME"]),
  ], "public-sector"),

  // 에너지환경공학과 — 학과가 "중요"로 지정한 기사 중심
  track("env-air", "대기환경", "대기오염을 측정하고 방지시설을 설계한다", "energy-env", envC, [
    n("ENV-AIR", true), n("SK-LAB-ANAL"), n("ENV-C-AIR", true, ["ENV-AIR"]), n("ENV-C-GHG", false, ["ENV-C-AIR"]), n("ENV-C-MEAS", false, ["SK-LAB-ANAL"]),
  ], "env-engineer"),
  track("env-water", "수질·자원순환", "수질오염과 폐기물을 처리한다", "energy-env", envC, [
    n("ENV-WATER", true), n("ENV-WASTE"), n("ENV-C-WATER", true, ["ENV-WATER"]), n("ENV-C-WASTE", false, ["ENV-WASTE"]), n("ENV-C-SOIL"),
  ], "env-engineer"),
  track("env-energy", "에너지·신재생", "신재생에너지 설비와 에너지 관리를 맡는다", "energy-env", envC, [
    n("ENV-RENEW", true), n("ENV-C-RENEW", false, ["ENV-RENEW"]), n("ENV-C-ENERGY"), n("ENV-DATA"),
  ], "env-engineer"),
  track("env-public", "환경직 공무원·공기업", "환경부·지자체·환경공단 등에서 일한다", "energy-env", envC, [
    n("ENV-WATER", true), n("ENV-AIR", true), n("ENV-C-WATER", false, ["ENV-WATER"]), n("ENV-C-AIR", false, ["ENV-AIR"]), n("ENV-C-SAFE"),
  ], "public-sector"),
  track("env-safety", "화공·안전", "공정 안전과 화학 분석을 맡는다", "energy-env", envC, [
    n("SK-LAB-ANAL", true), n("ENV-C-SAFE", true), n("ENV-C-CHEM", false, ["SK-LAB-ANAL"]), n("ENV-C-CHE"),
  ], "env-engineer"),

  // 의류학과 — 학과 진로 로드맵 표의 갈래
  track("clo-design", "패션 디자인", "스타일·소재·그래픽 디자이너", "clothing", cloC, [
    n("CLO-ILLUST", true), n("CLO-PATTERN", true, ["CLO-ILLUST"]), n("CLO-C-GTQ"), n("CLO-C-COLOR"), n("CLO-SHOW", false, ["CLO-PATTERN"]), n("SK-PORT"),
  ], "designer"),
  track("clo-tech", "패션 테크·소재", "3D·테크니컬 디자이너, 소재분석가", "clothing", cloC, [
    n("CLO-PATTERN", true), n("CLO-FABRIC"), n("CLO-3D", true, ["CLO-PATTERN"]), n("CLO-C-CG"), n("CLO-C-TECH", false, ["CLO-FABRIC"]),
  ], "designer"),
  track("clo-md", "머천다이징·유통", "상품기획, 바잉, 온라인 MD, 영업관리", "clothing", cloC, [
    n("CLO-BIGDATA", true), n("CLO-CONTEST"), n("CLO-C-MD", false, ["CLO-BIGDATA"]), n("CLO-C-DIST"), n("CLO-FIELD"), n("SK-COMP"),
  ], "marketer"),
  track("clo-marketing", "패션 마케팅", "마케터, 광고, 홍보", "clothing", cloC, [
    n("CLO-BIGDATA", true), n("CLO-C-GA"), n("SK-SNS"), n("CLO-CONTEST"), n("SK-TOEIC"),
  ], "marketer"),
  track("clo-trade", "해외 벤더·무역", "국내외 벤더 영업, R&D", "clothing", cloC, [
    n("SK-TOEIC", true), n("CLO-C-TRADE"), n("CLO-FIELD"), n("SK-OPIC"),
  ], "overseas-sales"),

  // 정보통신전자공학부 — 학과 진로 로드맵 표의 갈래
  track("ice-security", "네트워크·정보보안", "네트워크와 보안 시스템을 다룬다", "ice", iceC, [
    n("ICE-PROG", true), n("ICE-CRYPTO", true, ["ICE-PROG"]), n("ICE-C-CCNA"), n("SK-INFO-PE", false, ["ICE-PROG"]), n("ICE-C-COMM"),
  ], "sw-developer"),
  track("ice-wireless", "무선통신 시스템", "차세대 모바일 통신 시스템을 설계한다", "ice", iceC, [
    n("ICE-SIGNAL", true), n("SK-CIRCUIT"), n("ICE-C-RADIO", false, ["ICE-SIGNAL"]), n("ICE-C-COMM", false, ["ICE-SIGNAL"]),
  ], "electronics"),
  track("ice-semi", "반도체 소자·공정", "반도체 소자와 공정을 다룬다", "ice", iceC, [
    n("SK-CIRCUIT", true), n("ICE-SEMI", true, ["SK-CIRCUIT"]), n("ICE-C-SEMI", false, ["ICE-SEMI"]), n("SK-ELEC-PE"),
  ], "electronics"),
  track("ice-digital", "디지털 시스템 설계", "디지털 회로와 임베디드 시스템을 설계한다", "ice", iceC, [
    n("ICE-LOGIC", true), n("ICE-PROG"), n("SK-EMB", false, ["ICE-LOGIC"]), n("ICE-C-SEMI"), n("SK-ELEC-PE"),
  ], "electronics"),
  track("ice-analog", "아날로그 회로설계", "아날로그·전력 회로를 설계한다", "ice", iceC, [
    n("SK-CIRCUIT", true), n("ICE-SIGNAL"), n("SK-ELEC-PE", false, ["SK-CIRCUIT"]), n("ICE-C-ELECTRIC"),
  ], "electronics"),

  // 회계학과
  track("acc-cpa", "회계법인(공인회계사)", "회계감사·세무자문·경영컨설팅", "accounting", accC, [
    n("ACC-FIN", true), n("ACC-COST", true), n("ACC-TAX"), n("ACC-AUDIT", false, ["ACC-FIN"]), n("ACC-HYUN"), n("ACC-C-CPA", true, ["ACC-FIN", "ACC-COST"]),
  ], "finance"),
  track("acc-tax", "세무법인(세무사)", "세무 신고 대리와 조세 자문", "accounting", accC, [
    n("ACC-FIN", true), n("ACC-TAX", true), n("ACC-HYUN"), n("ACC-C-CTA", true, ["ACC-TAX"]),
  ], "finance"),
  track("acc-corp", "기업 회계·재무", "대기업·중견기업·외국계의 회계·재무 부서", "accounting", accC, [
    n("ACC-FIN", true), n("ACC-COST"), n("ACC-IT"), n("SK-COMP"), n("SK-TOEIC"),
  ], "finance"),
  track("acc-public", "공공기관·세무직 공무원", "공사·공기업, 세무직 7·9급", "accounting", accC, [
    n("ACC-FIN", true), n("ACC-TAX", true), n("SK-KHIST"),
  ], "public-sector"),

  // 특수교육과 — 학부에서 취득할 수 있다고 밝힌 자격 3가지
  track("sp-teacher", "중등 특수교사", "특수학교·특수학급 교사", "special-edu", spC, [
    n("SP-TYPES", true), n("SP-TEACH", true, ["SP-TYPES"]), n("SK-SPED", true, ["SP-TEACH"]),
  ], "educator"),
  track("sp-rehab", "재활상담사", "장애인의 직업·자립을 돕는 재활 전문가", "special-edu", spC, [
    n("SP-COUNSEL", true), n("SP-PRACT", true, ["SP-COUNSEL"]), n("SP-C-REHAB", true, ["SP-PRACT"]),
  ], "welfare"),
  track("sp-eval", "직업평가사", "장애 진단과 직업 능력을 평가한다", "special-edu", spC, [
    n("SP-ASSESS", true), n("SP-PRACT"), n("SP-C-EVAL", false, ["SP-ASSESS"]), n("SP-C-REHAB"),
  ], "welfare"),

  // 국사학과 — 학과 진로 로드맵 표의 갈래와 필요 자격
  track("his-curator", "학예사", "박물관·미술관에서 유물을 연구하고 전시한다", "korean-history", hisC, [
    n("HIS-SOURCE", true), n("HIS-HERITAGE", true), n("HIS-C-HANJA"), n("HIS-TRIP"),
  ], "arts-planner"),
  track("his-archive", "기록관리사", "공공·민간 기록물을 관리한다", "korean-history", hisC, [
    n("HIS-SOURCE", true), n("HIS-ARCHIVE", true, ["HIS-SOURCE"]), n("HIS-C-HANJA"),
  ], "public-sector"),
  track("his-translate", "고전번역가", "한문 사료를 우리말로 옮긴다", "korean-history", hisC, [
    n("HIS-SOURCE", true), n("HIS-C-HANJA", true, ["HIS-SOURCE"]),
  ]),
  track("his-content", "역사콘텐츠 크리에이터", "역사를 영상·글·전시 콘텐츠로 만든다", "korean-history", hisC, [
    n("HIS-CONTENT", true), n("SK-VIDEO"), n("HIS-CONTEST", false, ["HIS-CONTENT"]), n("HIS-TRIP"),
  ], "content-planner"),
  track("his-public", "공무원", "한국사·한자 능력을 살려 공직에 진출한다", "korean-history", hisC, [
    n("SK-KHIST", true), n("HIS-C-HANJA"), n("SK-COMP"), n("SK-TOEIC"),
  ], "public-sector"),

  // 사회복지학과 — 학과가 밝힌 주요 분야
  track("sw-youth", "청소년복지", "청소년 기관의 사회복지사·청소년지도사", "social-welfare", swC, [
    n("SW-SKILL", true), n("SW-PRACT", true, ["SW-SKILL"]), n("SK-SW-CERT", true, ["SW-PRACT"]), n("SW-C-YOUTH"), n("SW-C-1", false, ["SK-SW-CERT"]),
  ], "welfare"),
  track("sw-facility", "장애인·노인복지", "복지관·요양시설의 사회복지사", "social-welfare", swC, [
    n("SW-SKILL", true), n("SW-PRACT", true, ["SW-SKILL"]), n("SK-SW-CERT", true, ["SW-PRACT"]), n("SW-PROGRAM"), n("SW-C-1", false, ["SK-SW-CERT"]),
  ], "welfare"),
  track("sw-medical", "의료·정신건강 사회복지", "병원·정신건강 기관의 사회복지사", "social-welfare", swC, [
    n("SW-SKILL", true), n("SW-PRACT", true, ["SW-SKILL"]), n("SK-SW-CERT", true, ["SW-PRACT"]), n("SW-C-1", true, ["SK-SW-CERT"]),
  ], "welfare"),
  track("sw-public", "사회복지 공무원·공기업", "지자체·공단의 복지 행정", "social-welfare", swC, [
    n("SK-SW-CERT", true), n("SW-RESEARCH"), n("SW-C-1", false, ["SK-SW-CERT"]),
  ], "public-sector"),
  track("sw-research", "연구원", "대학원 진학 후 국책·지자체 연구기관", "social-welfare", swC, [
    n("SW-RESEARCH", true), n("SW-PROGRAM"), n("SW-GRAD", false, ["SW-RESEARCH"]),
  ]),
];
