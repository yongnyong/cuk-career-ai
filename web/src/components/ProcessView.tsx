"use client";
import { useState } from "react";
import { Check, ChevronDown, ScanSearch, X } from "lucide-react";
import { useStore } from "@/lib/store";
import { evaluateCondition } from "@/lib/engine";
import type { Condition, Opportunity, Section } from "@/lib/types";
import { VerdictIcon } from "./ui";

// 서버 /api/process/{id} 응답: 조건 정리 에이전트가 공고 한 건을 읽는 과정
interface Check {
  category?: string;
  label: string;
  kind?: string;
  quote: string;
  ok: boolean;
  exact: boolean;
  section: string | null;
  reason: string;
  becomes: { key: string; label: string } | null;
}
interface Trace {
  model: string;
  ms: number;
  at: string;
  sections: (Section & { used: boolean })[];
  checks: Check[];
  kept: number;
  dropped: number;
  final: Condition[];
  usedAi: boolean;
}

// 원문 문단에서 통과한 근거 구절을 표시한다(글자 그대로 있는 구절만)
function Highlighted({ text, quotes }: { text: string; quotes: string[] }) {
  const spans: [number, number][] = [];
  for (const q of quotes) {
    const i = q ? text.indexOf(q) : -1;
    if (i >= 0 && !spans.some(([a, b]) => i < b && i + q.length > a)) spans.push([i, i + q.length]);
  }
  spans.sort((a, b) => a[0] - b[0]);
  const out: React.ReactNode[] = [];
  let at = 0;
  spans.forEach(([a, b], k) => {
    out.push(text.slice(at, a));
    out.push(
      <mark key={k} className="rounded bg-gold px-0.5 text-on-gold">
        {text.slice(a, b)}
      </mark>,
    );
    at = b;
  });
  out.push(text.slice(at));
  return <>{out}</>;
}

function Step({ n, title, note, children }: { n: number; title: string; note?: string; children: React.ReactNode }) {
  return (
    <li className="grid gap-x-3 sm:grid-cols-[2rem_1fr]">
      <span className="font-display text-2xl leading-none text-edge" aria-hidden>
        {n}
      </span>
      <div className="min-w-0">
        <h3 className="font-bold">{title}</h3>
        {note && <p className="text-xs text-slate-500">{note}</p>}
        <div className="mt-2">{children}</div>
      </div>
    </li>
  );
}

export function ProcessView({ opp }: { opp: Opportunity }) {
  const { profile } = useStore();
  const [open, setOpen] = useState(false);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setOpen((v) => !v);
    if (trace || busy) return;
    setBusy(true);
    setError("");
    try {
      const r = await fetch(`/api/process/${encodeURIComponent(opp.id)}`);
      const data = r.headers.get("content-type")?.includes("application/json") ? await r.json() : null;
      if (r.ok && data) setTrace(data);
      else setError(typeof data?.detail === "string" ? data.detail : "서버에 연결하지 못했어요.");
    } catch {
      setError("서버에 연결하지 못했어요.");
    }
    setBusy(false);
  };

  return (
    <div className="card p-5">
      <button className="flex w-full items-center gap-2 text-left" onClick={load} aria-expanded={open}>
        <ScanSearch size={18} className="text-edge" />
        <span className="flex-1">
          <span className="block font-bold">AI 처리 과정 보기</span>
          <span className="block text-xs text-slate-500">이 공고를 AI가 어떻게 읽었고, 서버가 무엇을 걸러냈는지 단계별로 보여줘요.</span>
        </span>
        <ChevronDown size={18} className={`transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="mt-4 border-t border-line pt-4">
          {busy && <p className="text-sm text-slate-500">AI가 공고를 다시 읽는 중이에요… (처음 한 번만 몇 초 걸려요)</p>}
          {error && <p className="text-sm text-danger">{error}</p>}
          {trace && (
            <>
              <p className="rounded-md bg-paper px-3 py-2 text-sm">
                AI가 낸 조건 <b>{trace.checks.length}개</b> 중 <b className="text-ok">{trace.kept}개 통과</b>,{" "}
                <b className={trace.dropped ? "text-danger" : ""}>{trace.dropped}개 탈락</b>
                <span className="text-slate-500">
                  {" "}
                  · {trace.model} · {(trace.ms / 1000).toFixed(1)}초
                </span>
              </p>
              <ol className="mt-4 space-y-6">
                <Step n={1} title="원문에서 자격·대상 문단만 고른다" note="전형 절차나 접수 방법처럼 조건과 무관한 문단은 AI에 보내지 않아요.">
                  <ul className="space-y-1.5">
                    {trace.sections.map((s) => (
                      <li key={s.id} className={`rounded-md border px-3 py-2 text-xs ${s.used ? "border-edge/60" : "border-line opacity-50"}`}>
                        <b>
                          {s.id} {s.title}
                        </b>
                        <span className="ml-1.5 text-slate-500">{s.used ? "AI에 보냄" : "보내지 않음"}</span>
                        {s.used && (
                          <p className="mt-1 whitespace-pre-wrap text-slate-600">
                            <Highlighted text={s.text} quotes={trace.checks.filter((c) => c.ok && c.section === s.id).map((c) => c.quote)} />
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                </Step>

                <Step n={2} title="AI가 조건과 근거 구절을 낸다" note="조건마다 그 근거가 되는 원문 구절을 함께 내도록 했어요.">
                  <ul className="space-y-1.5">
                    {trace.checks.length === 0 && <li className="text-sm text-slate-500">AI가 조건을 내지 않았어요.</li>}
                    {trace.checks.map((c, i) => (
                      <li key={i} className="rounded-md bg-paper px-3 py-2 text-sm">
                        <span className="chip mr-1.5 bg-violet-100 text-violet-700">{c.category}</span>
                        <b>{c.label}</b>
                        {c.kind === "preferred" && <span className="ml-1.5 text-xs text-slate-500">우대</span>}
                        <p className="mt-0.5 text-xs text-slate-500">근거 구절: &ldquo;{c.quote}&rdquo;</p>
                      </li>
                    ))}
                  </ul>
                </Step>

                <Step n={3} title="서버가 근거 구절을 원문과 대조한다" note="구절이 원문에 없으면 그 조건은 버려요. AI가 지어낸 조건을 막는 단계예요.">
                  <ul className="space-y-1.5">
                    {trace.checks.map((c, i) => (
                      <li key={i} className={`flex items-start gap-2 rounded-md px-3 py-2 text-sm ${c.ok ? "bg-emerald-50" : "bg-red-50"}`}>
                        <span className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded ${c.ok ? "bg-ok text-white" : "bg-danger text-white"}`}>
                          {c.ok ? <Check size={13} /> : <X size={13} />}
                        </span>
                        <span className="min-w-0">
                          <b>{c.ok ? "통과" : "탈락"}</b> · {c.label}
                          <span className="block text-xs text-slate-600">
                            {c.reason}
                            {c.section && ` (${c.section})`}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </Step>

                <Step n={4} title="규칙이 내 정보와 비교해 판정한다" note="판정은 AI가 하지 않아요. 통과한 조건을 규칙이 내 학년·학적·점수와 비교해요.">
                  <ul className="space-y-1.5">
                    {trace.final.length === 0 && <li className="text-sm text-slate-500">남은 조건이 없어요.</li>}
                    {trace.final.map((c, i) => {
                      const r = profile ? evaluateCondition(c, profile) : null;
                      return (
                        <li key={i} className="flex items-start gap-2 rounded-md bg-paper px-3 py-2 text-sm">
                          {r && <VerdictIcon v={r.verdict} />}
                          <span>
                            <b>{c.label}</b>
                            {r && <span className="text-slate-600"> — {r.reason}</span>}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </Step>
              </ol>
              <p className="mt-4 text-xs text-slate-500">
                공식 API가 준 값(창업 단계·연령·학력)은 AI를 거치지 않고 그대로 조건이 돼요. 이 화면은 과정을 보여주는 용도이고 저장된 공고는 바꾸지 않아요.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
