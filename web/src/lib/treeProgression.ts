import type { TreeNode } from "./engine";
import { COMMON_SKILLS, SKILL_ROUTES } from "./data/skillRoutes";
import type { SkillRoute } from "./types";

export type TreeMode = "employment" | "startup";

const startupStages = [
  { title: "문제·팀 정리", detail: "아이템과 해결할 문제, 팀의 역할을 구체화해요.", skills: ["problem", "item", "team-capability", "regional-value", "SU-DOC-team-introduction"] },
  { title: "시장·가설 검증", detail: "고객과 경쟁 대안을 조사하고 사업모델을 점검해요.", skills: ["market", "business-model", "customer-validation", "differentiation", "social-impact", "target-customer"] },
  { title: "개발·실행 설계", detail: "개발 방법, 일정과 필요한 자금을 계획해요.", skills: ["feasibility", "execution", "schedule", "funding", "budget", "cost-breakdown"] },
  { title: "시제품·실증", detail: "제품을 구현하고 확인 가능한 결과물을 준비해요.", skills: ["SU-DOC-prototype", "item-images"] },
  { title: "사업화·제출자료", detail: "사업화 전략과 지원할 공고의 제출자료를 완성해요.", skills: ["market-entry", "SU-DOC-business-plan", "SU-DOC-pitch-deck", "SU-DOC-portfolio"] },
];

// Service-authored preparation order. These edges do not impose application eligibility.
const startupSequence: Record<string, string[]> = {
  market: ["problem"],
  "business-model": ["problem", "item"],
  "customer-validation": ["problem"],
  differentiation: ["item"],
  "social-impact": ["problem"],
  feasibility: ["market"],
  execution: ["business-model", "team-capability"],
  schedule: ["business-model"],
  funding: ["business-model"],
  budget: ["business-model"],
  "cost-breakdown": ["business-model"],
  "SU-DOC-prototype": ["feasibility", "schedule"],
  "item-images": ["feasibility"],
  "market-entry": ["customer-validation", "SU-DOC-prototype"],
  "SU-DOC-business-plan": ["execution", "budget"],
  "SU-DOC-pitch-deck": ["differentiation", "feasibility"],
  "SU-DOC-portfolio": ["SU-DOC-prototype"],
};
const startupId = (key: string) => key.startsWith("SU-") ? key : "SU-PREP-" + key;

function initialDepth(node: TreeNode, mode: TreeMode) {
  if (mode === "startup") {
    if (node.personalCompletion) return node.route?.stage ?? node.depth;
    const index = startupStages.findIndex(stage => stage.skills.some(key => startupId(key) === node.skill));
    return index < 0 ? 2 : index;
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
  if (mode === "startup") return startupStages[Math.min(depth, startupStages.length - 1)];
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
    { title: "직무 이해·기초", detail: "직무를 살펴보고 기초 지식을 익혀요." },
    { title: "전공·핵심 역량", detail: "목표 직무에 필요한 지식과 도구를 준비해요." },
    { title: "응용·직무 실습", detail: "배운 내용을 작은 과제에 적용해요." },
    { title: "프로젝트·심화", detail: "여러 역량을 활용해 깊이 있는 결과물을 만들어요." },
    { title: "실전·전문 심화", detail: "실전 경험과 전문 과제, 지원용 작업물을 준비해요." },
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
