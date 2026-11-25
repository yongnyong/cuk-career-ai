import type { TreeNode } from "./engine";
import type { CustomNode, CustomTree, SkillKind } from "./types";
import type { WeightTier } from "./treeRadial";
import { outfitFor, type Outfit } from "./hayang";

// 학생이 스킬트리에 직접 더하는 노드(예: '희망 기업 직무 인터뷰'). 프로필에 직무별로 저장된다.
export const KINDS: SkillKind[] = ["역량", "자격증", "어학", "교육", "프로젝트", "경험"];
export const LIMITS = { nodes: 40, name: 40, note: 300 } as const;

// 직업군마다 학생들이 흔히 하는 준비. 추가 창에서 눌러 바로 채운다(트리에 이미 있는 이름은 빼고 보여 준다)
type Idea = { name: string; kind: SkillKind };
const idea = (name: string, kind: SkillKind): Idea => ({ name, kind });
const IDEAS: Record<Outfit, Idea[]> = {
  medical: [idea("병원 실습 일지 정리", "경험"), idea("BLS 심폐소생술 교육 이수", "교육"), idea("국가고시 기출 1회독", "역량"), idea("의료봉사 참여", "경험")],
  dev: [idea("깃허브 포트폴리오 정리", "프로젝트"), idea("코딩테스트 50문제 풀기", "역량"), idea("정보처리기사", "자격증"), idea("해커톤 참가", "경험")],
  research: [idea("학부연구생 지원", "경험"), idea("관심 분야 논문 요약 발표", "역량"), idea("학회 포스터 발표", "경험"), idea("실험 노트 정리", "프로젝트")],
  engineer: [idea("캡스톤 디자인 완성", "프로젝트"), idea("기사 자격증 필기", "자격증"), idea("현장실습", "경험"), idea("CAD 실무 교육", "교육")],
  business: [idea("컴퓨터활용능력 1급", "자격증"), idea("토익 800점", "어학"), idea("공모전 기획서 제출", "프로젝트"), idea("현직자 직무 인터뷰", "경험")],
  global: [idea("토익스피킹 IH", "어학"), idea("교환학생 지원", "경험"), idea("해외 인턴십", "경험"), idea("무역영어 자격증", "자격증")],
  public: [idea("한국사능력검정 1급", "자격증"), idea("공공기관 체험형 인턴", "경험"), idea("NCS 문제집 1회독", "역량"), idea("토익 700점", "어학")],
  law: [idea("모의재판 참가", "경험"), idea("법률 상담 봉사", "경험"), idea("판례 스터디", "역량"), idea("법원 견학·방청", "경험")],
  care: [idea("상담센터 자원봉사", "경험"), idea("청소년상담사 3급", "자격증"), idea("상담 사례 스터디", "역량"), idea("복지관 현장실습", "경험")],
  edu: [idea("교육봉사 50시간", "경험"), idea("수업 지도안 작성", "프로젝트"), idea("한국사능력검정 1급", "자격증"), idea("멘토링 프로그램 참여", "경험")],
  creative: [idea("포트폴리오 사이트 만들기", "프로젝트"), idea("GTQ 포토샵 1급", "자격증"), idea("공모전 출품", "경험"), idea("SNS 콘텐츠 30개 발행", "프로젝트")],
  ministry: [idea("봉사활동 100시간", "경험"), idea("비영리단체 인턴", "경험"), idea("공동체 행사 기획", "프로젝트"), idea("사회복지사 2급", "자격증")],
  startup: [idea("고객 인터뷰 10명", "경험"), idea("사업계획서 초안", "프로젝트"), idea("창업 동아리 참여", "경험"), idea("시제품(MVP) 만들기", "프로젝트")],
};
export function nodeIdeas(jobId: string, startup = false, taken: readonly string[] = []): Idea[] {
  return IDEAS[outfitFor(jobId, startup)].filter((i) => !taken.includes(i.name));
}

const newId = () => (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`).slice(0, 12);

export function newNode(name = "새 노드"): CustomNode {
  // 카탈로그 노드 id와 겹치지 않게 접두어를 붙인다
  return { id: `my-${newId()}`, name, kind: "역량", weight: 2, prereq: [], done: false };
}

/** parent를 child의 선수로 넣으면 순환이 생기는지 */
export function wouldCycle(nodes: CustomNode[], child: string, parent: string): boolean {
  if (child === parent) return true;
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const stack = [parent];
  const seen = new Set<string>();
  while (stack.length) {
    const id = stack.pop()!;
    if (id === child) return true;
    if (seen.has(id)) continue;
    seen.add(id);
    stack.push(...(byId.get(id)?.prereq ?? []));
  }
  return false;
}

export function removeNode(nodes: CustomNode[], id: string): CustomNode[] {
  return nodes.filter((n) => n.id !== id).map((n) => ({ ...n, prereq: n.prereq.filter((q) => q !== id) }));
}

/** 스킬트리에 내 노드를 합친다. 선수 노드는 기존 노드나 다른 내 노드이고, 깊이는 선수 관계의 가장 긴 경로 */
export function withMyNodes(tree: TreeNode[], mine: CustomNode[] = []): TreeNode[] {
  if (!mine.length) return tree;
  const base = new Map(tree.map((n) => [n.skill, n]));
  const byId = new Map(mine.map((n) => [n.id, n]));
  const exists = (id: string) => base.has(id) || byId.has(id);
  const done = (id: string) => (base.has(id) ? base.get(id)!.state !== "none" : !!byId.get(id)?.done);
  const depth = new Map<string, number>();
  const depthOf = (id: string, trail = new Set<string>()): number => {
    if (base.has(id)) return base.get(id)!.depth;
    if (depth.has(id)) return depth.get(id)!;
    if (trail.has(id)) return 0; // 저장된 데이터가 꼬였어도 멈추지 않게
    trail.add(id);
    const parents = byId.get(id)!.prereq.filter(exists);
    const d = parents.length ? Math.max(...parents.map((q) => depthOf(q, trail) + 1)) : 0;
    depth.set(id, d);
    return d;
  };
  const added: TreeNode[] = mine.map((n) => {
    const prereq = n.prereq.filter(exists);
    return {
      skill: n.id,
      name: n.name,
      kind: n.kind,
      required: false,
      prereq,
      depth: depthOf(n.id),
      state: n.done ? "self" : "none",
      locked: !n.done && prereq.some((q) => !done(q)),
      opportunities: [],
      sequence: [],
      mine: { weight: n.weight, ...(n.note ? { note: n.note } : {}) },
    };
  });
  return [...tree, ...added].sort((a, b) => a.depth - b.depth);
}

/** 원형 파형·하양이가 그대로 쓰도록 스킬트리 노드 모양으로 바꾼다. 깊이는 선수 관계의 가장 긴 경로 */
export function toTreeNodes(tree: CustomTree): { nodes: TreeNode[]; weights: Map<string, { tier: WeightTier }> } {
  const byId = new Map(tree.nodes.map((n) => [n.id, n]));
  const depth = new Map<string, number>();
  const depthOf = (id: string, trail = new Set<string>()): number => {
    if (depth.has(id)) return depth.get(id)!;
    if (trail.has(id)) return 0; // 저장된 데이터가 꼬였어도 멈추지 않게
    trail.add(id);
    const parents = (byId.get(id)?.prereq ?? []).filter((q) => byId.has(q));
    const d = parents.length ? Math.max(...parents.map((q) => depthOf(q, trail) + 1)) : 0;
    depth.set(id, d);
    return d;
  };
  const nodes: TreeNode[] = tree.nodes.map((n) => {
    const prereq = n.prereq.filter((q) => byId.has(q));
    return {
      skill: n.id,
      name: n.name,
      kind: n.kind,
      required: n.weight === 3,
      prereq,
      depth: depthOf(n.id),
      state: n.done ? ("self" as const) : ("none" as const),
      locked: !n.done && prereq.some((q) => !byId.get(q)!.done),
      opportunities: [],
      sequence: [],
    };
  }).sort((a, b) => a.depth - b.depth);
  return { nodes, weights: new Map(tree.nodes.map((n) => [n.id, { tier: n.weight }])) };
}
