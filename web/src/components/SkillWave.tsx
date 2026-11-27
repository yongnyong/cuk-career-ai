"use client";
import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { EMPLOYMENT_SECTIONS, STARTUP_SECTIONS, employmentSection, startupSection, type TreeMode } from "@/lib/treeProgression";
import { Star } from "lucide-react";
import type { TreeNode } from "@/lib/engine";
import { nodeStatus } from "@/components/quest-ui";
import { questOutcome } from "@/lib/questOutcome";
import { assignSemesters, SEMESTERS, type WeightTier } from "@/lib/treeRadial";

const STARTUP_LABELS = STARTUP_SECTIONS;
const W = 1000;
const H = 800;
const CX = W / 2;
const CY = H / 2;
const R0 = 130; // 막대가 시작하는 안쪽 원
const LENGTH: Record<WeightTier, number> = { 1: 48, 2: 84, 3: 132 }; // 막대 길이 = 중요도

const GAP = 0.1; // 학기 칸 사이 여백(rad)
const COLOR = { done: "#2fd39a", go: "#46a6ff", check: "#e6bd52", lock: "#5f6690", late: "#ff8a5b" } as const;


const deg = (rad: number) => (rad * 180) / Math.PI;


type Bar = { node: TreeNode; slot: number; angle: number; length: number; width: number; tier: WeightTier };

/** 원형 파형 스킬트리. 막대 하나가 노드, 길이가 중요도, 바늘이 보고 있는 학기다 */
export function SkillWave({ tree, weights, current, title, subtitle, recommended, onPick, mode = "employment" }: {
  mode?: TreeMode;
  tree: TreeNode[];
  weights: Map<string, { tier: WeightTier }>;
  current: number;
  title: string;
  subtitle: string;
  recommended?: string;
  onPick: (skill: string) => void;
}) {
  const labels = mode === "startup" ? STARTUP_LABELS : SEMESTERS;
  const SLOT = (2 * Math.PI) / labels.length;
  const slotAngle = (slot: number) => -Math.PI / 2 + slot * SLOT;
  const termLabel = (slot: number) => mode === "startup" ? labels[slot] : `${SEMESTERS[slot][0]}학년 ${SEMESTERS[slot][2]}학기`;
  const [needle, setNeedle] = useState(current);
  const [zoom, setZoom] = useState<{ skill: string; origin: string } | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const dragging = useRef(false);

  const bars = useMemo(() => {
    const slots = mode === "startup" ? new Map(tree.map(node => [node.skill, STARTUP_SECTIONS.indexOf(startupSection(node))])) : assignSemesters(tree);
    const result: Bar[] = [];
    labels.forEach((_, slot) => {
      const nodes = tree.filter((n) => slots.get(n.skill) === slot)
        .sort((a, b) => (weights.get(b.skill)?.tier ?? 2) - (weights.get(a.skill)?.tier ?? 2));
      // 파형처럼 큰 막대를 칸 가운데에 두고 양옆으로 작아지게 놓는다
      const arranged: TreeNode[] = [];
      nodes.forEach((n, i) => (i % 2 ? arranged.push(n) : arranged.unshift(n)));
      const span = SLOT - GAP;
      const step = span / Math.max(arranged.length, 1);
      arranged.forEach((node, i) => {
        const tier = weights.get(node.skill)?.tier ?? 2;
        result.push({
          node, slot, tier,
          angle: -Math.PI / 2 + slot * SLOT + GAP / 2 + step * (i + 0.5),
          length: LENGTH[tier],
          width: Math.max(5, Math.min(13, R0 * step * 0.5)),
        });
      });
    });
    return result;
  }, [tree, weights, mode, SLOT, labels]);
  // 지난 학기 칸인데 아직 안 한 노드는 '밀린 노드'
  const colorOf = (bar: Bar) => {
    const status = nodeStatus(bar.node);
    return status !== "done" && bar.slot < current ? "late" : status;
  };

  const inSlot = bars.filter((b) => b.slot === needle);
  const done = tree.filter((n) => !n.groupChildren && n.state !== "none").length;

  const angleToSlot = (e: PointerEvent<SVGSVGElement>) => {
    const box = svg.current!.getBoundingClientRect();
    const x = ((e.clientX - box.left) / box.width) * W - CX;
    const y = ((e.clientY - box.top) / box.height) * H - CY;
    const turned = (Math.atan2(y, x) + Math.PI / 2 + 2 * Math.PI) % (2 * Math.PI);
    return Math.floor(turned / SLOT) % labels.length;
  };
  const pick = (bar: Bar) => {
    if (zoom) return;
    const tip = R0 + bar.length / 2;
    const x = CX + Math.cos(bar.angle) * tip, y = CY + Math.sin(bar.angle) * tip;
    setZoom({ skill: bar.node.skill, origin: `${(x / W) * 100}% ${(y / H) * 100}%` });
    // 트리 화면은 자세히 보기로 넘어가며 사라지고, 트리 만들기 화면은 그대로 남으니 확대를 되돌린다
    window.setTimeout(() => { onPick(bar.node.skill); setZoom(null); }, 330);
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") setNeedle((s) => (s + 1) % labels.length);
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") setNeedle((s) => (s + labels.length - 1) % labels.length);
  };

  return (
    <div className="relative h-full overflow-hidden">
      <div className={`wave-stage h-full ${zoom ? "wave-zoom" : ""}`} style={zoom ? { transformOrigin: zoom.origin } : undefined}>
        <svg
          ref={svg}
          viewBox={`0 0 ${W} ${H}`}
          className="h-full w-full touch-none select-none outline-none"
          role="slider"
          aria-label={mode === "startup" ? "준비 단계 선택" : "볼 학기 선택"}
          aria-valuemin={0}
          aria-valuemax={labels.length - 1}
          aria-valuenow={needle}
          aria-valuetext={termLabel(needle)}
          tabIndex={0}
          onKeyDown={onKey}
          onPointerDown={(e) => { if ((e.target as Element).closest("[data-bar]")) return; dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); setNeedle(angleToSlot(e)); }}
          onPointerMove={(e) => { if (dragging.current) setNeedle(angleToSlot(e)); }}
          onPointerUp={() => { dragging.current = false; }}
        >
          <defs>
            <radialGradient id="wave-glow">
              <stop offset="0%" stopColor="#46a6ff" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#46a6ff" stopOpacity="0" />
            </radialGradient>
          </defs>
          <circle cx={CX} cy={CY} r={R0 + 170} fill="url(#wave-glow)" />
          {/* 지난 학기 = 이미 녹음된 구간 */}
          {labels.map((label, slot) => {
            const a0 = slotAngle(slot) + GAP / 2, a1 = slotAngle(slot + 1) - GAP / 2;
            const r1 = R0 - 6, r2 = R0 + LENGTH[3] + 14;
            const p = (r: number, a: number) => `${CX + Math.cos(a) * r} ${CY + Math.sin(a) * r}`;
            const mid = (a0 + a1) / 2;
            const past = slot < current;
            return (
              <g key={label}>
                <path d={`M ${p(r1, a0)} A ${r1} ${r1} 0 0 1 ${p(r1, a1)} L ${p(r2, a1)} A ${r2} ${r2} 0 0 0 ${p(r2, a0)} Z`}
                  fill={slot === needle ? "rgb(70 166 255 / 0.10)" : past ? "rgb(47 211 154 / 0.06)" : "transparent"}
                  stroke={slot === needle ? "rgb(70 166 255 / 0.5)" : "#262b52"} />
                <text x={CX + Math.cos(mid) * (r2 + 26)} y={CY + Math.sin(mid) * (r2 + 26)} textAnchor="middle" dominantBaseline="middle"
                  className="cursor-pointer" fontSize={mode === "startup" ? 13 : slot === needle ? 20 : 16} fontWeight={slot === needle ? 700 : 400}
                  fill={slot === needle ? "#46a6ff" : slot === current ? "#ecebff" : "#8d92bd"} onClick={() => setNeedle(slot)}>
                  {label}{slot === current ? " · 지금" : ""}
                </text>
              </g>
            );
          })}
          {/* 막대가 없는 칸에도 잔물결을 그려 파형처럼 보이게 한다(장식) */}
          <g aria-hidden>
            {Array.from({ length: 96 }, (_, i) => {
              const a = -Math.PI / 2 + (i + 0.5) * (2 * Math.PI / 96);
              return <line key={i} x1={CX + Math.cos(a) * (R0 - 2)} y1={CY + Math.sin(a) * (R0 - 2)}
                x2={CX + Math.cos(a) * (R0 + 6 + (i * 7) % 9)} y2={CY + Math.sin(a) * (R0 + 6 + (i * 7) % 9)} stroke="#2f3560" strokeWidth={2} strokeLinecap="round" />;
            })}
          </g>
          {bars.map((bar, i) => {
            const status = colorOf(bar);
            const active = bar.slot === needle;
            const name = bar.node.state === "none" ? questOutcome(bar.node)?.title ?? bar.node.name : bar.node.name;
            return (
              <g key={bar.node.skill} data-bar transform={`rotate(${deg(bar.angle) + 90} ${CX} ${CY})`} className="cursor-pointer" onClick={() => pick(bar)}
                role="button" aria-label={`${name}, ${termLabel(bar.slot)}`}>
                <title>{name}</title>
                <rect className="wave-bar" style={{ animationDelay: `${i * 25}ms` }}
                  x={CX - bar.width / 2} y={CY - R0 - bar.length} width={bar.width} height={bar.length} rx={bar.width / 2}
                  fill={status === "lock" ? "transparent" : COLOR[status]} stroke={status === "lock" ? COLOR.lock : bar.tier === 3 ? "#f7c63d" : "none"}
                  strokeWidth={status === "lock" ? 2 : 2.5} strokeDasharray={status === "lock" ? "4 3" : undefined}
                  opacity={active ? 1 : 0.38} />
                {bar.node.skill === recommended && <circle cx={CX} cy={CY - R0 - bar.length - 12} r={5} fill="#46a6ff" />}
                {bar.tier === 3 && active && <circle cx={CX} cy={CY - R0 - bar.length - 12} r={4} fill="#f7c63d" />}
              </g>
            );
          })}
          {/* 바늘: 지금 보고 있는 학기 */}
          <g className="wave-needle pointer-events-none" style={{ transform: `rotate(${deg(slotAngle(needle) + SLOT / 2) + 90}deg)`, transformOrigin: `${CX}px ${CY}px` }}>
            <line x1={CX} y1={CY - R0 + 8} x2={CX} y2={CY - R0 - LENGTH[3] - 4} stroke="#ecebff" strokeWidth={2} />
            <circle cx={CX} cy={CY - R0 - LENGTH[3] - 8} r={6} fill="#ecebff" />
          </g>
          <circle cx={CX} cy={CY} r={R0 - 14} fill="#07081a" stroke="#46a6ff" strokeWidth={2} />
          <text x={CX} y={CY - 30} textAnchor="middle" fontSize={15} fill="#46a6ff">{subtitle}</text>
          <text x={CX} y={CY + 2} textAnchor="middle" fontSize={title.length > 8 ? 20 : 24} fontWeight={700} fill="#ecebff">{title}</text>
          <text x={CX} y={CY + 34} textAnchor="middle" fontSize={15} fill="#8d92bd">완료 {done} / {tree.filter(node => !node.groupChildren).length}</text>
        </svg>
      </div>
      {/* 바늘이 가리키는 학기의 노드 이름. 글씨는 여기서만 크게 읽는다 */}
      <div className="absolute left-3 top-3 w-56 rounded-md border border-line bg-panel/90 p-3 text-xs backdrop-blur">
        <p className="font-bold text-go">{termLabel(needle)}{needle === current && " · 지금"} <span className="font-normal text-ink/60">{inSlot.length}개</span></p>
        <p className="mt-0.5 text-[11px] text-ink/60">{mode === "startup" ? "제품과 팀 상황에 따라 필요한 퀘스트를 선택해요" : needle < current ? "지난 학기 권장 노드 · 주황은 밀린 노드(지금 해도 돼요)" : "이 시기에 권장하는 노드 · 시기는 준비 단계 순서로 추정"}</p>
        <ul className="mt-2 space-y-1">
          {inSlot.length === 0 && <li className="text-ink/60">이 구간에 배치된 퀘스트가 없어요</li>}
          {[...inSlot].sort((a, b) => mode === "employment" ? EMPLOYMENT_SECTIONS.indexOf(employmentSection(a.node)) - EMPLOYMENT_SECTIONS.indexOf(employmentSection(b.node)) || (a.node.credentialPriority?.rank ?? 2) - (b.node.credentialPriority?.rank ?? 2) : b.tier - a.tier).map((bar) => {
            const status = colorOf(bar);
            return (
              <li key={bar.node.skill}>
                <button className="flex w-full items-center gap-1.5 text-left hover:underline" onClick={() => pick(bar)}>
                  <span className="size-2.5 shrink-0 rounded-full" style={{ background: status === "lock" ? "transparent" : COLOR[status], border: `1.5px solid ${COLOR[status]}` }} />
                  {mode === "employment" && <span className="shrink-0 text-[10px] text-ink/60">{employmentSection(bar.node)}</span>}
                  <span className={bar.tier === 3 ? "font-bold text-gold" : ""}>{bar.node.name}</span>
                  {bar.node.credentialPriority && <span className="shrink-0 text-[10px] text-go">{bar.node.credentialPriority.label}</span>}
                  {bar.tier === 3 && <Star size={10} className="shrink-0 text-gold" fill="currentColor" />}
                  {bar.node.skill === recommended && <span className="shrink-0 text-[10px] font-bold text-go">추천</span>}
                  {status === "late" && <span className="shrink-0 text-[10px] font-bold" style={{ color: COLOR.late }}>밀림</span>}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      <p className="pointer-events-none absolute bottom-2 right-3 text-[11px] text-ink/60">바늘을 돌려 구간 선택 · 막대를 누르면 퀘스트를 볼 수 있어요</p>
    </div>
  );
}
