"use client";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Play, RotateCcw, Sparkles, X } from "lucide-react";
import { useStore } from "@/lib/store";
import { jobById } from "@/lib/data/catalog";
import { careerInterestOf } from "@/lib/interest";
import { outfitFor, stageTitle } from "@/lib/hayang";
import { layoutRadial, nodeWeights, RADIAL_RX, RADIAL_RY } from "@/lib/treeRadial";
import { progressionStage } from "@/lib/treeProgression";
import { recommendedTitle } from "@/lib/questOutcome";
import { replayScript, replayState } from "@/lib/growthReplay";
import type { TreeNode } from "@/lib/engine";
import { HayangFigure } from "@/components/Hayang";

const RADIUS = { 1: 11, 2: 15, 3: 21 } as const;

function Replay({ tree, onClose }: { tree: TreeNode[]; onClose: () => void }) {
  const s = useStore();
  const p = s.profile!;
  const mode = careerInterestOf(p) === "startup" ? "startup" : "employment";
  const outfit = outfitFor(p.jobId, mode === "startup");
  const doneCount = tree.filter((n) => n.state !== "none").length;
  // 완료한 노드가 거의 없으면 밋밋하니 완성 미리보기부터 보여 준다
  const [full, setFull] = useState(doneCount < 3);
  const [index, setIndex] = useState(0);
  const events = useMemo(() => replayScript(tree, full), [tree, full]);
  const layout = useMemo(() => layoutRadial(tree), [tree]);
  const weights = useMemo(() => nodeWeights(tree), [tree]);
  const state = replayState(events, index);
  const lit = new Set(state.lit);
  const ended = state.current.type === "end";

  useEffect(() => {
    if (index >= events.length - 1) return;
    const t = window.setTimeout(() => setIndex((i) => i + 1), events[index].ms);
    return () => window.clearTimeout(t);
  }, [index, events]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const restart = (nextFull: boolean) => { setFull(nextFull); setIndex(0); };
  const w = (layout.outer + 95) * RADIAL_RX, h = (layout.outer + 80) * RADIAL_RY;
  const exp = tree.filter((n) => lit.has(n.skill)).reduce((sum, n) => sum + (full || n.state === "verified" ? 100 : 60), 0);
  const pct = Math.round((exp / (tree.length * 100 || 1)) * 100);
  const quest = s.careerPath?.recommendedQuest;
  const questNode = quest && tree.find((n) => n.skill === quest.skillId);
  const nextTitle = questNode && quest ? recommendedTitle(questNode, quest) : tree.find((n) => n.state === "none" && !n.locked)?.name;
  const evolving = state.current.type === "evolve" ? state.current : null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex flex-col bg-paper/95 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="성장 재생">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
        <p className="font-display leading-none"><span className="text-sm">Lv.</span><span className="text-4xl">{1 + Math.floor(exp / 40)}</span></p>
        <div className="min-w-40 flex-1">
          <p className="text-sm font-bold">{full ? "완성 미리보기" : "지금까지의 성장"} · {jobById(p.jobId)?.name ?? "목표 직무"}</p>
          <div className="exp mt-1"><div className="h-full bg-gradient-to-r from-go to-gold transition-all duration-300" style={{ width: `${pct}%` }} /></div>
          <p className="mt-0.5 text-[11px] text-ink/60">노드 {lit.size}/{tree.length} · 준비 단계 순서로 재생해요(실제 완료한 날짜 순서가 아니에요)</p>
        </div>
        <button className="btn-ghost !px-2 !py-1" onClick={onClose} aria-label="닫기"><X size={16} /></button>
      </div>

      <div className="relative min-h-0 flex-1">
        <svg viewBox={`${-w} ${-h} ${2 * w} ${2 * h}`} className="h-full w-full" aria-hidden>
          {layout.rings.map((ring, i) => state.rings.includes(ring.stage) && (
            <g key={ring.stage} className="grow-ring">
              <ellipse rx={ring.r * RADIAL_RX} ry={ring.r * RADIAL_RY} fill="rgb(124 108 255 / 0.05)" stroke="#4a5596" strokeDasharray="4 6" />
              <text y={-ring.r * RADIAL_RY - 6} textAnchor="middle" fontSize={12} fontWeight={700} fill="#b9c2ff">{i + 1}단계 · {progressionStage(ring.stage, mode).title}</text>
            </g>
          ))}
          {tree.flatMap((n) => n.prereq.map((parent) => {
            const a = layout.positions.get(parent), b = layout.positions.get(n.skill);
            return a && b && lit.has(parent) && lit.has(n.skill) && <line key={`${parent}-${n.skill}`} className="grow-edge" x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#7c6cff" strokeWidth={2.5} pathLength={1} />;
          }))}
          {tree.map((n) => {
            const at = layout.positions.get(n.skill);
            if (!at) return null;
            const tier = weights.get(n.skill)?.tier ?? 2;
            const r = RADIUS[tier];
            const on = lit.has(n.skill);
            const color = tier === 3 ? "#f7c63d" : "#2fd39a";
            return (
              <g key={n.skill} transform={`translate(${at.x} ${at.y})`}>
                {on
                  ? <g className="grow-node"><circle r={r + 7} fill={color} opacity={0.22} /><circle r={r} fill={color} stroke="#fff" strokeWidth={2} /></g>
                  : <circle r={r} fill="#11132b" stroke="#3d4680" strokeDasharray="3 4" opacity={ended ? 0.9 : 0.45} />}
                {(on || ended) && <text y={r + 15} textAnchor="middle" fontSize={11} fontWeight={on ? 700 : 400} fill={on ? "#ecebff" : "#8087b3"}>{n.name.length > 13 ? n.name.slice(0, 12) + "…" : n.name}</text>}
              </g>
            );
          })}
          <g>
            <ellipse rx={66} ry={26} fill="#07081a" stroke="#46a6ff" strokeWidth={2.5} />
            <text y={5} textAnchor="middle" fontSize={14} fontWeight={700} fill="#ecebff">{jobById(p.jobId)?.name ?? "목표 직무"}</text>
          </g>
        </svg>

        <div key={state.stage} className={`absolute bottom-3 left-4 flex flex-col items-center ${state.stage > 1 ? "grow-evolve" : ""}`}>
          <HayangFigure stage={state.stage} outfit={outfit} size="md" />
          <p className="mt-1 text-xs font-bold">{stageTitle(state.stage, outfit)}</p>
        </div>
        {evolving && <p className="grow-banner absolute inset-x-0 top-6 text-center font-display text-2xl text-gold">하양이 진화! {stageTitle(evolving.to, outfit)}</p>}
        {state.current.type === "node" && <p key={state.current.skill} className="grow-caption absolute inset-x-0 bottom-4 text-center text-lg font-bold">✓ {state.current.name}</p>}
        {state.current.type === "intro" && <p className="grow-caption absolute inset-x-0 bottom-4 text-center text-lg font-bold">빈 트리에서 시작했어요</p>}

        {ended && (
          <div className="grow-caption absolute inset-x-0 bottom-4 mx-auto flex w-fit max-w-[92%] flex-col items-center gap-2 rounded-lg border-2 border-edge bg-panel px-4 py-3 text-center">
            <p className="font-bold">{full ? `전부 채우면 이런 모습이에요 · 지금은 ${doneCount}/${tree.length}` : `여기까지 노드 ${lit.size}개를 쌓았어요`}</p>
            {nextTitle && <p className="unlock rounded-md border border-go px-2 py-1 text-sm">다음 퀘스트: <b className="text-go">{nextTitle}</b></p>}
            <div className="flex flex-wrap justify-center gap-2">
              <button className="btn-ghost !py-1 text-sm" onClick={() => restart(full)}><RotateCcw size={14} /> 다시 보기</button>
              <button className="btn-ghost !py-1 text-sm" onClick={() => restart(!full)}><Sparkles size={14} /> {full ? "지금까지의 성장 보기" : "완성 미리보기"}</button>
              <button className="btn-gold !py-1 text-sm" onClick={onClose}>닫기</button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

/** 빈 트리에서 지금 트리까지 쌓이는 과정을 전체 화면으로 재생하는 버튼 */
export function GrowthReplayButton({ className = "btn-ghost" }: { className?: string }) {
  const s = useStore();
  const [open, setOpen] = useState(false);
  const tree = s.careerPath?.tree ?? [];
  if (!s.profile || tree.length === 0) return null;
  return <>
    <button className={className} onClick={() => setOpen(true)}><Play size={14} /> 성장 재생</button>
    {open && <Replay tree={tree} onClose={() => setOpen(false)} />}
  </>;
}
