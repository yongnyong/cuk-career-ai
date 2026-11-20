"use client";
import { AlertTriangle, CheckCircle2, HelpCircle, Sparkles, XCircle } from "lucide-react";
import { fmt, dday } from "@/lib/engine";
import type { Opportunity, OppType, Verdict } from "@/lib/types";
import { latest } from "@/lib/engine";

export function AiNotice({ className = "" }: { className?: string }) {
  return (
    <p className={`flex items-center gap-1 text-xs text-slate-500 ${className}`}>
      <Sparkles size={12} /> AI가 정리한 정보이니 원문을 확인하세요.
    </p>
  );
}

export function VirtualTag() {
  return <span className="chip bg-violet-100 text-violet-700">가상 공고</span>;
}

const TYPE_COLOR: Record<OppType, string> = {
  현장실습: "bg-blue-100 text-blue-700",
  창업지원: "bg-orange-100 text-orange-700",
  채용: "bg-violet-100 text-violet-700",
  장학: "bg-emerald-100 text-emerald-700",
  학사: "bg-slate-200 text-slate-700",
  비교과: "bg-pink-100 text-pink-700",
};
export function TypeTag({ type }: { type: OppType }) {
  return <span className={`chip ${TYPE_COLOR[type]}`}>{type}</span>;
}

export function DDay({ opp, now }: { opp: Opportunity; now: Date }) {
  const d = dday(opp, now);
  if (opp.deadlineStatus === "unknown") return <span className="chip bg-slate-100 text-slate-600">기한 확인</span>;
  if (d < 0) return <span className="chip bg-slate-200 text-slate-500">마감</span>;
  return (
    <span className={`chip ${d <= 3 ? "bg-danger text-white" : d <= 7 ? "bg-orange-100 text-orange-700" : "bg-slate-100 text-slate-600"}`}>
      D-{d === 0 ? "Day" : d}
    </span>
  );
}

export function VerdictIcon({ v, size = 16 }: { v: Verdict; size?: number }) {
  if (v === "pass") return <CheckCircle2 size={size} className="text-ok" />;
  if (v === "fail") return <XCircle size={size} className="text-danger" />;
  return <HelpCircle size={size} className="text-warn" />;
}

export function VerdictBadge({ v }: { v: Verdict }) {
  const cls = v === "pass" ? "bg-emerald-50 text-ok" : v === "fail" ? "bg-red-50 text-danger" : "bg-amber-50 text-warn";
  const label = v === "pass" ? "명시 조건 충족" : v === "fail" ? "조건 미충족" : "확인 필요";
  return (
    <span className={`chip ${cls}`}>
      <VerdictIcon v={v} size={12} /> {label}
    </span>
  );
}

export function SourceLine({ opp }: { opp: Opportunity }) {
  const v = latest(opp);
  return (
    <p className="text-xs text-slate-500">
      출처:{" "}
      <a href={opp.source.url} target="_blank" rel="noreferrer" className="underline">
        {opp.source.name}
      </a>{" "}
      · 확인 {fmt(v.checkedAt)} · 버전 {v.version}
      {opp.isVirtual && " · 실제 모집이 아닌 시연용 가상 공고"}
    </p>
  );
}

export function Warn({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <div>{children}</div>
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="card p-8 text-center text-sm text-slate-500">{children}</div>;
}
