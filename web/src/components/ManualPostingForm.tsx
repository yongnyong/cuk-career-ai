"use client";
import { useState } from "react";
import { ClipboardPaste } from "lucide-react";
import { useStore } from "@/lib/store";
import { fmt, latest } from "@/lib/engine";
import type { Opportunity } from "@/lib/types";
import { Warn } from "./ui";

// 관리자가 직접 확인한 공고 본문을 붙여넣어 서버에 등록한다(AI가 구조화).
// 로그인 뒤에만 보이는 공고처럼 자동 수집하면 안 되는 자료를 사람이 옮길 때 쓴다.
export function ManualPostingForm() {
  const { isAdmin } = useStore();
  const [text, setText] = useState("");
  const [sourceName, setSourceName] = useState("가톨릭대학교 현장실습지원센터");
  const [sourceUrl, setSourceUrl] = useState("https://co-op.catholic.ac.kr/");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<Opportunity | null>(null);

  if (!isAdmin) return <p className="text-sm text-slate-500">관리자 계정으로 로그인하면 공고를 서버에 등록할 수 있어요.</p>;

  const submit = async () => {
    setBusy(true);
    setError("");
    setSaved(null);
    try {
      const r = await fetch("/api/admin/postings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, sourceName, sourceUrl }),
      });
      const data = r.headers.get("content-type")?.includes("application/json") ? await r.json() : null;
      if (r.ok && data) {
        setSaved(data);
        setText("");
      } else setError(typeof data?.detail === "string" ? data.detail : "등록하지 못했어요. 입력 내용을 확인해 주세요.");
    } catch {
      setError("서버에 연결하지 못했어요.");
    }
    setBusy(false);
  };

  return (
    <div className="space-y-3">
      <Warn>
        직접 열어 확인한 공고만 붙여넣으세요. 첫 줄은 공고 제목으로 쓰여요. 명단·이름·연락처는 지우고 넣어 주세요(전화번호와 학번은 서버에서도 한 번 더 지워요).
      </Warn>
      <textarea
        className="input h-48 text-sm"
        placeholder={"첫 줄: 공고 제목\n그 아래: 모집 대상, 신청 기간, 제출 서류 등 본문"}
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={8000}
        aria-label="공고 본문"
      />
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="text-sm">
          <span className="mb-1 block font-semibold">출처(기관·부서)</span>
          <input className="input" value={sourceName} onChange={(e) => setSourceName(e.target.value)} maxLength={60} />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-semibold">원문·신청처 주소</span>
          <input className="input" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} maxLength={300} placeholder="https://" />
        </label>
      </div>
      <button className="btn-primary" disabled={busy || text.trim().length < 30 || sourceName.trim().length < 2} onClick={submit}>
        <ClipboardPaste size={16} /> {busy ? "AI가 구조화하는 중…" : "AI로 구조화해서 등록"}
      </button>
      {error && (
        <p className="text-sm text-danger" role="alert">
          {error}
        </p>
      )}
      {saved && (
        <div className="rounded-md border border-ok/60 p-3 text-sm" role="status">
          <p className="font-bold">등록했어요: {saved.title}</p>
          <p className="mt-1 text-slate-600">
            {saved.type} · {saved.org} · 마감 {fmt(latest(saved).deadline)} · 조건 {saved.required.length}개 · 신뢰도 {saved.confidence}
          </p>
          {/* 새 공고는 목록을 다시 받아야 보이므로 페이지 전체를 새로 연다 */}
          <a href={`/opportunities/${saved.id}`} className="mt-2 inline-block font-semibold underline">
            등록된 공고 열기
          </a>
        </div>
      )}
    </div>
  );
}
