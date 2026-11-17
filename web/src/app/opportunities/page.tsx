"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { RequireProfile } from "@/components/RequireProfile";
import { OppCard } from "@/components/OppCard";
import { AiNotice, DDay, TypeTag, VerdictBadge, VirtualTag } from "@/components/ui";
import { useStore } from "@/lib/store";
import { evaluate, isOpen, recommend } from "@/lib/engine";
import type { OppType } from "@/lib/types";

const TYPES: (OppType | "전체")[] = ["전체", "현장실습", "창업지원", "채용", "비교과", "장학", "학사"];

function List() {
  const s = useStore();
  const p = s.profile!;
  const now = s.nowDate;
  const [type, setType] = useState<OppType | "전체">("전체");
  const [mode, setMode] = useState<"rec" | "all">("rec");
  const [q, setQ] = useState("");
  const recs = useMemo(() => recommend(s.opportunities, p, now), [s.opportunities, p, now]);
  const newSet = new Set(s.newOpps);
  const match = (title: string, org: string, t: OppType) =>
    (type === "전체" || t === type) && (!q || (title + org).toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">기회</h1>
          <p className="text-sm text-slate-500">조건을 먼저 거르고, 목표 직무·보유 역량·마감 순으로 정렬했어요.</p>
        </div>
        <div className="flex rounded-lg border border-slate-300 bg-panel p-0.5 text-sm">
          {(["rec", "all"] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)} className={`rounded-md px-3 py-1 ${mode === m ? "bg-navy text-white" : ""}`}>
              {m === "rec" ? `맞춤 추천 ${recs.length}` : `전체 공고 ${s.opportunities.length}`}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setType(t)}
            className={`chip border px-3 py-1 ${type === t ? "border-edge bg-navy text-white" : "border-slate-300 bg-panel text-slate-600"}`}
          >
            {t}
          </button>
        ))}
        <input className="input ml-auto max-w-56 !py-1.5" placeholder="공고 검색" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {mode === "rec" ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {recs
            .filter((r) => match(r.opp.title, r.opp.org, r.opp.type))
            .map((r) => (
              <OppCard key={r.opp.id} r={r} now={now} isNew={newSet.has(r.opp.id)} />
            ))}
        </div>
      ) : (
        <div className="card divide-y divide-slate-100">
          {s.opportunities
            .filter((o) => match(o.title, o.org, o.type))
            .sort((a, b) => Number(isOpen(b, now)) - Number(isOpen(a, now)))
            .map((o) => (
              <Link key={o.id} href={`/opportunities/${o.id}`} className="flex flex-wrap items-center gap-2 px-4 py-3 text-sm hover:bg-slate-50">
                <TypeTag type={o.type} />
                {o.isVirtual && <VirtualTag />}
                <span className="font-medium">{o.title}</span>
                <span className="text-xs text-slate-400">{o.org}</span>
                <span className="ml-auto flex items-center gap-2">
                  <VerdictBadge v={evaluate(o, p).overall} />
                  <DDay opp={o} now={now} />
                </span>
              </Link>
            ))}
        </div>
      )}
      <AiNotice />
    </div>
  );
}

export default function Page() {
  return (
    <RequireProfile>
      <List />
    </RequireProfile>
  );
}
