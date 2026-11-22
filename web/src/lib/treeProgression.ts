import type { TreeNode } from "./engine";

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
    const index = startupStages.findIndex(stage => stage.skills.some(key => startupId(key) === node.skill));
    return index < 0 ? 2 : index;
  }
  if (["PR-ROLE-COMPARISON", "PR-COURSE-EVIDENCE"].includes(node.skill)) return 0;
  if (/포트폴리오|이력서|자기소개서|지원서|취업 면접/.test(node.name)) return 4;
  if (/배포|캡스톤|졸업연구|학부연구|논문 참여|실무실습|임상실습|인턴|현장실습|고급|심화/.test(node.name)) return 3;
  if (/기초|입문|개론|기본기/.test(node.name)) return 0;
  if (node.credentialOption) return node.credentialOption.stage;
  if (node.kind === "어학" || node.kind === "자격증") return 1;
  if (node.practice) return node.practice.independent ? 1 : 2;
  return node.kind === "프로젝트" || node.kind === "경험" ? 2 : 1;
}

export function assignProgression(nodes: TreeNode[], mode: TreeMode): TreeNode[] {
  const byId = new Map(nodes.map(node => [node.skill, node]));
  const depths = new Map<string, number>();
  function depthOf(id: string): number {
    const known = depths.get(id);
    if (known !== undefined) return known;
    const node = byId.get(id)!;
    const base = initialDepth(node, mode);
    depths.set(id, base);
    const parents = mode === "startup" ? (startupSequence[id.replace("SU-PREP-", "")] ?? []).map(startupId) : node.prereq;
    const depth = Math.max(base, ...parents.filter(parent => byId.has(parent)).map(parent => depthOf(parent) + 1));
    depths.set(id, depth);
    return depth;
  }
  return nodes.map(node => ({
    ...node,
    depth: depthOf(node.skill),
    sequence: mode === "startup"
      ? (startupSequence[node.skill.replace("SU-PREP-", "")] ?? []).map(startupId).filter(id => byId.has(id))
      : [],
  })).sort((a, b) => a.depth - b.depth);
}

export function progressionStage(depth: number, mode: TreeMode) {
  if (mode === "startup") return startupStages[Math.min(depth, startupStages.length - 1)];
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
    bands.push({ depth, y, skills: group.map(node => node.skill), width: columns * 226 - 20 });
    group.forEach((node, index) => positions.set(node.skill, { x: index % columns * 226, y: y + 76 + Math.floor(index / columns) * 130 }));
    y += 76 + Math.ceil(group.length / columns) * 130 + 64;
  }
  return { positions, bands };
}
