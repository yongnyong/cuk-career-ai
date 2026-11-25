import type { TreeNode } from "./engine";
import type { CustomNode, CustomTree, SkillKind } from "./types";
import type { WeightTier } from "./treeRadial";

// 학생이 스킬트리에 직접 더하는 노드(예: '토브넷 입사 준비'). 프로필에 직무별로 저장된다.
export const KINDS: SkillKind[] = ["역량", "자격증", "어학", "교육", "프로젝트", "경험"];
export const LIMITS = { nodes: 40, name: 40, note: 300 } as const;

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
