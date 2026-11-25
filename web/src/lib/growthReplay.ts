// 성장 재생: 빈 트리에서 지금 트리까지 노드가 하나씩 켜지는 순서를 만든다.
// 노드를 언제 완료했는지는 저장하지 않으므로, 실제 완료 순서가 아니라 준비 단계 순서(안쪽 고리 → 바깥 고리)로 재생한다.
import { hayangStage, type HayangStage } from "./hayang";
import { ringOf } from "./treeRadial";

type ReplayNode = { skill: string; name: string; state: string; depth: number };

export type ReplayEvent =
  | { type: "intro"; ms: number }
  | { type: "ring"; stage: number; ms: number }
  | { type: "node"; skill: string; name: string; ms: number }
  | { type: "evolve"; from: HayangStage; to: HayangStage; ms: number }
  | { type: "end"; ms: number };

/** full이면 아직 안 한 노드까지 모두 켜는 '완성 미리보기' */
export function replayScript(tree: readonly ReplayNode[], full = false): ReplayEvent[] {
  const lit = tree.filter((n) => full || n.state !== "none").map((n, index) => ({ n, index }))
    .sort((a, b) => ringOf(a.n.depth) - ringOf(b.n.depth) || a.n.depth - b.n.depth || a.index - b.index).map((x) => x.n);
  // 노드가 많아도 점등 구간이 12초 안팎이 되게 한 개당 시간을 맞춘다
  const per = Math.round(Math.min(900, Math.max(260, 12000 / Math.max(lit.length, 1))));
  const events: ReplayEvent[] = [{ type: "intro", ms: 1100 }];
  for (const stage of [...new Set(tree.map((n) => ringOf(n.depth)))].sort((a, b) => a - b)) events.push({ type: "ring", stage, ms: 380 });
  let stage: HayangStage = 1;
  lit.forEach((node, index) => {
    events.push({ type: "node", skill: node.skill, name: node.name, ms: per });
    const next = hayangStage(Math.round(((index + 1) / Math.max(tree.length, 1)) * 100));
    if (next > stage) {
      events.push({ type: "evolve", from: stage, to: next, ms: 1500 });
      stage = next;
    }
  });
  events.push({ type: "end", ms: 0 });
  return events;
}

/** index번째 이벤트까지 끝났을 때의 화면 상태 */
export function replayState(events: readonly ReplayEvent[], index: number) {
  const lit: string[] = [];
  const rings: number[] = [];
  let stage: HayangStage = 1;
  for (const event of events.slice(0, index + 1)) {
    if (event.type === "node") lit.push(event.skill);
    if (event.type === "ring") rings.push(event.stage);
    if (event.type === "evolve") stage = event.to;
  }
  return { lit, rings, stage, current: events[Math.min(index, events.length - 1)] };
}
