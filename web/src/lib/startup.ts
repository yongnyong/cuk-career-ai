import { evaluate, isOpen, progress, type TreeNode } from "./engine";
import { selectRecommendedQuest } from "./skillTree";
import { assignProgression, earlierUnfinishedStep } from "./treeProgression";
import type { Opportunity, Profile, Skill, StartupCatalog, StartupPlan, TreeSignal } from "./types";

export const startupSkills = (catalog: StartupCatalog): Skill[] => catalog.nodes
  .filter((n) => n.kind === "artifact" || n.kind === "preparation")
  .map((n) => ({ id: n.id, name: n.title, kind: n.kind === "artifact" ? "프로젝트" : "역량", verifiable: false }));

export function buildStartupPath(profile: Profile, opportunities: Opportunity[], now: Date, catalog: StartupCatalog, plan?: StartupPlan) {
  const definitions = catalog.nodes.filter((n) => n.kind === "artifact" || n.kind === "preparation");
  const ids = new Set(definitions.map((n) => n.id));
  const byPosting = new Map(opportunities.filter((o) => o.startup).map((o) => [o.startup!.postingId, o]));
  const signals = new Map<string, TreeSignal[]>();
  let tree: TreeNode[] = definitions.map((definition): TreeNode => {
    const state = profile.skills[definition.id] ?? profile.skills[definition.related_skill_id ?? ""] ?? "none";
    const references: TreeSignal[] = definition.references.map((r) => ({
      skillId: definition.id, basis: r.necessity === "required" ? "required" : "activity",
      status: state === "none" ? "gap" : "matched",
      preparation: { kind: r.basis === "submission" ? "direct" : "suggested", action: definition.title, completion: definition.completion },
      reference: { id: r.posting_id, title: r.posting_title, url: r.source_url, quote: r.quote,
        historical: !byPosting.has(r.posting_id) || !isOpen(byPosting.get(r.posting_id)!, now), scope: "posting" },
    }));
    // Current required deliverables come first, while historic rubrics remain useful evidence.
    references.sort((a, b) => Number(a.reference.historical) - Number(b.reference.historical) || Number(b.basis === "required") - Number(a.basis === "required"));
    signals.set(definition.id, references);
    const connections = [...new Set(catalog.edges.filter((e) => e.parent_id === definition.id && ids.has(e.child_id)).map((e) => e.child_id))];
    const linkedIds = new Set(definition.references.map((r) => r.posting_id));
    return {
      route: { domain: "common", stage: 1 },
      skill: definition.id, name: definition.title.replace("발표자료·피치덱 제작", "아이템 소개 발표자료 제작"), kind: definition.kind === "artifact" ? "프로젝트" : "역량",
      required: false, prereq: [], connections, depth: 0, state, locked: false,
      opportunities: [...byPosting.values()].filter((o) => linkedIds.has(o.startup!.postingId) && isOpen(o, now) && evaluate(o, profile).overall !== "fail"),
      evidence: references, startup: definition,
    };
  });
  for (const item of plan?.nodes ?? []) {
    if (!item.active && !item.completed) continue;
    const dependencies = new Set(plan?.nodes.map(n => n.id));
    const references: TreeSignal[] = (item.evidence ?? []).map(source => {
      const posting = opportunities.find(o => o.id === source.posting_id);
      return {
        skillId: item.id, basis: "required", status: item.completed ? "matched" : "gap",
        preparation: { kind: "direct", action: item.title, completion: item.completion },
        reference: { id: source.posting_id, title: source.title + " · 공고 버전 " + source.version, url: source.source_url,
          quote: source.quote, historical: !posting || !isOpen(posting, now), scope: "posting" },
      };
    });
    tree.push({
      skill: item.id, name: item.title, kind: "프로젝트", state: item.completed ? "self" : "none",
      required: false, prereq: (item.requires ?? []).filter(id => dependencies.has(id)),
      locked: (item.requires ?? []).some(id => plan?.nodes.some(n => n.id === id && !n.completed)),
      depth: item.stage ?? 2, route: { domain: "specialist", stage: item.stage ?? 2 },
      sequence: item.reuse.filter(id => dependencies.has(id)),
      opportunities: opportunities.filter(o => item.evidence?.some(source => source.posting_id === o.id)),
      evidence: references, personalCompletion: item.completion, personalReason: item.reason,
    });
  }
  tree = assignProgression(tree, "startup");
  const remaining = tree.filter((n) => n.state === "none");
  remaining.sort((a, b) => Number(b.opportunities.length > 0) - Number(a.opportunities.length > 0) ||
    Number(b.startup?.kind === "preparation") - Number(a.startup?.kind === "preparation"));
  const active = remaining.filter((node) => node.opportunities.length > 0);
  let recommendedQuest = selectRecommendedQuest(active.length ? active : remaining, signals, [], new Set());
  const earlier = recommendedQuest && earlierUnfinishedStep(tree, recommendedQuest.skillId);
  if (earlier && earlier.skill !== recommendedQuest!.skillId) {
    recommendedQuest = { ...recommendedQuest!, skillId: earlier.skill, actionKind: "start", reasonCode: "prerequisite", targetSkill: recommendedQuest!.skillId };
  }
  const next = plan?.nodes.find(n => n.active && !n.completed);
  if (next) recommendedQuest = { skillId: next.id, actionKind: "start", reasonCode: "track", signals: [] };
  else if (plan?.nodes.some(n => n.active)) recommendedQuest = null;
  const skills = { ...profile.skills, ...Object.fromEntries(tree.map((node) => [node.skill, node.state])) };
  return { tree, recommendedQuest, treeProgress: progress({ ...profile, skills }, tree) };
}
