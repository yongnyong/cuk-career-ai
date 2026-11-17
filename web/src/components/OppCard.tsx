"use client";
import Link from "next/link";
import type { Recommendation } from "@/lib/engine";
import { DDay, TypeTag, VerdictBadge, VirtualTag } from "./ui";

export function OppCard({ r, now, isNew }: { r: Recommendation; now: Date; isNew?: boolean }) {
  const o = r.opp;
  // 지원금·혜택에 금액이 적혀 있으면 카드에서 바로 보이게 한다
  const money = o.facts?.find((f) => /지원금|혜택/.test(f.label))?.value.match(/(?:최대\s*)?\d[\d,.]*\s*(?:억|천만|백만|만)\s*원/)?.[0];
  return (
    <Link href={`/opportunities/${o.id}`} className={`card block p-4 transition hover:border-edge ${isNew ? "unlock border-2 border-edge" : ""}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        <TypeTag type={o.type} />
        {o.isVirtual && <VirtualTag />}
        {isNew && <span className="chip bg-gold text-on-gold">새 기회</span>}
        <span className="ml-auto">
          <DDay opp={o} now={now} />
        </span>
      </div>
      <h3 className="mt-2 font-bold leading-snug">{o.title}</h3>
      <p className="text-xs text-slate-500">{o.org}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <VerdictBadge v={r.verdict} />
        {money && <span className="chip bg-amber-100 text-amber-700">{money}</span>}
      </div>
      <ul className="mt-2 space-y-0.5 text-xs text-slate-600">
        {r.reasons.slice(0, 3).map((x) => (
          <li key={x}>· {x}</li>
        ))}
      </ul>
    </Link>
  );
}
