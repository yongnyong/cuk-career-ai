"use client";
import { useEffect, useState } from "react";
import { Database, GitBranch } from "lucide-react";
import { useStore } from "@/lib/store";
import { jobsFor } from "@/lib/engine";
import { skillById } from "@/lib/data/catalog";
import { DEPARTMENTS } from "@/lib/data/departments";

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

// 모든 학과의 직무·테크와 노드를 한 화면에서 확인한다
export function TrackBrowser() {
  const [dept, setDept] = useState("psychology");
  const jobs = jobsFor(dept);
  return (
    <div className="space-y-3">
      <select className="input sm:w-72" value={dept} onChange={(e) => setDept(e.target.value)} aria-label="학과 선택">
        {DEPARTMENTS.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
            {jobsFor(d.id).some((j) => j.departments) ? " (학과 테크 있음)" : ""}
          </option>
        ))}
      </select>
      <ul className="grid gap-2 lg:grid-cols-2">
        {jobs.map((j) => (
          <li key={j.id} className="rounded-md border border-line p-3 text-sm">
            <div className="flex flex-wrap items-center gap-1.5 font-bold">
              {j.name}
              {j.departments && <span className="chip bg-gold text-on-gold">학과 테크</span>}
              {j.srcUrl && (
                <a href={j.srcUrl} target="_blank" rel="noreferrer" className="text-xs font-normal underline">
                  출처
                </a>
              )}
            </div>
            <p className="text-xs text-slate-500">{j.summary}</p>
            <p className="mt-1 text-xs text-slate-600">
              {j.nodes.map((n) => `${skillById(n.skill)?.name ?? n.skill}${n.required ? "(필수)" : ""}`).join(" → ")}
            </p>
          </li>
        ))}
      </ul>
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
          <GitBranch size={16} /> 학과별 직무·테크 전체 보기
        </h2>
        <TrackBrowser />
      </section>
    </>
  );
}
