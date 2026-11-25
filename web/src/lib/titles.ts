import type { TreeNode } from "./engine";
import { HOME_PROOFS, OUTFIT_LABEL, STAGE_FROM, type Outfit } from "./hayang";

// 칭호: 스킬트리에서 실제로 한 일로만 얻는다. 희귀도는 색으로 구분한다
export type Rarity = "common" | "rare" | "epic" | "legend";
export const RARITY_LABEL: Record<Rarity, string> = { common: "일반", rare: "희귀", epic: "영웅", legend: "전설" };

export interface TitleInput {
  tree: TreeNode[];
  pct: number; // 완료한 노드 비율(진화 진행도)
  outfit: Outfit;
  questsStarted: number; // 지원 퀘스트로 시작한 공고 수
  coreSkills: ReadonlySet<string>; // 핵심(크기 '대') 노드
  proofs?: number; // 증빙을 첨부한 완료 노드 수(내 집 마련 인증)
}

export interface Title {
  id: string;
  name: string;
  rarity: Rarity;
  how: string; // 얻는 방법
  earned: boolean;
  progress?: string; // 아직이면 '1/3' 같은 진행
}

const done = (n: TreeNode) => n.state !== "none";
const count = (tree: TreeNode[], pick: (n: TreeNode) => boolean) => tree.filter((n) => pick(n) && done(n)).length;
const step = (have: number, need: number) => ({ earned: have >= need, progress: have >= need ? undefined : `${have}/${need}` });

export function titlesFor(input: TitleInput): Title[] {
  const { tree, pct, outfit, questsStarted, coreSkills, proofs = 0 } = input;
  const cores = tree.filter((n) => coreSkills.has(n.skill));
  const byPct = (need: number) => ({ earned: pct >= need, progress: `${pct}/${need}%` });
  const list: (Omit<Title, "earned" | "progress"> & { check: () => { earned: boolean; progress?: string } })[] = [
    { id: "freshman", name: "갓 입학한 새내기", rarity: "common", how: "CUK Career AI 시작", check: () => ({ earned: true }) },
    { id: "first-step", name: "첫 발걸음", rarity: "common", how: "노드 1개 완료", check: () => step(count(tree, () => true), 1) },
    { id: "hunter", name: "기회 사냥꾼", rarity: "common", how: "지원 퀘스트 1개 시작", check: () => step(questsStarted, 1) },
    { id: "collector", name: "자격증 수집가", rarity: "rare", how: "자격증 노드 2개 완료", check: () => step(count(tree, (n) => n.kind === "자격증"), 2) },
    { id: "global", name: "글로벌 인재", rarity: "rare", how: "어학 노드 1개 완료", check: () => step(count(tree, (n) => n.kind === "어학"), 1) },
    { id: "maker", name: "프로젝트 장인", rarity: "rare", how: "프로젝트 노드 3개 완료", check: () => step(count(tree, (n) => n.kind === "프로젝트"), 3) },
    { id: "proven", name: "증명하는 자", rarity: "rare", how: "검증된 노드 1개", check: () => step(tree.filter((n) => n.state === "verified").length, 1) },
    { id: "core", name: "핵심만 찍는 자", rarity: "epic", how: "★ 핵심 노드 모두 완료", check: () => cores.length ? step(cores.filter(done).length, cores.length) : { earned: false, progress: "핵심 노드 없음" } },
    { id: "job", name: `${OUTFIT_LABEL[outfit]} 하양이`, rarity: "epic", how: `진화 2단계(노드 ${STAGE_FROM[1]}% 완료)`, check: () => byPct(STAGE_FROM[1]) },
    { id: "bag", name: "명품백 든 하양이", rarity: "epic", how: `진화 3단계(노드 ${STAGE_FROM[2]}% 완료)`, check: () => byPct(STAGE_FROM[2]) },
    { id: "car", name: "차 뽑은 하양이", rarity: "epic", how: `진화 4단계(노드 ${STAGE_FROM[3]}% 완료)`, check: () => byPct(STAGE_FROM[3]) },
    { id: "home", name: "내 집 마련", rarity: "legend", how: `진화 5단계(노드 ${STAGE_FROM[4]}% 완료 + 증빙 인증 ${HOME_PROOFS}개)`,
      check: () => pct < STAGE_FROM[4] ? byPct(STAGE_FROM[4]) : { earned: proofs >= HOME_PROOFS, progress: `인증 ${proofs}/${HOME_PROOFS}` } },
    { id: "allclear", name: "올클리어", rarity: "legend", how: "스킬트리 노드 전부 완료", check: () => byPct(100) },
  ];
  return list.map(({ check, ...t }) => {
    const r = check();
    return { ...t, earned: r.earned, progress: r.earned ? undefined : r.progress };
  });
}

const RANK: Record<Rarity, number> = { common: 0, rare: 1, epic: 2, legend: 3 };

/** 장착한 칭호. 고른 게 없거나 더는 자격이 없으면 얻은 것 중 가장 희귀한 것(같으면 뒤에 얻는 것) */
export function equippedTitle(titles: Title[], chosen?: string): Title {
  const earned = titles.filter((t) => t.earned);
  return earned.find((t) => t.id === chosen) ?? earned.reduce((best, t) => (RANK[t.rarity] >= RANK[best.rarity] ? t : best), earned[0]);
}
