"use client";
import { Check, KeyRound, Lock, Swords } from "lucide-react";
import { dday, progress, type TreeNode } from "@/lib/engine";
import { formatScore, jobById } from "@/lib/data/catalog";
import { getDepartment } from "@/lib/data/departments";
import type { Profile } from "@/lib/types";

// 노드 상태 3가지 + 기회 열림. 색·아이콘·글자를 항상 같이 쓴다.
const STATUS = {
  done: { label: "완료", icon: Check, box: "border-ok shadow-[0_0_14px_rgb(47_211_154/0.35)]", badge: "bg-ok text-white" },
  go: { label: "지금 도전", icon: Swords, box: "border-go shadow-[0_0_14px_rgb(70_166_255/0.45)]", badge: "bg-go text-white" },
  lock: { label: "잠김", icon: Lock, box: "border-dashed border-lock text-lock", badge: "bg-slate-200 text-slate-400" },
} as const;

export const nodeStatus = (n: TreeNode) => (n.state !== "none" ? "done" : n.locked ? "lock" : "go");

export function NodeBox({ node, isNew, now }: { node: TreeNode; isNew?: boolean; now: Date }) {
  const st = STATUS[nodeStatus(node)];
  const opps = node.opportunities;
  const soonest = opps.length ? Math.min(...opps.map((o) => dday(o, now))) : null;
  return (
    <div className={`w-48 overflow-hidden rounded-md border-2 bg-panel text-left ${st.box} ${isNew ? "unlock" : ""}`}>
      <div className="flex items-center gap-2 px-2 py-2">
        <span className={`grid size-7 shrink-0 place-items-center rounded ${st.badge}`}>
          <st.icon size={15} />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-bold leading-tight">{node.name}</span>
          <span className="block text-[11px] opacity-70">
            {node.state === "none" ? st.label : node.score ? `완료 · ${formatScore(node.skill, node.score)}` : node.state === "verified" ? "완료 · 검증됨" : "완료 · 자기 보고"}
            {node.required ? " · 필수" : ""}
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
export function StatusWindow({ profile, children }: { profile: Profile; children?: React.ReactNode }) {
  const job = jobById(profile.jobId);
  const dept = getDepartment(profile.departmentId);
  const prog = progress(profile);
  return (
    <section className="window p-4 sm:p-5">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <div className="font-display leading-none">
          <span className="text-lg">Lv.</span>
          <span className="text-5xl">{prog.level}</span>
        </div>
        <div className="min-w-52 flex-1">
          <p className="text-sm text-ink/65">
            {dept?.name} {profile.grade}학년 · {profile.pseudoId}
          </p>
          <h1 className="text-xl font-bold">목표: {job?.name}</h1>
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
