"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";

const labels = { name: "아이템명", overview: "아이템 개요", problem: "문제 인식(Problem)" };
type FieldId = keyof typeof labels;

export function StartupApplication({ expanded = false }: { expanded?: boolean }) {
  const { startupPlan: plan, saveStartupApplication, startupApplicationStale, refreshStartupPlan, startupPlanRevision } = useStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [edits, setEdits] = useState<Partial<Record<FieldId, string>>>({});
  const [feedback, setFeedback] = useState<string | null>(null);
  const [editRevision, setEditRevision] = useState<number | null>(null);
  const application = plan?.application;
  const dirty = Object.keys(edits).length > 0 || feedback !== null;

  async function submit(body: object) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await saveStartupApplication(body, editRevision ?? startupPlanRevision);
      setEdits({});
      setFeedback(null);
      setEditRevision(null);
      setNotice("초안을 저장했어요.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "저장하지 못했어요.");
    } finally { setBusy(false); }
  }

  return <details open={expanded || undefined} className="window space-y-3 p-4" id="startup-application">
    <summary className="cursor-pointer font-bold">글로벌 창업경진대회 신청서 초안</summary>
    <p className="text-xs text-ink/70">2026년 공식 양식의 세 문항을 활용한 모의 지원 · 접수 마감</p>
    <a className="text-xs underline" href="https://www.catholic.ac.kr/ko/campuslife/notice.do?articleNo=277684&attachNo=227459&mode=download" target="_blank" rel="noreferrer">학교 공식 양식 보기</a>
    {!plan?.idea || !plan.customer ? <p className="text-sm">창업 대화에서 팀의 아이디어와 대상 고객을 먼저 등록해 주세요.</p> : <>
      <p className="text-sm">등록한 아이디어 · {plan.idea}<br />대상 고객 · {plan.customer}</p>
      {!application && <button className="btn-gold" disabled={busy} onClick={() => void submit({ action: "generate" })}>내 자료로 초안 만들기</button>}
      {application && <>
        <label className="block text-sm">팀이 기록한 고객 피드백
          <textarea className="input mt-1 min-h-24 w-full" maxLength={3000} value={feedback ?? application.feedback}
            placeholder="언제 누구에게 무엇을 확인했고 어떤 반응을 들었는지 기록하세요."
            onChange={e => { setEditRevision(previous => previous ?? startupPlanRevision); setFeedback(e.target.value); }} />
        </label>
        {(Object.keys(labels) as FieldId[]).map(key => {
          const field = application.fields[key];
          return <div key={key} className="space-y-1 border-t border-line pt-3">
            <label className="block text-sm font-bold" htmlFor={`application-${key}`}>{labels[key]}</label>
            <p className="text-xs text-ink/70">{field?.status === "edited" ? "직접 수정" : field?.status === "draft" ? "팀 자료 기반 초안" : "추가 정보 필요"}</p>
            {startupApplicationStale[key] && <p className="text-xs text-danger">작성 후 근거 자료가 바뀌었어요. 문장을 검토해 주세요.</p>}
            <textarea id={`application-${key}`} className="input min-h-24 w-full" maxLength={6000}
              value={edits[key] ?? field?.value ?? ""} onChange={e => {
                setEditRevision(previous => previous ?? startupPlanRevision);
                setEdits(previous => ({ ...previous, [key]: e.target.value }));
              }} />
            {key === "problem" && !application.feedback && <p className="text-xs">학생 피드백을 추가하면 실제 사례를 바탕으로 이 문항을 작성할 수 있어요.</p>}
            {!!field?.sources.length && <details className="text-xs"><summary>사용한 자료 보기</summary>
              {field.sources.map(source => <p key={source}>{source}</p>)}
              {Object.entries(field.input_snapshot).map(([label, value]) => value && <p key={label}>{label} · {value}</p>)}
            </details>}
            {field?.status !== "edited" && <button className="btn-ghost text-xs" disabled={busy || dirty}
              onClick={() => void submit({ action: "generate", field_ids: [key] })}>이 문항 다시 작성</button>}
          </div>;
        })}
        <div className="flex flex-wrap gap-2">
          <button className="btn-gold" disabled={busy || !dirty} onClick={() => void submit({ action: "save", values: edits, ...(feedback !== null ? { feedback } : {}) })}>수정 내용 저장</button>
          <button className="btn-ghost" disabled={busy || dirty} onClick={() => void submit({ action: "generate" })}>팀 자료로 초안 갱신</button>
        </div>
        {dirty && <p className="text-xs">수정 내용을 저장한 뒤 문항을 다시 작성할 수 있어요.</p>}
        {dirty && editRevision !== startupPlanRevision && <p role="alert" className="text-xs text-danger">다른 작업으로 팀 자료가 바뀌었어요. 입력 내용을 복사해 둔 뒤 최신 초안을 불러와 주세요.</p>}
      </>}
    </>}
    {busy && <p role="status" className="text-sm">저장 중이에요.</p>}
    {notice && <p role="status" className="text-sm">{notice}</p>}
    {error && <div role="alert" className="text-sm text-danger">{error}<button className="ml-2 underline" onClick={() => {
      if (dirty && !window.confirm("현재 입력 내용을 버리고 저장된 최신 초안을 불러올까요?")) return;
      setEdits({}); setFeedback(null); setEditRevision(null); setError("");
      void refreshStartupPlan();
    }}>팀 정보 다시 불러오기</button></div>}
  </details>;
}
