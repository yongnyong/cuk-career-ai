"use client";
import { Check, KeyRound, Lock, Star, Swords } from "lucide-react";
import { dday, progress, type TreeNode } from "@/lib/engine";
import { formatScore, jobById } from "@/lib/data/catalog";
import { getDepartment } from "@/lib/data/departments";
import type { Profile } from "@/lib/types";
import { careerInterestOf } from "@/lib/interest";
import { questOutcome } from "@/lib/questOutcome";
import { EquippedTitle, Hayang } from "@/components/Hayang";

// 노드 상태 3가지 + 기회 열림. 색·아이콘·글자를 항상 같이 쓴다.
const STATUS = {
  done: { label: "완료", icon: Check, box: "border-ok shadow-[0_0_14px_rgb(47_211_154/0.35)]", badge: "bg-ok text-white" },
  go: { label: "지금 도전", icon: Swords, box: "border-go shadow-[0_0_14px_rgb(70_166_255/0.45)]", badge: "bg-go text-white" },
  lock: { label: "잠김", icon: Lock, box: "border-dashed border-lock text-lock", badge: "bg-slate-200 text-slate-400" },
  check: { label: "응시요건 준비·확인", icon: KeyRound, box: "border-line", badge: "bg-slate-100 text-slate-600" },
} as const;

export const nodeStatus = (n: TreeNode) => (n.state !== "none" ? "done" : n.locked ? "lock"
  : n.credentialEligibility && n.credentialEligibility.status !== "ready" ? "check" : "go");

// 중요도 크기: 1 작게, 2 보통, 3 크게(먼저 찍을 노드)
const WEIGHT_BOX = { 1: "w-44 opacity-90", 2: "w-48", 3: "w-[216px] ring-2 ring-gold/70" } as const;

// 방사형 전체 보기용 원형 노드(최대 112×86px). 원 크기가 중요도이고, 상세는 노드를 눌러 본다
export const COMPACT_DIAMETER = { 1: 30, 2: 40, 3: 54 } as const;

export function NodeBox({ node, isNew, now, proof, recommended, weight, compact }: {
  node: TreeNode; isNew?: boolean; now: Date; proof?: boolean; recommended?: boolean; weight?: 1 | 2 | 3; compact?: boolean;
}) {
  const st = STATUS[nodeStatus(node)];
  const outcome = questOutcome(node);
  const title = node.state === "none" || proof ? outcome?.title ?? node.name : node.name;
  const opps = node.opportunities;
  const soonest = opps.length ? Math.min(...opps.map((o) => dday(o, now))) : null;
  const hasPosting = node.evidence?.some(s => s.reference.scope === "role" && (s.basis === "required" || s.basis === "preferred"));
  const credential = node.kind === "자격증" || node.kind === "어학";
  const source = credential ? outcome?.label : node.startup ? '창업 공고 근거' : hasPosting ? "공고 근거" : node.practice ? "직무 연습" : node.evidence?.some(s => s.basis === "activity") ? "연계 활동" : undefined;
  if (compact) {
    const size = COMPACT_DIAMETER[weight ?? 2];
    return (
      <div title={title} className="flex w-28 flex-col items-center text-center">
        <span style={{ width: size, height: size }} className={`relative grid place-items-center rounded-full border-2 ${st.box} ${st.badge} ${weight === 3 ? "ring-4 ring-gold/60" : ""} ${recommended ? "outline outline-2 outline-offset-4 outline-go" : ""} ${isNew ? "unlock" : ""}`}>
          {weight === 3 ? <Star size={22} fill="currentColor" /> : <st.icon size={size / 2.4} />}
          {opps.length > 0 && <span className="absolute -right-1 -top-1 grid size-4 place-items-center rounded-full bg-gold text-on-gold"><KeyRound size={9} /></span>}
        </span>
        <span className={`mt-1 line-clamp-2 leading-tight ${weight === 3 ? "text-[13px] font-bold text-gold" : weight === 1 ? "text-[11px] text-ink/75" : "text-xs font-semibold"}`}>{title}</span>
        {node.credentialPriority && <span className="text-[10px] text-go">{node.credentialPriority.label}</span>}
        {recommended && <span className="text-[10px] font-bold leading-none text-go">추천 퀘스트</span>}
      </div>
    );
  }
  return (
    <div className={`${WEIGHT_BOX[weight ?? 2]} overflow-hidden rounded-md border-2 bg-panel text-left ${st.box} ${isNew ? "unlock" : ""}`}>
      <div className={`flex items-center gap-2 px-2 ${weight === 3 ? "py-3" : "py-2"}`}>
        <span className={`grid size-7 shrink-0 place-items-center rounded ${st.badge}`}>
          <st.icon size={15} />
        </span>
        <span className="min-w-0">
          <span title={title} className={`block font-bold leading-tight ${weight === 3 ? "text-base" : "text-sm"}`}>{title}</span>
          {weight === 3 && <span className="flex items-center gap-0.5 text-[11px] font-bold text-gold"><Star size={11} fill="currentColor" /> 핵심 노드</span>}
          {recommended && <span className="block text-[11px] font-bold text-go">추천 퀘스트</span>}
          {node.state === "none" && node.credentialEligibility &&
            <span className="block text-[11px] text-go">{node.credentialEligibility.label}</span>}
          <span className="block text-[11px] opacity-70">
            {node.state === "none" ? st.label : node.score ? `완료 · ${formatScore(node.skill, node.score)}` : node.state === "verified" ? "완료 · 검증됨" : "완료 · 자기 보고"}
            {node.credentialPriority && ` · ${node.credentialPriority.label}`}
            {node.required ? " · 트랙 기본" : ""}
            {node.mine ? " · 내 노드" : ""}
            {source && ` · ${source}`}
            {proof ? " · 증빙 첨부" : ""}
          </span>
        </span>
      </div>
      {opps.length > 0 && (
        <div className="flex items-center gap-1 bg-gold px-2 py-1 text-[11px] font-bold text-on-gold">
          <KeyRound size={12} />
          {isNew ? "새 기회 열림" : `기회 ${opps.length}건`}
          <span className="ml-auto">D-{soonest === 0 ? "Day" : soonest}</span>
        </div>
      )}
    </div>
  );
}

export function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {Object.values(STATUS).map((s) => (
        <li key={s.label} className="flex items-center gap-1.5">
          <span className={`grid size-5 place-items-center rounded ${s.badge}`}>
            <s.icon size={12} />
          </span>
          {s.label}
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <span className="grid size-5 place-items-center rounded bg-gold text-on-gold">
          <KeyRound size={12} />
        </span>
        기회 열림
      </li>
    </ul>
  );
}

// 상태창: 내가 누구이고 어디까지 왔는지
export function StatusWindow({ profile, children, treeProgress }: {
  profile: Profile; children?: React.ReactNode; treeProgress?: ReturnType<typeof progress>;
}) {
  const job = jobById(profile.jobId);
  const dept = getDepartment(profile.departmentId);
  const prog = treeProgress ?? progress(profile);
  return (
    <section className="window p-4 sm:p-5">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <div className="2xl:hidden"><Hayang owner={profile.pseudoId} jobId={profile.jobId} startup={careerInterestOf(profile) === "startup"} /></div>
        <div className="font-display leading-none">
          <span className="text-lg">Lv.</span>
          <span className="text-5xl">{prog.level}</span>
        </div>
        <div className="min-w-52 flex-1">
          <p className="flex flex-wrap items-center gap-1.5 text-sm text-ink/65">
            <EquippedTitle /> {dept?.name} {profile.grade}학년 · {profile.pseudoId}
          </p>
          <h1 className="text-xl font-bold">{careerInterestOf(profile) === 'startup' ? '창업 준비' : `취업 · ${job?.name}`}</h1>
          <div className="mt-2 flex items-center gap-2">
            <div className="exp flex-1" role="progressbar" aria-valuenow={prog.pct} aria-valuemin={0} aria-valuemax={100} aria-label="경험치">
              <div className="h-full bg-gradient-to-r from-go to-edge transition-all" style={{ width: `${prog.pct}%` }} />
            </div>
            <span className="text-xs font-bold tabular-nums">EXP {prog.pct}%</span>
          </div>
        </div>
        {children}
      </div>
    </section>
  );
}
