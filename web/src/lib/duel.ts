// 스킬트리 대전: 두 사람의 트리를 나란히 놓고, 이기고 지는 것보다 둘이 같이 하면 좋은 일을 찾는다.
import { KINDS } from "./customTree";

export interface DuelNode { skill: string; name: string; kind: string; done: boolean; depth: number }
export interface Duelist { name: string; desc: string; jobId: string; startup: boolean; nodes: DuelNode[] }

type TreeLike = { skill: string; name: string; kind: string; state: string; depth: number };
export const duelistOf = (name: string, desc: string, jobId: string, startup: boolean, tree: readonly TreeLike[]): Duelist => ({
  name, desc, jobId, startup,
  nodes: tree.map((n) => ({ skill: n.skill, name: n.name, kind: n.kind, done: n.state !== "none", depth: n.depth })),
});

export type Together =
  | { type: "both"; name: string; kind: string } // 둘 다 아직 안 한 같은 노드
  | { type: "teach"; name: string; kind: string } // 나는 했고 상대는 아직
  | { type: "learn"; name: string; kind: string } // 상대는 했고 나는 아직
  | { type: "kind"; kind: string; mine: string; theirs: string }; // 같은 분류에서 각자 다음 할 일

export function duel(me: Duelist, other: Duelist) {
  const kinds = KINDS.filter((kind) => [...me.nodes, ...other.nodes].some((n) => n.kind === kind));
  const count = (d: Duelist, kind: string) => {
    const nodes = d.nodes.filter((n) => n.kind === kind);
    return { done: nodes.filter((n) => n.done).length, total: nodes.length };
  };
  const axes = kinds.map((kind) => ({ kind, me: count(me, kind), other: count(other, kind) }));
  const theirs = new Map(other.nodes.map((n) => [n.skill, n]));
  const shared = [...me.nodes].sort((a, b) => a.depth - b.depth).flatMap((n) => theirs.has(n.skill) ? [{ mine: n, theirs: theirs.get(n.skill)! }] : []);
  const pick = (type: "both" | "teach" | "learn", test: (mine: boolean, theirs: boolean) => boolean, limit: number): Together[] =>
    shared.filter((x) => test(x.mine.done, x.theirs.done)).slice(0, limit).map((x) => ({ type, name: x.mine.name, kind: x.mine.kind }));
  const sharedIds = new Set(shared.map((x) => x.mine.skill));
  const next = (d: Duelist, kind: string) => [...d.nodes].sort((a, b) => a.depth - b.depth).find((n) => n.kind === kind && !n.done && !sharedIds.has(n.skill));
  const byKind: Together[] = kinds.flatMap((kind) => {
    const mine = next(me, kind), their = next(other, kind);
    return mine && their ? [{ type: "kind" as const, kind, mine: mine.name, theirs: their.name }] : [];
  });
  const together = [
    ...pick("both", (a, b) => !a && !b, 2),
    ...pick("teach", (a, b) => a && !b, 1),
    ...pick("learn", (a, b) => !a && b, 1),
    ...byKind,
  ].slice(0, 5);
  const done = (d: Duelist) => d.nodes.filter((n) => n.done).length;
  return { axes, together, team: { done: done(me) + done(other), total: me.nodes.length + other.nodes.length } };
}

// ── 친구에게 보내는 링크. 서버에 저장하지 않고 트리 요약을 주소에 담는다 ──
const MAX_NODES = 60;
const b64 = {
  to: (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""),
  from: (text: string) => Uint8Array.from(atob(text.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0)),
};

export function encodeDuelist(d: Duelist): string {
  const data = { n: d.name, d: d.desc, j: d.jobId, s: d.startup ? 1 : 0, k: d.nodes.slice(0, MAX_NODES).map((n) => [n.skill, n.name, KINDS.indexOf(n.kind as (typeof KINDS)[number]), n.done ? 1 : 0, n.depth]) };
  return b64.to(new TextEncoder().encode(JSON.stringify(data)));
}

/** 링크에서 온 값은 남이 만든 데이터다. 모양이 맞지 않으면 버리고, 길이를 자른다 */
export function decodeDuelist(code: string): Duelist | null {
  try {
    const data = JSON.parse(new TextDecoder().decode(b64.from(code)));
    const text = (value: unknown, max: number) => typeof value === "string" ? value.slice(0, max) : "";
    if (!data || !Array.isArray(data.k) || !text(data.n, 20)) return null;
    const nodes = (data.k as unknown[]).slice(0, MAX_NODES).flatMap((row): DuelNode[] => {
      if (!Array.isArray(row)) return [];
      const [skill, name, kind, done, depth] = row;
      const kindName = KINDS[Number(kind)];
      if (!text(skill, 60) || !text(name, 60) || !kindName) return [];
      return [{ skill: text(skill, 60), name: text(name, 60), kind: kindName, done: done === 1, depth: Math.min(Math.max(Number(depth) || 0, 0), 20) }];
    });
    return nodes.length ? { name: text(data.n, 20), desc: text(data.d, 40), jobId: text(data.j, 40), startup: data.s === 1, nodes } : null;
  } catch {
    return null;
  }
}
