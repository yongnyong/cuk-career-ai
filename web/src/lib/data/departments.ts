// 가톨릭대학교 학부 학과 목록
// 출처: 가톨릭대학교 홈페이지 입학·교육 > 대학 (https://www.catholic.ac.kr/ko/academics/edu_undergraduate1.do 외)
// 확인 기준일: 2026-11-16. 학과 개편이 있을 수 있으므로 서비스 등록 시 공식 페이지를 다시 확인한다.
// AI전자정보융합대학 소속 구분은 홈페이지 퀵메뉴 기준 추정이며 확인 필요.

export type Campus = "성심" | "성의" | "성신";

export type Field =
  | "humanities"
  | "language"
  | "social"
  | "law_econ"
  | "business"
  | "science"
  | "engineering"
  | "living"
  | "bio"
  | "ict"
  | "arts"
  | "pharmacy"
  | "medicine"
  | "nursing"
  | "theology"
  | "open";

export interface Department {
  id: string;
  name: string;
  college: string;
  campus: Campus;
  field: Field;
}

const d = (id: string, name: string, college: string, field: Field, campus: Campus = "성심"): Department => ({
  id,
  name,
  college,
  campus,
  field,
});

export const DEPARTMENTS: Department[] = [
  // 인문사회계열
  d("kor-lit", "국어국문학과", "인문사회계열", "humanities"),
  d("philosophy", "철학과", "인문사회계열", "humanities"),
  d("korean-history", "국사학과", "인문사회계열", "humanities"),
  d("english", "영어영문학부", "인문사회계열", "language"),
  d("chinese", "중국언어문화학과", "인문사회계열", "language"),
  d("japanese", "일어일본문화학과", "인문사회계열", "language"),
  d("french", "프랑스어문화학과", "인문사회계열", "language"),
  d("korean-culture", "한국어문화학과", "인문사회계열", "language"),
  d("social-welfare", "사회복지학과", "인문사회계열", "social"),
  d("psychology", "심리학과", "인문사회계열", "social"),
  d("sociology", "사회학과", "인문사회계열", "social"),
  d("child", "아동학과", "인문사회계열", "social"),
  d("special-edu", "특수교육과", "인문사회계열", "social"),
  d("intl", "국제학부", "인문사회계열", "law_econ"),
  d("law", "법학과", "인문사회계열", "law_econ"),
  d("economics", "경제학과", "인문사회계열", "law_econ"),
  d("public-admin", "행정학과", "인문사회계열", "law_econ"),
  // 경영대학
  d("business", "경영학과", "경영대학", "business"),
  d("accounting", "회계학과", "경영대학", "business"),
  d("global-business", "글로벌경영학과", "경영대학", "business"),
  // 자연공학계열
  d("chemistry", "화학과", "자연공학계열", "science"),
  d("math", "수학과", "자연공학계열", "science"),
  d("physics", "물리학과", "자연공학계열", "science"),
  d("energy-env", "에너지환경공학과", "자연공학계열", "engineering"),
  d("space-design", "공간디자인·소비자학과", "자연공학계열", "living"),
  d("clothing", "의류학과", "자연공학계열", "living"),
  d("food-nutrition", "식품영양학과", "자연공학계열", "living"),
  // 바이오헬스융합대학
  d("biotech", "생명공학과", "바이오헬스융합대학", "bio"),
  d("biomed-chem", "바이오메디컬화학공학과", "바이오헬스융합대학", "bio"),
  d("biologics", "바이오로직스공학부", "바이오헬스융합대학", "bio"),
  d("ai-biomed", "AI의공학과", "바이오헬스융합대학", "bio"),
  d("biomed-science", "의생명과학과", "바이오헬스융합대학", "bio"),
  d("biomed-sw", "바이오메디컬소프트웨어학과", "바이오헬스융합대학", "bio"),
  // AI전자정보융합대학
  d("ai", "인공지능학과", "AI전자정보융합대학", "ict"),
  d("data-science", "데이터사이언스학과", "AI전자정보융합대학", "ict"),
  d("cs", "컴퓨터정보공학부", "AI전자정보융합대학", "ict"),
  d("ice", "정보통신전자공학부", "AI전자정보융합대학", "ict"),
  d("media-tech", "미디어기술콘텐츠학과", "AI전자정보융합대학", "ict"),
  // 예체능계열
  d("music", "음악과", "예체능계열", "arts"),
  d("vocal", "성악과", "예체능계열", "arts"),
  d("art-media", "예술미디어융합학과", "예체능계열", "arts"),
  // 약학대학
  d("pharmacy", "약학과", "약학대학", "pharmacy"),
  // 학부대학·융합
  d("free-major", "자유전공학부", "학부대학", "open"),
  d("div-humsoc", "인문사회계열(광역)", "학부대학", "open"),
  d("div-scieng", "자연공학계열(광역)", "학부대학", "open"),
  d("convergence", "융합전공학부", "융합전공학부", "open"),
  // 성의교정
  d("medicine", "의예과·의학과", "의과대학", "medicine", "성의"),
  d("nursing", "간호학과", "간호대학", "nursing", "성의"),
  // 성신교정
  d("theology", "신학과", "신학대학", "theology", "성신"),
];

export const COLLEGES = Array.from(new Set(DEPARTMENTS.map((x) => x.college)));

export const DEPARTMENT_SOURCE = {
  label: "가톨릭대학교 홈페이지 입학·교육 > 대학",
  url: "https://www.catholic.ac.kr/ko/academics/edu_undergraduate1.do",
  checkedAt: "2026-11-16",
};

export function getDepartment(id: string) {
  return DEPARTMENTS.find((x) => x.id === id);
}
