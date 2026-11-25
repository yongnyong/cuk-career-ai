import type { CustomNode, CustomTree, Profile, SkillState } from "../types";

// 명예의 전당: 공개된 이력만으로 정리한 예시 트리. 본인이 작성한 것이 아니며 출처를 함께 보여 준다.
// skill: 학생 트리에서 이 단계에 해당하는 준비 노드(카탈로그 id). 그 사람이 해당 자격을 가졌다는 뜻이 아니다.
export interface FameNode extends Omit<CustomNode, "done"> {
  skill?: string;
  detail: string; // 공개 이력의 해당 내용
}

export interface FameEntry {
  id: string;
  name: string;
  role: string;
  field: string;
  departments: string[]; // 먼저 추천할 학과
  summary: string;
  source: { label: string; url: string };
  nodes: FameNode[];
}

const node = (id: string, name: string, kind: FameNode["kind"], weight: FameNode["weight"], prereq: string[], detail: string, skill?: string): FameNode =>
  ({ id, name, kind, weight, prereq, detail, ...(skill && { skill }) });

export const HALL_OF_FAME: FameEntry[] = [
  {
    id: "yang-jaewon",
    name: "양재원",
    role: "가톨릭대학교 심리학과 교수",
    field: "임상심리학",
    departments: ["psychology"],
    summary: "임상심리 수련과 자격을 거쳐 사회불안·섭식장애의 인지편향을 연구하고, 2015년부터 가톨릭대에서 이상심리·임상심리를 가르친다.",
    source: { label: "가톨릭대학교 심리학과 교수소개", url: "https://psychology.catholic.ac.kr/psychology/faculty/faculty.do" },
    nodes: [
      node("y1", "심리학 학부·석사", "교육", 3, [], "연세대학교 심리학과에서 학부와 석사를 마쳤다.", "PSY-STAT"),
      node("y2", "심리검사·평가 역량", "교육", 2, ["y1"], "임상심리 수련의 기본이 되는 심리평가 역량.", "PSY-TEST"),
      node("y3", "정신병리 지식", "교육", 2, ["y1"], "현재 학부 이상심리학, 대학원 정신병리학을 강의한다.", "PSY-PATHO"),
      node("y4", "병원 임상심리 레지던트", "경험", 3, ["y2", "y3"], "성균관의대 삼성서울병원 정신건강의학과에서 임상심리 레지던트로 일했다.", "PSY-CLIN-PRACT"),
      node("y5", "임상심리전문가(한국심리학회)", "자격증", 3, ["y4"], "한국심리학회 임상심리전문가 자격을 갖고 있다."),
      node("y6", "정신건강임상심리사 1급", "자격증", 2, ["y4"], "보건복지부 정신건강임상심리사 1급 자격을 갖고 있다. 학생 트리의 2급이 첫 단계다.", "PSY-C-MH"),
      node("y7", "심리학 박사(사회불안 인지편향)", "경험", 3, ["y5"], "2010년 연세대학교에서 사회불안의 인지편향을 주제로 박사학위를 받았다.", "PSY-GRAD"),
      node("y8", "대학 강의 경력", "경험", 1, ["y7"], "경일대학교 전임강사, 연세대학교 조교수로 일했다."),
      node("y9", "가톨릭대 심리학과 교수", "경험", 3, ["y8"], "2015년부터 가톨릭대학교 심리학과 교수로 일하고 있다."),
      node("y10", "학회 이사 활동", "경험", 1, ["y9"], "한국임상심리학회와 한국심리학회에서 이사직을 여러 차례 맡았다."),
    ],
  },
  {
    id: "oh-eunyoung",
    name: "오은영",
    role: "정신건강의학과·소아청소년정신과 전문의",
    field: "아동·청소년 정신건강",
    departments: ["psychology", "social-welfare", "child"],
    summary: "의대를 거쳐 정신건강의학과 전문의가 된 뒤 소아청소년 세부 전문의 과정을 마쳤고, 연구·저술·부모 교육으로 아동 정신건강을 대중에게 알려 왔다.",
    source: { label: "텐아시아 인터뷰(2021)", url: "https://www.tenasia.co.kr/article/2021052882634" },
    nodes: [
      node("o1", "의과대학", "교육", 3, [], "연세대학교 의과대학을 나왔다(본인 인터뷰)."),
      node("o2", "정신건강의학과 전문의", "자격증", 3, ["o1"], "정신건강의학과 전문의다."),
      node("o3", "소아청소년정신과 세부 전문의", "자격증", 3, ["o2"], "정신건강의학과 전문의 뒤 소아청소년 세부 전문의 과정을 한 번 더 마쳤다(본인 인터뷰)."),
      node("o4", "발달 정신병리 이해", "교육", 2, ["o1"], "0~18세 아동·청소년의 발달과 정신건강을 다룬다. 심리학과 학생에게는 발달정신병리학이 대응한다.", "PSY-PATHO"),
      node("o5", "아동·부모 상담", "경험", 2, ["o3", "o4"], "아동·청소년과 부모를 상담한다. 학생 트리의 상담면접 실습이 첫 단계다.", "PSY-INTERVIEW"),
      node("o6", "연구·저술·부모 교육", "경험", 2, ["o5"], "연구, 책 집필, 부모 교육을 하는 기관을 운영한다고 밝혔다(본인 인터뷰)."),
      node("o7", "대중 소통", "경험", 1, ["o6"], "방송과 저서로 아동 정신건강과 양육 정보를 알려 왔다."),
    ],
  },
];

/** 원형 파형으로 보여 주는 트리. 내가 이미 한 대응 노드는 완료(초록)로 칠한다 */
export function fameTree(entry: FameEntry, skills: Profile["skills"]): CustomTree {
  return {
    id: entry.id,
    title: entry.name,
    goal: entry.name,
    createdAt: "",
    updatedAt: "",
    nodes: entry.nodes.map(({ skill, ...n }) => ({ ...n, done: !!skill && (skills[skill] ?? "none") !== "none" })),
  };
}

/** 멘토 따라잡기 점수: 학생 트리와 이어지는 단계 중 내가 마친 비율(인증 1.0, 자기 체크 0.6, 중요도 가중) */
export function mentorScore(entry: FameEntry, skills: Record<string, SkillState>) {
  const linked = entry.nodes.filter((n) => n.skill);
  const total = linked.reduce((sum, n) => sum + n.weight, 0);
  const got = linked.reduce((sum, n) => sum + n.weight * (skills[n.skill!] === "verified" ? 1 : skills[n.skill!] === "self" ? 0.6 : 0), 0);
  return { score: total ? Math.round((got / total) * 100) : 0, linked: linked.length, done: linked.filter((n) => (skills[n.skill!] ?? "none") !== "none").length };
}
