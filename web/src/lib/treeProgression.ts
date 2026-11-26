import type { TreeNode } from "./engine";
import { COMMON_SKILLS, SKILL_ROUTES, LANGUAGE_EXAMS } from "./data/skillRoutes";
import type { SkillRoute } from "./types";

export type TreeMode = "employment" | "startup";

export const EMPLOYMENT_SECTIONS = ["공통 역량", "직무 자격증", "프로젝트·포트폴리오"];
export const STARTUP_SECTIONS = ["공통 준비", "고객·시장 검증", "아이템 구체화", "사업화 준비"];

export function startupSection(node: TreeNode) {
  if (node.startupSection && STARTUP_SECTIONS.includes(node.startupSection)) return node.startupSection;
  if (node.route?.domain === "common") return STARTUP_SECTIONS[0];
  const key = node.skill.replace("SU-PREP-", "");
  if (["problem", "item", "business-model", "team-capability", "SU-DOC-team-introduction"].includes(key)) return STARTUP_SECTIONS[0];
  if (["market", "customer-validation", "differentiation", "social-impact", "target-customer"].includes(key)) return STARTUP_SECTIONS[1];
  if (["feasibility", "execution", "schedule", "SU-DOC-prototype", "item-images"].includes(key)) return STARTUP_SECTIONS[2];
  return STARTUP_SECTIONS[3];
}

export function employmentSection(node: TreeNode) {
  if (routeFor(node).domain === "common") return EMPLOYMENT_SECTIONS[0];
  return node.kind === "자격증" ? EMPLOYMENT_SECTIONS[1] : EMPLOYMENT_SECTIONS[2];
}

export function layoutEmployment(tree: TreeNode[]) {
  const positions = new Map<string, { x: number; y: number }>();
  const levels = [...new Set(tree.map(node => node.depth))].sort((a, b) => a - b);
  const width = 432;
  let y = 100;
  for (const depth of levels) {
    let rows = 1;
    EMPLOYMENT_SECTIONS.forEach((title, section) => {
      const group = tree.filter(node => node.depth === depth && employmentSection(node) === title)
        .sort((a, b) => (a.credentialPriority?.rank ?? 2) - (b.credentialPriority?.rank ?? 2));
      rows = Math.max(rows, Math.ceil(group.length / 2));
      group.forEach((node, index) => positions.set(node.skill, {
        x: section * (width + 80) + (index % 2) * 226,
        y: y + Math.floor(index / 2) * 210,
      }));
    });
    y += rows * 210 + 90;
  }
  const bands = EMPLOYMENT_SECTIONS.map((title, section) => ({
    depth: -section - 1, x: section * (width + 80), y: 0, width, title,
    skills: tree.filter(node => employmentSection(node) === title).map(node => node.skill),
  }));
  return { positions, bands };
}

// Keep the shared foundation small. Evidence-backed, completed and personal work
// stays visible, together with every prerequisite of the retained nodes.
export function unifiedTree(nodes: TreeNode[], mode: TreeMode, recommended?: string): TreeNode[] {
  const foundation = new Set(mode === "employment"
    ? ["SK-RESUME", "SK-COMP", ...LANGUAGE_EXAMS]
    : ["SU-PREP-problem", "SU-PREP-item", "SU-PREP-team-capability"]);
  const byId = new Map(nodes.map(node => [node.skill, node]));
  const personalPostings = new Set(nodes.filter(node => node.personalCompletion).flatMap(node => node.opportunities.map(opp => opp.id)));
  const curated = mode === "employment" && nodes.some(node => node.curated);
  const kept = new Set<string>();
  function keep(id: string) {
    if (kept.has(id)) return;
    const node = byId.get(id);
    if (!node) return;
    kept.add(id);
    [...node.prereq, ...(node.sequence ?? [])].forEach(keep);
  }
  for (const node of nodes) {
    const relevant = mode === "employment"
      ? routeFor(node).domain === "specialist" || (node.evidence ?? []).some(signal => signal.basis === "required" || signal.basis === "preferred")
      : !!node.personalCompletion || node.opportunities.some(opp => personalPostings.has(opp.id));
    if ((curated ? node.curated : foundation.has(node.skill) || relevant || node.required) || node.mine || node.state !== "none" || node.skill === recommended) keep(node.skill);
  }
  const visible = nodes.filter(node => kept.has(node.skill));
  if (mode !== "employment") return visible;
  const exams = visible.filter(node => LANGUAGE_EXAMS.includes(node.skill));
  if (!exams.length) return visible;
  const group: TreeNode = {
    skill: "COMMON-LANGUAGE", name: "어학", kind: "분류", required: false,
    prereq: [], depth: 0, state: "none", locked: false, opportunities: [],
    route: { domain: "common", stage: 0 }, groupChildren: exams.map(node => node.skill),
  };
  return [group, ...visible.map(node => LANGUAGE_EXAMS.includes(node.skill)
    ? { ...node, groupParent: group.skill, depth: Math.max(1, node.depth) } : node)]
    .sort((a, b) => a.depth - b.depth);

}

// Only concrete result reuse establishes an optional ordering for legacy nodes.
// General business topics can proceed in parallel.
const startupSequence: Record<string, string[]> = {
  "item-images": ["SU-DOC-prototype"],
  "SU-DOC-portfolio": ["SU-DOC-prototype"],
};
const startupId = (key: string) => key.startsWith("SU-") ? key : "SU-PREP-" + key;

function initialDepth(node: TreeNode, mode: TreeMode) {
  if (mode === "startup") {
    return 0; // Section is a category, never a minimum dependency depth.
  }
  return routeFor(node).stage;
}

export function routeFor(node: TreeNode): SkillRoute {
  if (node.route) return node.route;
  const explicit = SKILL_ROUTES[node.skill];
  if (explicit) return { ...explicit, stage: node.credentialOption?.stage ?? explicit.stage };
  return {
    domain: COMMON_SKILLS.has(node.skill) || node.kind === "어학" ? "common" : "specialist",
    stage: node.credentialOption?.stage ?? (node.practice ? (node.practice.independent ? 1 : 2)
      : node.kind === "프로젝트" || node.kind === "경험" ? 2 : node.kind === "교육" ? 0 : 1),
  };
}

// Reject invalid prerequisites; optional preparation suggestions never change eligibility.
export function assignProgression(nodes: TreeNode[], mode: TreeMode): TreeNode[] {
  const byId = new Map(nodes.map(node => [node.skill, node]));
  if (byId.size !== nodes.length) throw new Error("스킬 경로에 중복 ID가 있어요.");
  const depths = new Map<string, number>();
  const active = new Set<string>();
  const sequences = new Map<string, string[]>();
  const ordered: TreeNode[] = [];
  function visit(id: string) {
    if (depths.has(id)) return;
    if (active.has(id)) throw new Error(`스킬 경로 순환: ${[...active, id].join(" → ")}`);
    const node = byId.get(id);
    if (!node) throw new Error(`없는 선행 스킬: ${id}`);
    active.add(id);
    const required = node.prereq;
    for (const parent of required) visit(parent);
    let depth = Math.max(initialDepth(node, mode), ...required.map(parent => depths.get(parent)! + 1));
    const suggestions = mode === "startup" ? node.personalCompletion ? node.sequence ?? []
      : (startupSequence[id.replace("SU-PREP-", "")] ?? []).map(startupId)
      : routeFor(node).recommendedBefore ?? [];
    const sequence: string[] = [];
    for (const parent of suggestions) {
      if (node.personalCompletion) {
        visit(parent);
        sequence.push(parent);
        depth = Math.max(depth, depths.get(parent)! + 1);
        continue;
      }
      // A suggested path must never contradict a mandatory path.
      const reaches = (current: string, seen = new Set<string>()): boolean => {
        if (current === id) return true;
        if (seen.has(current)) return false;
        seen.add(current);
        const other = byId.get(current);
        return !!other && [...other.prereq, ...(mode === "startup" ? [] : routeFor(other).recommendedBefore ?? [])]
          .some(next => reaches(next, seen));
      };
      if (!byId.has(parent) || active.has(parent) || reaches(parent)) continue;
      visit(parent);
      sequence.push(parent);
      depth = Math.max(depth, depths.get(parent)! + 1);
    }
    active.delete(id);
    depths.set(id, depth);
    sequences.set(id, sequence);
    ordered.push(node);
  }
  for (const node of nodes) visit(node.skill);
  return ordered.map(node => ({ ...node,
    route: mode === "employment" ? routeFor(node) : node.route,
    depth: depths.get(node.skill)!, sequence: sequences.get(node.skill) ?? [],
  })).sort((a, b) => a.depth - b.depth);
}

export function progressionStage(depth: number, mode: TreeMode, domain?: "common" | "specialist") {
  if (mode === "startup") return { title: depth === 0 ? "병행 가능한 준비" : `선행 작업 후 · ${depth}단계`, detail: "연결된 작업의 결과물을 활용해 다음 준비를 진행해요." };
  if (domain === "common") {
    const common = [
      { title: "공통 기본기", detail: "여러 직무에서 함께 사용하는 기본 역량을 준비해요." },
      { title: "어학·도구 활용", detail: "목표 직무에서 필요한 어학과 업무 도구를 선택해 준비해요." },
      { title: "업무 결과물", detail: "문서·분석표·발표 자료처럼 활용할 수 있는 결과물을 만들어요." },
      { title: "지원 서류", detail: "목표 공고에 맞춰 경력과 작업물을 설명해요." },
      { title: "포트폴리오·면접", detail: "작업물을 제출용으로 묶고 면접에서 자신의 기여를 설명해요." },
    ];
    return common[Math.min(depth, common.length - 1)];
  }
  if (depth > 4) return { title: `전문 심화 · 후속 ${depth - 4}`, detail: "앞선 실전·전문 과제를 마친 뒤 이어서 준비해요." };
  const stages = [
    { title: "공통 역량과 직무 기초", detail: "직무를 살펴보고 기초 지식을 익혀요." },
    { title: "직무 핵심 역량", detail: "목표 직무에 필요한 지식과 도구를 준비해요." },
    { title: "직무 실습과 결과물", detail: "배운 내용을 작은 과제에 적용해요." },
    { title: "프로젝트와 지원 서류", detail: "여러 역량을 활용해 깊이 있는 결과물을 만들어요." },
    { title: "포트폴리오와 실전 경험", detail: "실전 경험과 전문 과제, 지원용 작업물을 준비해요." },
  ];
  return stages[Math.min(depth, stages.length - 1)];
}

export function earlierUnfinishedStep(nodes: TreeNode[], target: string): TreeNode | undefined {
  const byId = new Map(nodes.map(node => [node.skill, node]));
  const visited = new Set<string>();
  const missing: TreeNode[] = [];
  function visit(id: string): void {
    if (visited.has(id)) return;
    visited.add(id);
    const node = byId.get(id);
    if (!node || node.state !== "none") return;
    const parents = (node.sequence ?? []).map(parent => byId.get(parent)).filter((parent): parent is TreeNode => !!parent)
      .sort((a, b) => a.depth - b.depth);
    for (const parent of parents) {
      visit(parent.skill);
    }
    missing.push(node);
  }
  visit(target);
  return missing.sort((a, b) => a.depth - b.depth)[0];
}

export function layoutProgression(tree: TreeNode[], columns = 3) {
  const positions = new Map<string, { x: number; y: number }>();
  const levels = [...new Set(tree.map(node => node.depth))].sort((a, b) => a - b);
  const bands = [];
  let y = 0;
  for (const depth of levels) {
    const group = tree.filter(node => node.depth === depth);
    const center = (node: TreeNode) => {
      const parents = [...node.prereq, ...(node.sequence ?? [])].flatMap(id => positions.has(id) ? [positions.get(id)!.x] : []);
      return parents.length ? parents.reduce((sum, x) => sum + x, 0) / parents.length : 0;
    };
    group.sort((a, b) => center(a) - center(b));
    const width = Math.max(columns, group.length) * 226 - 20;
    bands.push({ depth, y, skills: group.map(node => node.skill), width });
    group.forEach((node, index) => positions.set(node.skill, { x: index * 226, y: y + 90 }));
    y += 300;
  }
  return { positions, bands };
}
