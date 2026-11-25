"use client";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { evolution, hayangImage, outfitFor, stageTitle, type HayangStage, type Outfit } from "@/lib/hayang";
import { listProofs, PROOFS_CHANGED } from "@/lib/files";
import { equippedTitle, RARITY_LABEL, titlesFor, type Title } from "@/lib/titles";
import { nodeWeights } from "@/lib/treeRadial";
import { careerInterestOf } from "@/lib/interest";
import { useStore } from "@/lib/store";
import { useMounted } from "@/lib/useMounted";

// 자동차·아파트는 하양이와 같은 굵은 남색 외곽선·단색 채색으로 그린 소품이다
function Car() {
  return (
    <svg viewBox="0 0 120 64" className="h-full w-full" aria-hidden>
      <path d="M10 44 Q8 30 22 28 L34 14 Q38 10 46 10 L78 10 Q86 10 90 16 L100 28 Q114 30 112 44 Z" fill="#7cc4ff" stroke="#1b2550" strokeWidth="4" strokeLinejoin="round" />
      <path d="M40 16 L50 16 L50 28 L30 28 Z M56 16 L76 16 Q80 16 83 20 L89 28 L56 28 Z" fill="#eef7ff" stroke="#1b2550" strokeWidth="3" strokeLinejoin="round" />
      <circle cx="32" cy="46" r="10" fill="#1b2550" /><circle cx="32" cy="46" r="4" fill="#d9dce8" />
      <circle cx="90" cy="46" r="10" fill="#1b2550" /><circle cx="90" cy="46" r="4" fill="#d9dce8" />
      <rect x="104" y="32" width="6" height="5" rx="2" fill="#f7c63d" />
    </svg>
  );
}
function Apartment() {
  const windows = [0, 1, 2, 3, 4].flatMap((r) => [0, 1, 2].map((c) => ({ x: 14 + c * 18, y: 16 + r * 18, lit: (r + c) % 3 === 0 })));
  return (
    <svg viewBox="0 0 120 130" className="h-full w-full" aria-hidden>
      <rect x="76" y="40" width="38" height="86" rx="4" fill="#cfd9ff" stroke="#1b2550" strokeWidth="4" />
      {[0, 1, 2].map((r) => <rect key={r} x="86" y={52 + r * 22} width="18" height="10" rx="2" fill="#f7e7a8" stroke="#1b2550" strokeWidth="2" />)}
      <rect x="6" y="6" width="70" height="120" rx="5" fill="#ffd9e2" stroke="#1b2550" strokeWidth="4" />
      {windows.map((w) => <rect key={`${w.x}-${w.y}`} x={w.x} y={w.y} width="12" height="10" rx="2" fill={w.lit ? "#ffe58a" : "#eef7ff"} stroke="#1b2550" strokeWidth="2" />)}
      <rect x="32" y="104" width="16" height="22" rx="3" fill="#a77b5b" stroke="#1b2550" strokeWidth="3" />
    </svg>
  );
}

function Bag() {
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden>
      <path d="M20 26 Q20 6 32 6 Q44 6 44 26" fill="none" stroke="#1b2550" strokeWidth="5" strokeLinecap="round" />
      <path d="M8 24 L56 24 L60 56 Q60 60 56 60 L8 60 Q4 60 4 56 Z" fill="#ff8fb8" stroke="#1b2550" strokeWidth="4" strokeLinejoin="round" />
      <path d="M6 36 L58 36" stroke="#1b2550" strokeWidth="3" />
      <rect x="25" y="31" width="14" height="11" rx="3" fill="#f7c63d" stroke="#1b2550" strokeWidth="3" />
    </svg>
  );
}

/** 진화 단계 그림 하나(후광·명품백·자동차·아파트 포함) */
export function HayangFigure({ stage, outfit, size = "md", className = "" }: { stage: HayangStage; outfit: Outfit; size?: "sm" | "md" | "lg"; className?: string }) {
  const box = size === "lg" ? "h-56 w-44" : size === "sm" ? "h-24 w-[4.7rem]" : "h-36 w-28";
  // 자동차(왼쪽)·아파트(오른쪽)가 그림 밖으로 나가므로 그만큼 자리를 비워 둬 옆 글자를 가리지 않게 한다
  const width = size === "lg" ? 176 : size === "sm" ? 75 : 112;
  const room = { marginLeft: stage >= 4 ? Math.round(width * 0.4) : 0, marginRight: stage >= 5 ? Math.round(width * 0.5) : 0 };
  return (
    <div className={`hayang relative shrink-0 ${box} ${className}`} style={room} data-stage={stage}>
      {stage >= 5 && <div className="absolute -right-[46%] bottom-[8%] h-[80%] w-[70%]"><Apartment /></div>}
      {stage >= 2 && <div className="hayang-halo absolute left-1/2 top-[-14%] aspect-square w-[160%] -translate-x-1/2 rounded-full" />}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={hayangImage(stage, outfit)} alt="" title="가톨릭대학교 캐릭터 하양이" className="relative h-full w-full object-contain drop-shadow-[0_6px_10px_rgb(0_0_0/0.35)]" />
      {stage >= 3 && <div className="absolute right-[2%] bottom-[4%] h-[24%] w-[30%]"><Bag /></div>}
      {stage >= 4 && <div className="absolute -left-[38%] bottom-0 h-[26%] w-[66%]"><Car /></div>}
    </div>
  );
}

const STAGE_TITLE_ID: Record<HayangStage, string | null> = { 1: null, 2: "job", 3: "bag", 4: "car", 5: "home" };

/** 전체 화면 진화 연출: 이전·새 모습이 흰 실루엣으로 번갈아 깜박이다가 섬광과 함께 새 모습이 드러난다 */
export function EvolutionOverlay({ from, to, outfit, newTitle, onClose }: {
  from: HayangStage; to: HayangStage; outfit: Outfit; newTitle?: Title; onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return createPortal(
    <div className="evo fixed inset-0 z-50 grid place-items-center bg-paper/90 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="하양이 진화" onClick={onClose}>
      <div className="flex flex-col items-center gap-4 px-4 text-center" onClick={(e) => e.stopPropagation()}>
        <p className="evo-intro font-display text-lg text-go">어라…? 하양이의 모습이…!</p>
        <div className="relative grid h-72 w-72 place-items-center">
          <span className="evo-ring absolute inset-0 rounded-full" />
          <span className="evo-ring evo-ring-2 absolute inset-0 rounded-full" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={hayangImage(from, outfit)} alt="" className="evo-old absolute h-64 object-contain" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={hayangImage(to, outfit)} alt="" className="evo-new absolute h-64 object-contain" />
          <div className="evo-final absolute"><HayangFigure stage={to} outfit={outfit} size="lg" /></div>
          <span className="evo-flash pointer-events-none absolute -inset-[50%] rounded-full" />
        </div>
        <div className="evo-text space-y-2">
          <p className="text-xl font-bold">축하해요! {stageTitle(from, outfit)}는<br /><span className="text-gold">{stageTitle(to, outfit)}</span>로 진화했어요!</p>
          {newTitle && <p className="text-sm">{newTitle.earned ? "새 칭호 획득" : "진화하면 얻는 칭호"} <TitleBadge title={newTitle} /></p>}
          <button className="btn-gold mt-2" onClick={onClose} autoFocus>확인</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function TitleBadge({ title }: { title: Title }) {
  return <span className={`title-badge title-${title.rarity}`} title={`${RARITY_LABEL[title.rarity]} 칭호 · ${title.how}`}>[{RARITY_LABEL[title.rarity]}] {title.name}</span>;
}

/** 이 브라우저에 증빙을 첨부해 둔 노드 id. 증빙이 바뀌면 다시 읽는다 */
function useProofSkills(owner?: string) {
  const [skills, setSkills] = useState<string[]>([]);
  useEffect(() => {
    if (!owner) return;
    const load = () => { listProofs(owner).then((all) => setSkills(Object.keys(all))).catch(() => setSkills([])); };
    load();
    window.addEventListener(PROOFS_CHANGED, load);
    return () => window.removeEventListener(PROOFS_CHANGED, load);
  }, [owner]);
  return skills;
}

/** 지금 프로필의 칭호 목록과 장착 칭호 */
export function useTitles() {
  const s = useStore();
  const p = s.profile;
  const tree = useMemo(() => s.careerPath?.tree ?? [], [s.careerPath]);
  const proofSkills = useProofSkills(p?.pseudoId);
  // 인증으로 치는 것: 완료한 노드에 붙인 증빙
  const proofs = useMemo(() => tree.filter((n) => n.state !== "none" && proofSkills.includes(n.skill)).length, [tree, proofSkills]);
  const evo = useMemo(() => evolution(tree, proofs), [tree, proofs]);
  const pct = evo.pct;
  const titles = useMemo(() => {
    if (!p) return [];
    const weights = nodeWeights(tree);
    const core = new Set([...weights].filter(([, w]) => w.tier === 3).map(([skill]) => skill));
    return titlesFor({ tree, pct, outfit: outfitFor(p.jobId, careerInterestOf(p) === "startup"), questsStarted: s.followed.length, coreSkills: core, proofs });
  }, [p, tree, pct, s.followed.length, proofs]);
  return { titles, equipped: titles.length ? equippedTitle(titles, p?.title) : undefined, evolution: evo, proofs };
}

export function EquippedTitle() {
  const { equipped } = useTitles();
  return equipped ? <TitleBadge title={equipped} /> : null;
}

/** 스킬트리 노드를 완료할수록 진화하는 하양이. 단계가 오르면 전체 화면 진화 연출을 한 번 보여 준다 */
export function Hayang({ owner, jobId, startup, size = "md" }: {
  owner: string; jobId: string; startup?: boolean; size?: "md" | "lg";
}) {
  const outfit = outfitFor(jobId, startup);
  const { titles, evolution: evo } = useTitles();
  const stage = evo.stage;
  const [evolution, setEvolution] = useState<{ from: HayangStage; to: HayangStage } | null>(null);
  useEffect(() => {
    // 이 브라우저에서 마지막으로 본 단계보다 올라갔으면 진화 연출. 저장소를 못 쓰면 연출만 생략한다
    const key = `hayang-stage:${owner}`;
    try {
      const seen = Number(localStorage.getItem(key) ?? stage) as HayangStage;
      localStorage.setItem(key, String(stage));
      if (stage > seen) {
        const t = window.setTimeout(() => setEvolution({ from: seen, to: stage }), 0);
        return () => window.clearTimeout(t);
      }
    } catch { /* 저장소 없음 */ }
  }, [owner, stage]);
  const newTitle = evolution ? titles.find((t) => t.id === STAGE_TITLE_ID[evolution.to]) : undefined;

  return (
    <figure className="flex shrink-0 flex-col items-center" aria-label={`${stageTitle(stage, outfit)}, 진화 ${stage}단계`}>
      <Link href="/hayang" aria-label="하양이 도감 열기"><HayangFigure stage={stage} outfit={outfit} size={size} /></Link>
      <figcaption className="mt-1 text-center text-[11px] leading-tight">
        <span className="block font-bold">{stageTitle(stage, outfit)}</span>
        <span className="text-ink/60">{evo.toNext === null ? "최종 진화 완료" : evo.toNext === 0 ? `내 집 마련까지 증빙 인증 ${evo.proofsNeeded}개` : `다음 진화까지 노드 ${evo.toNext}개${evo.proofsNeeded ? ` + 인증 ${evo.proofsNeeded}개` : ""}`}</span>
      </figcaption>
      {evolution && <EvolutionOverlay {...evolution} outfit={outfit} newTitle={newTitle} onClose={() => setEvolution(null)} />}
    </figure>
  );
}

/** 넓은 화면 왼쪽 기둥: 하양이와 칭호, 진화 진행도 */
export function HayangRail() {
  const s = useStore();
  const mounted = useMounted();
  const p = mounted ? s.profile : null;
  const { equipped, evolution: evo } = useTitles();
  if (!p) return null;
  return (
    <div className="window sticky top-20 flex flex-col items-center gap-3 px-3 py-5 text-center">
      <Hayang owner={p.pseudoId} jobId={p.jobId} startup={careerInterestOf(p) === "startup"} />
      {equipped && <TitleBadge title={equipped} />}
      <div className="w-full space-y-1">
        <div className="h-2 overflow-hidden rounded-full bg-line">
          <div className="h-full bg-gradient-to-r from-go to-gold transition-all" style={{ width: `${evo.pct}%` }} />
        </div>
        <p className="text-[11px] text-ink/60">노드 {evo.done}/{evo.total} 완료</p>
      </div>
      <Link href="/hayang" className="btn-ghost w-full !py-1 text-xs">하양이 도감 · 칭호</Link>
    </div>
  );
}
