import { isOpen, type TreeNode } from "./engine";
import type { Opportunity } from "./types";
import { JOBS, jobById } from "./data/catalog";

export type WeightTier = 1 | 2 | 3;
type Point = { x: number; y: number };

// 추천 퀘스트(selectRecommendedQuest)와 같은 근거 순위: 공고 필수 > 우대 > 학습 활동 > 학과 자료
const BASIS_WEIGHT = { required: 6, preferred: 5, activity: 2, school: 1 } as const;

const parentsOf = (node: TreeNode) => [...node.prereq, ...(node.sequence ?? [])];

/** 노드 중요도. 트랙 필수, 공고 근거, 열린 공고 수, 이 노드를 선수로 쓰는 노드 수만 쓴다. 근거 없는 난이도는 넣지 않는다. */
export function nodeWeights(tree: TreeNode[]): Map<string, { score: number; tier: WeightTier }> {
  const dependents = new Map<string, number>();
  for (const node of tree) if (!node.mine) for (const parent of parentsOf(node)) dependents.set(parent, (dependents.get(parent) ?? 0) + 1);
  const scores = tree.filter((node) => !node.mine).map((node) => {
    const refs = new Map<string, number>();
    for (const signal of node.evidence ?? []) {
      refs.set(signal.reference.id, Math.max(refs.get(signal.reference.id) ?? 0, BASIS_WEIGHT[signal.basis]));
    }
    const evidence = Math.min([...refs.values()].reduce((sum, value) => sum + value, 0), 12);
    const opportunities = new Set(node.opportunities.filter((o) => !o.isVirtual).map((o) => o.id)).size;
    const score = (node.required ? 6 : 0) + evidence + 2 * Math.min(opportunities, 3) + 2 * Math.min(dependents.get(node.skill) ?? 0, 3);
    return [node.skill, score] as const;
  });
  const ranked = scores.map(([, score]) => score).filter((score) => score > 0).sort((a, b) => b - a);
  const flat = ranked.length === 0 || ranked[0] === Math.min(...scores.map(([, score]) => score));
  // 상위 약 25%는 대, 다음 35%는 중. 같은 점수는 같은 크기로 묶는다
  const bigCut = ranked[Math.max(0, Math.round(tree.length * 0.25) - 1)] ?? Infinity;
  const midCut = ranked[Math.min(ranked.length, Math.round(tree.length * 0.6)) - 1] ?? Infinity;
  return new Map([
    ...scores.map(([skill, score]) => [skill, {
      score,
      tier: (flat ? 2 : score > 0 && score >= bigCut ? 3 : score > 0 && score >= midCut ? 2 : 1) as WeightTier,
    }] as const),
    ...tree.filter((node) => node.mine).map((node) => [node.skill, { score: 0, tier: node.mine!.weight as WeightTier }] as const),
  ]);
}

const KIND_ORDER = ["역량", "자격증", "어학", "교육", "프로젝트", "경험"];
const kindRank = (kind: string) => (KIND_ORDER.indexOf(kind) + 1 || KIND_ORDER.length + 1);
// 방사형 전체 보기: 노드는 원형 아이콘 + 아래 이름(최대 112×86px). 캔버스가 가로로 넓어 고리를 가로로 조금 늘린다.
// 간격 125는 어느 방향에서도 이웃 노드가 겹치지 않는 최소값(약 122)에 여유를 둔 값이다
export const RADIAL_RX = 1.3;
export const RADIAL_RY = 1;
const R_FIRST = 110;
const R_GAP = 125;
const R_SEP = 125; // 같은 고리에서 이웃 노드 사이 최소 간격(정규화 반지름 기준 호 길이)
// 고리는 준비 단계 5개(progressionStage)와 맞춘다. 그보다 깊은 후속 단계는 바깥 고리에 함께 둔다
export const ringOf = (depth: number) => Math.min(depth, 4);

export interface RadialLayout {
  positions: Map<string, Point>; // 노드 중심 좌표, 목표 직무가 (0,0)
  rings: { stage: number; r: number }[]; // 타원 반지름은 r × RADIAL_RX, r × RADIAL_RY
  sectors: { kind: string; start: number; end: number; count: number }[];
  outer: number;
}

/** 원하는 각도(오름차순)를 지키되 이웃끼리 sep 이상 떨어지게 민다 */
function spread(targets: number[], sep: number): number[] {
  const n = targets.length;
  if (n === 0) return [];
  const even = () => targets.map((_, index) => targets[0] + (2 * Math.PI * index) / n);
  if (n * sep >= 2 * Math.PI) return even();
  const pushed = [...targets];
  for (let i = 1; i < n; i++) pushed[i] = Math.max(pushed[i], pushed[i - 1] + sep);
  const shift = (pushed.reduce((sum, a) => sum + a, 0) - targets.reduce((sum, a) => sum + a, 0)) / n;
  const out = pushed.map((a) => a - shift);
  return out[n - 1] - out[0] > 2 * Math.PI - sep ? even() : out;
}

/** 가운데 목표 직무, 고리 = 준비 단계(안쪽이 먼저), 방향 = 노드 분류 */
export function layoutRadial(tree: TreeNode[]): RadialLayout {
  const positions = new Map<string, Point>();
  const angles = new Map<string, number>();
  const kinds = [...new Set(tree.map((node) => node.kind))].sort((a, b) => kindRank(a) - kindRank(b));
  let cursor = -Math.PI / 2;
  const sectors = kinds.map((kind) => {
    const count = tree.filter((node) => node.kind === kind).length;
    const start = cursor;
    cursor += (2 * Math.PI * count) / Math.max(tree.length, 1);
    return { kind, start, end: cursor, count };
  });
  const stages = [...new Set(tree.map((node) => ringOf(node.depth)))].sort((a, b) => a - b);
  const rings: RadialLayout["rings"] = [];
  for (const stage of stages) {
    const ring = tree.filter((node) => ringOf(node.depth) === stage);
    const items = sectors.flatMap((sector) => {
      const center = (node: TreeNode) => {
        const known = parentsOf(node).flatMap((id) => angles.has(id) ? [angles.get(id)!] : []);
        return known.length ? known.reduce((sum, angle) => sum + angle, 0) / known.length : (sector.start + sector.end) / 2;
      };
      const nodes = ring.filter((node) => node.kind === sector.kind).sort((a, b) => center(a) - center(b) || a.depth - b.depth);
      return nodes.map((node, index) => ({ node, target: sector.start + ((sector.end - sector.start) * (index + 0.5)) / nodes.length }));
    }).sort((a, b) => a.target - b.target);
    // 간격은 호가 아니라 현(직선 거리)으로 잰다. 작은 고리에서는 호 길이가 같아도 실제 거리가 더 짧다
    const fit = items.length > 1 ? R_SEP / (2 * Math.sin(Math.PI / items.length)) : 0;
    const r = Math.max(rings.length ? rings[rings.length - 1].r + R_GAP : R_FIRST, fit);
    rings.push({ stage, r });
    spread(items.map((item) => item.target), 2 * Math.asin(Math.min(1, R_SEP / (2 * r)))).forEach((angle, index) => {
      const { node } = items[index];
      angles.set(node.skill, angle);
      positions.set(node.skill, { x: Math.cos(angle) * r * RADIAL_RX, y: Math.sin(angle) * r * RADIAL_RY });
    });
  }
  return { positions, rings, sectors, outer: rings[rings.length - 1]?.r ?? R_FIRST };
}

// 자세히 보기: 노드가 적어서 원래 크기 카드로 원형 배치한다
const SLOT = 240;
const RING_GAP = 170;
const FIRST_RING = 250;

/** 이 노드를 선수로 갖는 노드들(재귀). 고리 순서대로 돌려준다 */
export function descendantRings(tree: TreeNode[], skill: string, maxRings = 2): TreeNode[][] {
  const seen = new Set([skill]);
  const rings: TreeNode[][] = [];
  let frontier = [skill];
  while (frontier.length && rings.length < maxRings) {
    const next = tree.filter((node) => !seen.has(node.skill) && parentsOf(node).some((parent) => frontier.includes(parent)));
    next.forEach((node) => seen.add(node.skill));
    if (next.length) rings.push(next);
    frontier = next.map((node) => node.skill);
  }
  return rings;
}

export type Advantage = {
  id: string;
  label: string;
  detail?: string;
  count: number;
  orgs: string[];
};

/**
 * "이 노드가 유리한 곳". 노드별로 직접 연결된 공고가 적어서 세 가지를 합친다.
 * 1) 이 노드가 트랙에 들어 있는 직무(카탈로그)와 그 직무로 분류된 열린 공고의 기관
 * 2) 이 노드와 이어지는 노드에서 열린 공고
 * 3) 이 역량을 필수·우대로 적은 공고 근거(지난 공고 포함)
 */
export function advantagesOf(tree: TreeNode[], skill: string, opportunities: Opportunity[] = [], now = new Date(), targetJob?: string): Advantage[] {
  const node = tree.find((n) => n.skill === skill);
  if (!node) return [];
  const groups = new Map<string, { label: string; detail?: string; ids: Set<string>; orgs: Set<string>; rank: number }>();
  const group = (key: string, label: string, rank: number, detail?: string) => {
    const found = groups.get(key) ?? { label, detail, ids: new Set<string>(), orgs: new Set<string>(), rank };
    groups.set(key, found);
    return found;
  };
  const add = (target: ReturnType<typeof group>, o: { id: string; org?: string }) => {
    target.ids.add(o.id);
    if (o.org?.trim()) target.orgs.add(o.org.trim());
  };
  const open = opportunities.filter((o) => !o.isVirtual && isOpen(o, now));
  for (const job of JOBS.filter((j) => j.nodes.some((n) => n.skill === skill))) {
    const target = group(`job:${job.id}`, job.name, job.id === targetJob ? 1 : 2, job.id === targetJob ? "내 목표 직무" : undefined);
    for (const o of open) if (o.jobs.includes(job.id) || (job.base && o.jobs.includes(job.base))) add(target, o);
  }
  const scope = [node, ...descendantRings(tree, skill).flat()];
  for (const o of new Map(scope.flatMap((n) => n.opportunities).filter((o) => !o.isVirtual).map((o) => [o.id, o])).values()) {
    const jobs = o.jobs.filter((id) => jobById(id));
    if (jobs.length) for (const id of jobs) add(group(`job:${id}`, jobById(id)!.name, id === targetJob ? 1 : 2, id === targetJob ? "내 목표 직무" : undefined), o);
    else add(group(`type:${o.type}`, `${o.type} 공고`, 0, "이 노드에서 열린 공고"), o);
  }
  for (const signal of node.evidence ?? []) {
    if (signal.basis === "required" || signal.basis === "preferred") {
      add(group("evidence", "이 역량을 요구한 공고", 0, signal.reference.historical ? "지난 공고 포함" : undefined), { id: signal.reference.id, org: signal.reference.organization });
    }
  }
  return [...groups.entries()]
    .map(([id, g]) => ({ id, label: g.label, detail: g.detail, count: g.ids.size, orgs: [...g.orgs].slice(0, 3), rank: g.rank }))
    .filter((a) => a.rank > 0 || a.count > 0)
    .sort((a, b) => Number(b.count > 0) - Number(a.count > 0) || a.rank - b.rank || b.count - a.count)
    .slice(0, 6)
    .map(({ id, label, detail, count, orgs }) => ({ id, label, detail, count, orgs }));
}

export interface FocusLayout {
  center: string;
  positions: Map<string, Point>;
  rings: TreeNode[][];
  advantages: Advantage[];
  advantagePositions: Map<string, Point>;
  outer: number;
}

/** 노드 하나를 가운데 두고, 이어지는 노드를 안쪽 고리에, 유리한 곳을 바깥 고리에 놓는다 */
export function layoutFocus(tree: TreeNode[], skill: string, opportunities: Opportunity[] = [], now = new Date(), targetJob?: string): FocusLayout {
  const positions = new Map<string, Point>([[skill, { x: 0, y: 0 }]]);
  const angles = new Map<string, number>([[skill, -Math.PI / 2]]);
  const rings = descendantRings(tree, skill);
  let radius = 0;
  for (const ring of rings) {
    radius = Math.max(radius + (radius ? RING_GAP : FIRST_RING), (ring.length * SLOT) / (2 * Math.PI));
    const target = (node: TreeNode) => {
      const known = parentsOf(node).flatMap((id) => angles.has(id) && id !== skill ? [angles.get(id)!] : []);
      return known.length ? known.reduce((sum, angle) => sum + angle, 0) / known.length : 0;
    };
    ring.sort((a, b) => target(a) - target(b)).forEach((node, index) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * index) / ring.length;
      angles.set(node.skill, angle);
      positions.set(node.skill, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius });
    });
  }
  const advantages = advantagesOf(tree, skill, opportunities, now, targetJob);
  const outer = Math.max(radius + (radius ? RING_GAP + 30 : FIRST_RING), (advantages.length * 260) / (2 * Math.PI));
  const advantagePositions = new Map(advantages.map((advantage, index) => {
    const angle = -Math.PI / 2 + (Math.PI / Math.max(advantages.length, 1)) + (2 * Math.PI * index) / advantages.length;
    return [advantage.id, { x: Math.cos(angle) * outer, y: Math.sin(angle) * outer }];
  }));
  return { center: skill, positions, rings, advantages, advantagePositions, outer };
}

// ── 원형 파형 보기: 1학년 1학기(12시)부터 4학년 2학기까지 시계방향 8칸 ──
export const SEMESTERS = ["1-1", "1-2", "2-1", "2-2", "3-1", "3-2", "4-1", "4-2"];

/** 지금 학기 칸(0~7). 3~8월은 1학기, 9~2월은 2학기(1·2월은 직전 2학기)로 본다 */
export function currentSemester(grade: number, now: Date) {
  const month = now.getMonth() + 1;
  const term = month >= 3 && month <= 8 ? 0 : 1;
  const year = Math.min(Math.max(Math.round(grade) || 1, 1), 4);
  return Math.min((year - 1) * 2 + term, SEMESTERS.length - 1);
}

/**
 * 노드별 권장 학기 칸(정석 로드맵). 학기 정보가 따로 없어 준비 단계 순서로 추정한다.
 * 단계 순서대로 줄 세운 뒤 1학년 1학기부터 4학년 2학기까지 고르게 나눈다. 선수 노드는 항상 같은 칸이거나 앞 칸이다.
 * 지난 학기 칸에 있는데 아직 안 한 노드는 화면에서 '밀린 노드'로 표시한다.
 */
export function assignSemesters(tree: TreeNode[]): Map<string, number> {
  const ordered = tree.map((node, index) => ({ node, index })).sort((a, b) => a.node.depth - b.node.depth || a.index - b.index);
  return new Map(ordered.map(({ node }, i) => [node.skill, Math.floor((i * SEMESTERS.length) / Math.max(ordered.length, 1))]));
}
