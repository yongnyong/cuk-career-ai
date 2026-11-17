"use client";
import Link from "next/link";
import type { Recommendation } from "@/lib/engine";
import { DDay, TypeTag, VerdictBadge, VirtualTag } from "./ui";

export function OppCard({ r, now, isNew }: { r: Recommendation; now: Date; isNew?: boolean }) {
  const o = r.opp;
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
      <div className="mt-2">
        <VerdictBadge v={r.verdict} />
      </div>
      <ul className="mt-2 space-y-0.5 text-xs text-slate-600">
        {r.reasons.slice(0, 3).map((x) => (
          <li key={x}>· {x}</li>
        ))}
      </ul>
    </Link>
  );
}
