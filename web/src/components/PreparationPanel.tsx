"use client";

import { useEffect, useRef, useState } from "react";
import { useStore } from "@/lib/store";

interface PreparationReport {
  ai: { provider: string; status: string; message?: string };
  evidence_snapshot_on: string;
  data_gaps: string[];
  plan: {
    action_key: string;
    title: string;
    reason: string;
    source_urls: string[];
    historical_reference: boolean;
    steps: { checkpoint_on: string; action: string; deliverable: string }[];
    completion_rule: string;
  }[];
}

export function PreparationPanel() {
  const { profile } = useStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<{ key: string; report: PreparationReport } | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  // Explicit field list: identity, admission year, birth date and proof files stay out.
  const input = profile ? {
    departmentId: profile.departmentId, grade: profile.grade, status: profile.status,
    jobId: profile.jobId, skills: profile.skills, scores: profile.scores ?? {},
    weeklyHours: profile.weeklyHours,
  } : null;
  const key = JSON.stringify(input);
  const report = saved?.key === key ? saved.report : null;

  const generate = async () => {
    if (!input || busy) return;
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/preparation/plan", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: input, useAi: true }), signal: request.signal,
      });
      if (!response.headers.get("content-type")?.includes("application/json")) {
        throw new Error("로컬 API 서버를 실행한 뒤 다시 시도해 주세요.");
      }
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "입력 정보를 확인해 주세요.");
      setSaved({ key, report: body });
    } catch (cause) {
      if (!request.signal.aborted) setError(cause instanceof Error ? cause.message : "준비 계획을 불러오지 못했어요.");
    } finally {
      if (!request.signal.aborted) setBusy(false);
    }
  };

  return (
    <section className="card space-y-3 p-4" aria-label="맞춤 준비 계획">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-bold">이번 학기 맞춤 준비 계획</h2>
          <p className="text-xs text-ink/60">내 기록과 공고·학교 근거를 비교해 먼저 할 일을 정해요.</p>
        </div>
        <button className="btn-primary text-sm" disabled={busy || !profile} onClick={generate}>
          {busy ? "준비 순서를 정하는 중…" : report ? "다시 분석하기" : "AI 준비 계획 만들기"}
        </button>
      </div>
      {busy && <p className="text-xs text-ink/60" role="status">최대 90초 정도 걸릴 수 있어요.</p>}
      {saved && !report && <p className="text-xs text-ink/60">내 정보가 바뀌었어요. 새 기록으로 다시 분석해 주세요.</p>}
      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
      {report && (
        <>
          <p className="text-xs text-ink/60">
            {report.ai.status === "completed" ? "AI가 준비 우선순위를 정했어요." : report.ai.message ?? "근거 기반 기본 순서예요."}
            {" "}근거 자료 기준: {report.evidence_snapshot_on}. 전체 지원자격·합격 가능성 판정은 아니에요.
          </p>
          <ol className="grid gap-3 md:grid-cols-3">
            {report.plan.map((item, index) => (
              <li key={item.action_key} className="rounded-lg border border-line p-3">
                <h3 className="text-sm font-bold">{index + 1}. {item.title}</h3>
                <p className="mt-2 text-xs text-ink/70">{item.reason}</p>
                {item.historical_reference && <p className="mt-1 text-xs text-warn">과거 공고를 준비 기준으로 참고해요.</p>}
                <ul className="mt-3 space-y-2 text-xs">
                  {item.steps.map((step, i) => (
                    <li key={i}><strong>{step.checkpoint_on}</strong> · {step.action}<br />결과물: {step.deliverable}</li>
                  ))}
                </ul>
                <p className="mt-3 text-xs text-ink/60">{item.completion_rule}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  {item.source_urls.map((url, i) => <a key={url} href={url} target="_blank" rel="noreferrer" className="underline">근거 원문 {i + 1}</a>)}
                </div>
              </li>
            ))}
          </ol>
          {report.data_gaps.length > 0 && <ul className="space-y-1 text-xs text-ink/60">{report.data_gaps.map((gap) => <li key={gap}>{gap}</li>)}</ul>}
        </>
      )}
    </section>
  );
}
