import type { Job, RecommendedQuest, SkillState, TreeSignal } from "./types";

type NodeInput = Job["nodes"][number] & { kind: string; state: SkillState };

const basisRank: Record<TreeSignal["basis"], number> = {
  required: 4, preferred: 3, activity: 2, school: 1,
};

function compareSignals(a: TreeSignal, b: TreeSignal) {
  return basisRank[b.basis] - basisRank[a.basis] ||
    Number(a.reference.historical) - Number(b.reference.historical) ||
    Number(b.status === "gap") - Number(a.status === "gap") ||
    (b.reference.version ?? 0) - (a.reference.version ?? 0) ||
    a.reference.id.localeCompare(b.reference.id);
}

export function groupTreeSignals(signals: readonly TreeSignal[]) {
  const grouped = new Map<string, TreeSignal[]>();
  for (const signal of [...signals].sort(compareSignals)) {
    if (signal.status === "matched") continue;
    let url: URL;
    try {
      url = new URL(signal.reference.url);
    } catch {
      continue;
    }
    if (url.protocol !== "https:" && url.protocol !== "http:") continue;
    url.hash = "";
    const references = grouped.get(signal.skillId) ?? [];
    if (references.some((entry) => entry.reference.id === signal.reference.id || entry.reference.url === url.href)) continue;
    references.push({ ...signal, reference: { ...signal.reference, url: url.href } });
    grouped.set(signal.skillId, references);
  }
  return grouped;
}

export function buildPersonalizedTree<T extends NodeInput>(
  nodes: readonly T[], signals: ReadonlyMap<string, TreeSignal[]>, focus: readonly string[],
): T[] {
  const choices = nodes.filter((node) => !node.required && node.state === "none" && signals.has(node.skill));
  if (!choices.length) return [...nodes];
  const strongest = (node: T) => basisRank[signals.get(node.skill)![0].basis];
  choices.sort((a, b) => strongest(b) - strongest(a) ||
    Number(focus.includes(b.kind)) - Number(focus.includes(a.kind)) ||
    signals.get(b.skill)!.length - signals.get(a.skill)!.length);
  const bySkill = new Map(nodes.map((node) => [node.skill, node]));
  const selected = new Set<string>();
  function include(skill: string) {
    const node = bySkill.get(skill);
    if (!node || selected.has(skill)) return;
    selected.add(skill);
    for (const prerequisite of node.prereq ?? []) include(prerequisite);
  }
  for (const node of nodes) {
    if (node.required || node.state !== "none") include(node.skill);
  }
  let branches = 0;
  for (const node of choices) {
    if (selected.has(node.skill)) continue;
    include(node.skill);
    if (++branches === 2) break;
  }
  return nodes.filter((node) => selected.has(node.skill));
}

export function selectRecommendedQuest(
  nodes: readonly (NodeInput & { locked: boolean })[],
  signals: ReadonlyMap<string, TreeSignal[]>,
  focus: readonly string[],
  belowTarget: ReadonlySet<string>,
): RecommendedQuest | null {
  const bySkill = new Map(nodes.map((node) => [node.skill, node]));
  const inherited = new Map<string, { targetSkill: string; signals: TreeSignal[] }>();
  function connectPrerequisites(skill: string, targetSkill: string, evidence: TreeSignal[], visited: Set<string>) {
    if (visited.has(skill)) return;
    visited.add(skill);
    const node = bySkill.get(skill);
    if (!node || node.state !== "none") return;
    const previous = inherited.get(skill);
    if (!previous || compareSignals(evidence[0], previous.signals[0]) < 0) {
      inherited.set(skill, { targetSkill, signals: evidence });
    }
    for (const parent of node.prereq ?? []) connectPrerequisites(parent, targetSkill, evidence, visited);
  }
  for (const node of nodes) {
    const evidence = signals.get(node.skill);
    if (node.state === "none" && node.locked && evidence?.length) {
      const visited = new Set([node.skill]);
      for (const parent of node.prereq ?? []) connectPrerequisites(parent, node.skill, evidence, visited);
    }
  }

  const candidates = nodes.flatMap((node) => {
    if (node.locked) return [];
    const direct = signals.get(node.skill) ?? [];
    const route = inherited.get(node.skill);
    const improve = belowTarget.has(node.skill);
    const verify = direct[0]?.status === "unknown";
    if (node.state !== "none" && !improve && !verify) return [];
    const usePrerequisite = route && (!direct.length || compareSignals(route.signals[0], direct[0]) < 0);
    const evidence = usePrerequisite ? route.signals : direct;
    const quest: RecommendedQuest = {
      skillId: node.skill,
      actionKind: usePrerequisite ? "start" : improve ? "improve" : verify ? "verify" : "start",
      reasonCode: usePrerequisite ? "prerequisite" : evidence.length ? "evidence" : improve ? "score_target" : "track",
      signals: evidence,
      targetSkill: usePrerequisite ? route.targetSkill : undefined,
    };
    return [{ node, quest, rank: evidence.length ? basisRank[evidence[0].basis] : improve ? 1 : 0 }];
  });
  candidates.sort((a, b) => b.rank - a.rank ||
    Number(focus.includes(b.node.kind)) - Number(focus.includes(a.node.kind)) ||
    Number(b.node.required) - Number(a.node.required) ||
    b.quest.signals.length - a.quest.signals.length);
  return candidates[0]?.quest ?? null;
}
