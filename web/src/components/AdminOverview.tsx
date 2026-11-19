"use client";
import { useEffect, useState } from "react";
import { ClipboardPaste, Database, GitBranch } from "lucide-react";
import { useStore } from "@/lib/store";
import { TrackEditor } from "./TrackEditor";
import { ManualPostingForm } from "./ManualPostingForm";

type Overview = {
  users: number;
  postings: { total: number; open: number; pendingReview: number; bySource: Record<string, number>; byType: Record<string, number> };
  lastCheckedAt: string | null;
};
const SOURCE: Record<string, string> = { cuk: "학교 공지", kst: "K-Startup", w24: "고용24 공채속보" };

// 관리자 계정 전용: 서버 현황(개수만, 개인정보 없음)
export function ServerOverview() {
  const { isAdmin } = useStore();
  const [data, setData] = useState<Overview | null>(null);
  useEffect(() => {
    if (!isAdmin) return;
    fetch("/api/admin/overview")
      .then((r) => (r.ok ? r.json() : null))
      .then(setData)
      .catch(() => setData(null));
  }, [isAdmin]);
  if (!isAdmin) return <p className="text-sm text-slate-500">서버 현황은 관리자 계정으로 로그인하면 보여요.</p>;
  if (!data) return <p className="text-sm text-slate-500">서버 현황을 불러오는 중…</p>;
  const cell = (label: string, value: number | string) => (
    <div className="rounded-md bg-paper p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-xl font-bold tabular-nums">{value}</div>
    </div>
  );
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {cell("가입 계정", data.users)}
        {cell("수집 공고", data.postings.total)}
        {cell("모집 중", data.postings.open)}
        {cell("검수 대기", data.postings.pendingReview)}
      </div>
      <p className="text-sm text-slate-600">
        출처별: {Object.entries(data.postings.bySource).map(([k, v]) => `${SOURCE[k] ?? k} ${v}건`).join(" · ")}
      </p>
      <p className="text-sm text-slate-600">
        유형별: {Object.entries(data.postings.byType).map(([k, v]) => `${k} ${v}건`).join(" · ")}
      </p>
      <p className="text-xs text-slate-500">마지막 수집 확인: {data.lastCheckedAt ? new Date(data.lastCheckedAt).toLocaleString("ko-KR") : "없음"}</p>
    </div>
  );
}

export function AdminOverview() {
  return (
    <>
      <section className="card space-y-3 p-5">
        <h2 className="flex items-center gap-1.5 font-bold">
          <Database size={16} /> 서버 현황
        </h2>
        <ServerOverview />
      </section>
      <section className="card space-y-3 p-5">
        <h2 className="flex items-center gap-1.5 font-bold">
          <ClipboardPaste size={16} /> 직접 확인한 공고 등록 (서버 저장 · AI 구조화)
        </h2>
        <ManualPostingForm />
      </section>
      <section className="card space-y-3 p-5">
        <h2 className="flex items-center gap-1.5 font-bold">
          <GitBranch size={16} /> 학과별 테크트리 — 학생 화면 보기·수정
        </h2>
        <TrackEditor />
      </section>
    </>
  );
}
