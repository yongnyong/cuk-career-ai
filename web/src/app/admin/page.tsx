"use client";
import { useState } from "react";
import Link from "next/link";
import { CalendarClock, ClipboardCheck, FilePlus2, RotateCcw, Sparkles } from "lucide-react";
import { useStore } from "@/lib/store";
import { fmt, latest, parsePosting, type Parsed } from "@/lib/engine";
import { DEMO_CORRECTION, DEMO_NEW_POSTING } from "@/lib/data/opportunities";
import { jobById, skillById } from "@/lib/data/catalog";
import { Warn } from "@/components/ui";
import type { Condition, Opportunity } from "@/lib/types";

function toOpportunity(raw: string, x: Parsed, now: string): Opportunity {
  const required: Condition[] = [];
  if (x.status) required.push({ key: "status", label: x.status.join("·") + "생", status: x.status, src: "§1" });
  if (x.grades) required.push({ key: "grade", label: `${x.grades.join("·")}학년`, grades: x.grades, src: "§1" });
  const lines = raw.split(/\n/).map((l) => l.trim()).filter(Boolean).slice(1);
  return {
    id: "opp-" + Date.now().toString(36),
    type: x.type,
    title: x.title,
    org: "관리자 등록(가상)",
    source: { name: "가상 테스트 공고", url: "https://www.catholic.ac.kr/ko/campuslife/notice.do" },
    isVirtual: true,
    jobs: x.jobs,
    required,
    preferred: x.preferred,
    documents: x.documents,
    applyUrl: "https://www.catholic.ac.kr/ko/campuslife/notice.do",
    sections: lines.map((t, i) => ({ id: `§${i + 1}`, title: t.split(/[:：]/)[0], text: t })),
    versions: [{ version: 1, checkedAt: now, deadline: x.deadline! }],
    confidence: x.confidence,
    reviewed: x.confidence >= 0.8,
  };
}

export default function Admin() {
  const s = useStore();
  const [raw, setRaw] = useState(DEMO_NEW_POSTING);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [added, setAdded] = useState<string | null>(null);
  const [corrId, setCorrId] = useState(DEMO_CORRECTION.oppId);
  const [corrDate, setCorrDate] = useState(DEMO_CORRECTION.newDeadline.slice(0, 16));
  const [corrDone, setCorrDone] = useState(false);
  const queue = s.opportunities.filter((o) => !o.reviewed);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">관리자</h1>
        <p className="text-sm text-slate-500">공고 등록 → AI 구조화 → 검수 → 학생 스킬트리 연결·알림까지의 흐름을 확인해요.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card space-y-3 p-5">
          <h2 className="flex items-center gap-1.5 font-bold">
            <FilePlus2 size={16} /> 새 공고 등록
          </h2>
          <Warn>공고 원문에 명단·연락처 같은 개인정보가 있으면 넣지 마세요. 저장하지 않고 AI에도 보내지 않아요.</Warn>
          <textarea className="input h-44 font-mono text-xs" value={raw} onChange={(e) => setRaw(e.target.value)} />
          <button className="btn-primary" onClick={() => (setParsed(parsePosting(raw)), setAdded(null))}>
            <Sparkles size={16} /> AI 구조화
          </button>
          {parsed && (
            <div className="space-y-2 rounded-lg bg-paper p-3 text-sm">
              <div className="flex items-center gap-2">
                <b>구조화 결과</b>
                <span className={`chip ${parsed.confidence >= 0.8 ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                  신뢰도 {parsed.confidence}
                </span>
                {parsed.confidence < 0.8 && <span className="text-xs text-amber-700">0.8 미만 → 검수 대기열</span>}
              </div>
              <pre className="overflow-x-auto rounded bg-navy p-3 text-[11px] leading-relaxed text-emerald-200">
                {JSON.stringify(
                  {
                    type: parsed.type,
                    title: parsed.title,
                    required: { status: parsed.status, grades: parsed.grades },
                    preferred: parsed.preferred,
                    documents: parsed.documents,
                    deadline: parsed.deadline,
                    confidence: parsed.confidence,
                  },
                  null,
                  2,
                )}
              </pre>
              <p className="text-xs">
                우대 역량: {parsed.preferred.map((x) => skillById(x)?.name).join(", ") || "없음"} · 연결 직무:{" "}
                {parsed.jobs.map((j) => jobById(j)?.name).join(", ") || "없음"}
              </p>
              {parsed.unparsed.length > 0 && <p className="text-xs text-amber-700">추출 실패: {parsed.unparsed.join(", ")} — 사람이 확인해야 해요</p>}
              <button
                className="btn bg-accent text-white"
                disabled={!parsed.deadline}
                onClick={() => {
                  const o = toOpportunity(raw, parsed, s.now);
                  s.addOpportunity(o);
                  setAdded(o.id);
                  setParsed(null);
                }}
              >
                등록하고 학생에게 연결
              </button>
              {!parsed.deadline && <p className="text-xs text-danger">마감일을 읽지 못해 등록할 수 없어요. 날짜는 AI가 추측하지 않아요.</p>}
            </div>
          )}
          {added && (
            <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-ok">
              등록 완료. 관련 노드를 가진 학생의{" "}
              <Link href="/tree" className="underline">
                스킬트리
              </Link>
              에 &lsquo;새 기회&rsquo;로 표시돼요.
            </p>
          )}
        </section>

        <div className="space-y-4">
          <section className="card space-y-3 p-5">
            <h2 className="flex items-center gap-1.5 font-bold">
              <CalendarClock size={16} /> 정정 공고 처리 (마감 변경)
            </h2>
            <select className="input" value={corrId} onChange={(e) => (setCorrId(e.target.value), setCorrDone(false))}>
              {s.opportunities.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.title} — 현재 마감 {fmt(latest(o).deadline)} (v{latest(o).version})
                </option>
              ))}
            </select>
            <input type="datetime-local" className="input" value={corrDate} onChange={(e) => setCorrDate(e.target.value)} />
            <button
              className="btn-primary"
              onClick={() => {
                s.correctDeadline(corrId, corrDate + ":00+09:00");
                setCorrDone(true);
              }}
            >
              새 버전 저장 · 알림 재계산
            </button>
            {corrDone && (
              <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-ok">
                새 버전을 저장했어요. 이전 예약 알림은 무효 처리되고 새 마감 기준으로 다시 예약됐어요.{" "}
                <Link href="/notifications" className="underline">
                  알림 확인
                </Link>
              </p>
            )}
          </section>

          <section className="card p-5">
            <h2 className="flex items-center gap-1.5 font-bold">
              <ClipboardCheck size={16} /> 검수 대기열 {queue.length}
            </h2>
            <p className="text-xs text-slate-500">신뢰도 0.8 미만인 구조화 결과는 사람이 확인한 뒤 공개해요.</p>
            <ul className="mt-2 space-y-2">
              {queue.length === 0 && <li className="text-sm text-slate-500">대기 중인 공고가 없어요.</li>}
              {queue.map((o) => (
                <li key={o.id} className="flex flex-wrap items-center gap-2 rounded-lg bg-paper px-3 py-2 text-sm">
                  <Link href={`/opportunities/${o.id}`} className="font-medium hover:underline">
                    {o.title}
                  </Link>
                  <span className="chip bg-amber-100 text-amber-700">신뢰도 {o.confidence}</span>
                  <button className="btn-ghost ml-auto !py-1 text-xs" onClick={() => s.approve(o.id)}>
                    확인 후 승인
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="card p-5 text-sm">
            <h2 className="font-bold">데이터 현황</h2>
            <p className="mt-1 text-slate-600">
              공고 {s.opportunities.length}건 (가상 {s.opportunities.filter((o) => o.isVirtual).length} · 실제 공개{" "}
              {s.opportunities.filter((o) => !o.isVirtual).length}) · 알림 {s.notices.length}건
            </p>
            <button
              className="btn-ghost mt-3"
              onClick={() => confirm("시연 데이터를 처음 상태로 되돌릴까요? 프로필도 지워져요.") && s.resetDemo()}
            >
              <RotateCcw size={14} /> 시연 데이터 초기화
            </button>
          </section>
        </div>
      </div>
    </div>
  );
}
