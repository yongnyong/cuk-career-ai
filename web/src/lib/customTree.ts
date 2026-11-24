import type { TreeNode } from "./engine";
import type { CustomNode, CustomTree, SkillKind } from "./types";
import type { WeightTier } from "./treeRadial";

// 학생이 직접 만드는 트리(예: '토브넷 입사 루트'). 프로필에 함께 저장된다.
export const KINDS: SkillKind[] = ["역량", "자격증", "어학", "교육", "프로젝트", "경험"];
export const LIMITS = { trees: 10, nodes: 40, name: 40, note: 300 } as const;

const newId = () => (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`).slice(0, 12);

export function emptyTree(now: Date): CustomTree {
  return { id: newId(), title: "새 트리", goal: "", nodes: [], createdAt: now.toISOString(), updatedAt: now.toISOString() };
}

export function newNode(name = "새 노드"): CustomNode {
  return { id: newId(), name, kind: "역량", weight: 2, prereq: [], done: false };
}

/** 지금 스킬트리를 복사해 고쳐 쓸 수 있게 한다. 가중치는 화면의 노드 크기를 그대로 옮긴다 */
export function fromCareerTree(title: string, goal: string, tree: TreeNode[], weights: Map<string, { tier: WeightTier }>, now: Date): CustomTree {
  const ids = new Set(tree.map((n) => n.skill));
  return {
    ...emptyTree(now),
    title,
    goal,
    nodes: tree.slice(0, LIMITS.nodes).map((n) => ({
      id: n.skill,
      name: n.name,
      kind: n.kind as SkillKind,
      weight: weights.get(n.skill)?.tier ?? 2,
      prereq: n.prereq.filter((q) => ids.has(q)),
      done: n.state !== "none",
    })),
  };
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
