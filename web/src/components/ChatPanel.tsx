"use client";
import { useEffect, useRef, useState } from "react";
import { MessageSquareText, Send } from "lucide-react";
import { useStore } from "@/lib/store";
import { answer, verifyCitations } from "@/lib/engine";
import type { ChatAnswer, Opportunity } from "@/lib/types";
import { AiNotice } from "./ui";

type Msg = { role: "user"; text: string } | { role: "bot"; a: ChatAnswer };

// 실제 공고는 서버에 설정된 AI 제공자가 답한다(근거 문단 번호는 서버에서 대조).
const REAL_SUGGEST = ["지원 자격이 어떻게 되나요?", "언제까지 신청해야 해요?", "어떻게 신청하나요?", "합격하려면 뭐가 필요해요?"];
async function askServer(oppId: string, question: string): Promise<ChatAnswer | null> {
  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ oppId, question }),
    });
    if (!r.headers.get("content-type")?.includes("application/json")) return null;
    const data = await r.json();
    if (r.ok) return data;
    return r.status === 429 ? { text: data.detail, citations: [], held: true } : null;
  } catch {
    return null;
  }
}

const SUGGEST = ["자기소개서 분량 제한이 있어요?", "합격하려면 TOEIC 몇 점이 필요해요?", "마감이 바뀌었나요?", "제가 지원할 수 있나요?"];

export function ChatPanel({ opp }: { opp: Opportunity }) {
  const { profile, mode } = useStore();
  const useAi = mode === "server" && !opp.isVirtual;
  const [busy, setBusy] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (msgs.length) end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [msgs, busy]);

  const ask = async (text: string) => {
    if (!text.trim() || busy) return;
    setMsgs((m) => [...m, { role: "user", text }]);
    setQ("");
    setBusy(true);
    // 실제 공고: 서버 모델에 묻고, 실패하면 브라우저의 규칙 기반 답변으로 대신한다.
    const fromAi = useAi ? await askServer(opp.id, text.slice(0, 300)) : null;
    const a = verifyCitations(fromAi ?? answer(text, opp, profile), opp);
    setMsgs((m) => [...m, { role: "bot", a }]);
    setBusy(false);
  };

  return (
    <aside className="card flex h-fit max-h-[calc(100vh-7rem)] flex-col lg:sticky lg:top-20">
      <div className="border-b border-slate-100 p-4">
        <h2 className="flex items-center gap-1.5 font-bold">
          <MessageSquareText size={16} className="text-accent" /> 공고 질문하기
        </h2>
        <p className="text-xs text-slate-500">이 공고 원문만 근거로 답해요. 근거가 없으면 답을 보류해요.</p>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4 text-sm">
        {msgs.length === 0 && (
          <div className="flex flex-wrap gap-1.5">
            {(useAi ? REAL_SUGGEST : SUGGEST).map((x) => (
              <button key={x} onClick={() => ask(x)} className="chip border border-slate-300 bg-panel px-2.5 py-1 text-slate-600 hover:bg-slate-50">
                {x}
              </button>
            ))}
          </div>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-navy px-3 py-2 text-white">
              {m.text}
            </div>
          ) : (
            <div
              key={i}
              className={`w-fit max-w-[90%] rounded-2xl rounded-bl-sm px-3 py-2 ${m.a.held ? "border border-amber-300 bg-amber-50" : "bg-paper"}`}
            >
              {m.a.held && <span className="chip mb-1 bg-amber-200 text-amber-800">확인 필요 · 답변 보류</span>}
              <p>{m.a.text}</p>
              {m.a.citations.length > 0 && (
                <div className="mt-1 flex gap-1">
                  {m.a.citations.map((c) => (
                    <a key={c.sectionId} href={opp.source.url} target="_blank" rel="noopener noreferrer" className="chip bg-blue-100 text-blue-700">
                      원문 근거 · {c.sectionId} v{c.version}
                    </a>
                  ))}
                </div>
              )}
            </div>
          ),
        )}
        {busy && <p className="text-xs text-slate-500">원문에서 근거를 찾는 중…</p>}
        <div ref={end} />
      </div>
      <form
        className="flex gap-2 border-t border-slate-100 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          ask(q);
        }}
      >
        <input className="input" placeholder="질문을 입력하세요" maxLength={300} value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn-primary !px-3" aria-label="보내기" disabled={busy}>
          <Send size={16} />
        </button>
      </form>
      <AiNotice className="px-4 pb-3" />
    </aside>
  );
}
