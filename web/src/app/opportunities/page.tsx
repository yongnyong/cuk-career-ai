"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { RequireProfile } from "@/components/RequireProfile";
import { OppCard } from "@/components/OppCard";
import { AiNotice, DDay, TypeTag, VerdictBadge, VirtualTag } from "@/components/ui";
import { useStore } from "@/lib/store";
import { evaluate, isOpen } from "@/lib/engine";
import type { Opportunity, OppType } from "@/lib/types";
import { careerInterestOf } from "@/lib/interest";

const TYPES: (OppType | "전체")[] = ["전체", "현장실습", "창업지원", "채용", "비교과", "장학", "학사"];
const PAGE_SIZE = 24;

function List() {
  const s = useStore();
  const p = s.profile!;
  const startup = careerInterestOf(p) === 'startup';
  const now = s.nowDate;
  const [type, setType] = useState<OppType | "전체">("전체");
  const [mode, setMode] = useState<"rec" | "prep" | "all">("rec");
  const [q, setQ] = useState("");
  const [requestedPage, setPage] = useState(1);
  const recs = s.recommendations;
  const references = s.preparationRecommendations;
  const cards = mode === "prep" ? references : recs;
  const newSet = new Set(s.newOpps);
  const filtered = useMemo(() => {
    const query = q.toLowerCase();
    const match = (title: string, org: string, t: OppType) =>
      (type === "전체" || t === type) && (!query || (title + org).toLowerCase().includes(query));
    if (mode !== "all") return { cards: cards.filter(r => match(r.opp.title, r.opp.org, r.opp.type)), all: [] };
    // Evaluate open status once per posting and retain the original order within each group.
    const open: Opportunity[] = [], closed: Opportunity[] = [];
    for (const o of s.opportunities) {
      if (match(o.title, o.org, o.type)) (isOpen(o, now) ? open : closed).push(o);
    }
    return { cards: [], all: [...open, ...closed] };
  }, [cards, s.opportunities, mode, type, q, now]);
  const count = mode === "all" ? filtered.all.length : filtered.cards.length;
  const pageCount = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const page = Math.min(requestedPage, pageCount);
  const start = (page - 1) * PAGE_SIZE;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">기회</h1>
          <p className="text-sm text-slate-500">{startup ? '창업 지원사업·경진대회의 제출물과 지원 자격을 확인해요. 지난 공고도 준비 자료로 볼 수 있어요.' : '지원 조건을 확인하고, 목표·관심 직무부터 추천해요. 전공·학과·같은 계열의 탐색 공고도 이어서 볼 수 있어요.'}</p>
        </div>
        <div className="flex rounded-lg border border-slate-300 bg-panel p-0.5 text-sm">
          {(["rec", "prep", "all"] as const).map((m) => (
            <button key={m} onClick={() => { setMode(m); setPage(1); }} className={`rounded-md px-3 py-1 ${mode === m ? "bg-navy text-white" : ""}`}>
              {m === "rec" ? '맞춤 추천 ' + recs.length : m === "prep" ? '준비 참고 ' + references.length : '전체 공고 ' + s.opportunities.length}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {(startup ? ['전체', '창업지원'] as const : TYPES.filter((t) => t !== '창업지원')).map((t) => (
          <button
            key={t}
            onClick={() => { setType(t); setPage(1); }}
            className={`chip border px-3 py-1 ${type === t ? "border-edge bg-navy text-white" : "border-slate-300 bg-panel text-slate-600"}`}
          >
            {t}
          </button>
        ))}
        <input className="input ml-auto max-w-56 !py-1.5" placeholder="공고 검색" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
      </div>

      {mode === "prep" && <p className="text-sm text-slate-500">앞으로 준비할 조건을 살펴보세요. 지난 공고와 접수 예정 공고, 현재 지원 조건을 확인해야 하는 공고가 포함돼요.</p>}
      {mode === "rec" && s.opportunitySearch.status === "loading" && <p role="status" className="text-sm text-slate-500">목표와 관련된 공고 원문을 찾고 있어요.</p>}
      {mode === "rec" && s.opportunitySearch.status === "fallback" && <p role="status" className="text-sm text-slate-500">공고 검색에 연결하지 못해 기존 추천을 표시하고 있어요.</p>}
      {mode !== "all" ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {count === 0 && <p className="text-sm text-slate-500">지금 표시할 공고가 없어요. 전체 공고에서 준비 자료를 확인할 수 있어요.</p>}
          {filtered.cards.slice(start, start + PAGE_SIZE)
            .map((r) => (
              <OppCard key={r.opp.id} r={r} now={now} isNew={newSet.has(r.opp.id)} />
            ))}
        </div>
      ) : (
        <div className="card divide-y divide-slate-100">
          {count === 0 && <p className="p-4 text-sm text-slate-500">검색 결과가 없어요.</p>}
          {filtered.all.slice(start, start + PAGE_SIZE)
            .map((o) => (
              <Link key={o.id} href={`/opportunities/${o.id}`} prefetch={false} className="flex flex-wrap items-center gap-2 px-4 py-3 text-sm hover:bg-slate-50">
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
      {count > 0 && <nav aria-label="공고 페이지" className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <p role="status" aria-live="polite">총 {count.toLocaleString()}개 중 {start + 1}–{Math.min(start + PAGE_SIZE, count)}개 · {page}/{pageCount}페이지</p>
        <div className="flex gap-2">
          <button type="button" disabled={page === 1} onClick={() => setPage(page - 1)} className="rounded border px-3 py-1 disabled:opacity-40">이전 페이지</button>
          <button type="button" disabled={page === pageCount} onClick={() => setPage(page + 1)} className="rounded border px-3 py-1 disabled:opacity-40">다음 페이지</button>
        </div>
      </nav>}
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
