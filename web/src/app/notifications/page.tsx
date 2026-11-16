"use client";
import Link from "next/link";
import { Clock, FastForward, RotateCcw } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { Empty } from "@/components/ui";
import { DEMO_START, useStore } from "@/lib/store";
import { fmt } from "@/lib/engine";
import type { Notice } from "@/lib/types";

const DAY = 86_400_000;
const STATUS: Record<Notice["status"], { label: string; cls: string }> = {
  sent: { label: "발송됨", cls: "bg-emerald-100 text-emerald-700" },
  scheduled: { label: "예약", cls: "bg-blue-100 text-blue-700" },
  cancelled: { label: "무효", cls: "bg-slate-200 text-slate-500" },
};

function Body() {
  const s = useStore();
  const shift = (days: number) => s.setNow(new Date(s.nowDate.getTime() + days * DAY).toISOString());
  const groups: Notice["status"][] = ["sent", "scheduled", "cancelled"];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">알림</h1>
        <p className="text-sm text-slate-500">지원 퀘스트를 시작한 공고의 D-7·3·1과 정정 알림이에요. 같은 알림은 한 번만 발송돼요.</p>
      </div>

      <div className="card flex flex-wrap items-center gap-2 border-violet-200 bg-violet-50 p-4 text-sm">
        <Clock size={16} className="text-violet-700" />
        <span className="font-medium text-violet-900">시연용 가상 시계</span>
        <span className="font-bold">{fmt(s.now)}</span>
        <div className="ml-auto flex flex-wrap gap-1.5">
          {[1, 3, 7].map((d) => (
            <button key={d} className="btn-ghost !py-1 text-xs" onClick={() => shift(d)}>
              <FastForward size={12} /> +{d}일
            </button>
          ))}
          <button className="btn-ghost !py-1 text-xs" onClick={() => s.setNow(DEMO_START)}>
            <RotateCcw size={12} /> 처음으로
          </button>
        </div>
        <p className="w-full text-xs text-violet-700">실제 서비스에서는 서버 작업 큐가 시각에 맞춰 발송해요. 시연에서는 날짜를 넘겨 확인해요.</p>
      </div>

      {s.notices.length === 0 && (
        <Empty>
          아직 알림이 없어요.{" "}
          <Link href="/opportunities" className="underline">
            기회
          </Link>
          에서 지원 퀘스트를 시작해 보세요.
        </Empty>
      )}

      {groups.map((g) => {
        const list = s.notices.filter((n) => n.status === g);
        if (!list.length) return null;
        const sorted = g === "sent" ? [...list].reverse() : list;
        return (
          <section key={g}>
            <h2 className="mb-2 text-sm font-bold text-slate-600">
              {STATUS[g].label} {list.length}
            </h2>
            <ul className="card divide-y divide-slate-100">
              {sorted.map((n) => (
                <li key={n.id}>
                  <Link href={`/opportunities/${n.oppId}`} className="flex flex-wrap items-center gap-2 px-4 py-3 text-sm hover:bg-slate-50">
                    <span className={`chip ${STATUS[g].cls}`}>{STATUS[g].label}</span>
                    <span className={g === "cancelled" ? "text-slate-400 line-through" : ""}>{n.message}</span>
                    <span className="ml-auto text-xs text-slate-400">
                      {fmt(n.fireAt)} · v{n.version}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

export default function Page() {
  return (
    <RequireProfile>
      <Body />
    </RequireProfile>
  );
}
