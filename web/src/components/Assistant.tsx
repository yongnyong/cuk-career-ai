"use client";
// 모든 페이지에서 같은 대화를 쓰는 개인 맞춤 챗봇. 로그인 계정은 대화가 서버 DB에 저장되고 어느 기기에서든 이어진다.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, MessageSquareText, Send, Trash2, X } from "lucide-react";
import { useStore } from "@/lib/store";
import { recommend } from "@/lib/engine";
import { AiNotice } from "./ui";

type Citation = { oppId: string; sectionId: string; title: string; version: number };
export type AssistantMsg = { role: "user" | "bot"; text: string; citations?: Citation[]; held?: boolean; suggestions?: string[] };

const isDemo = (id: string | null) => !!id && id.startsWith("demo-");
const START = ["나한테 맞는 공고 있어?", "다음에 뭘 준비하면 돼?", "마감이 가장 가까운 공고는?"];

// 지금 보는 페이지(path)는 대화 창이 넘긴다. 레이아웃의 공급자에서 주소를 읽으면 동적 페이지를 미리 만들 수 없다
type Ctx = { msgs: AssistantMsg[]; busy: boolean; saved: boolean; ask: (q: string, path: string) => void; clear: () => void };
const AssistantContext = createContext<Ctx | null>(null);

export function AssistantProvider({ children }: { children: React.ReactNode }) {
  const s = useStore();
  // 대화는 계정(owner)별로 들고, 계정이 바뀌면 다른 계정의 대화를 보여주지 않는다
  const [conv, setConv] = useState<{ owner: string | null; msgs: AssistantMsg[] }>({ owner: null, msgs: [] });
  const owner = s.session;
  const msgs = useMemo(() => (conv.owner === owner ? conv.msgs : []), [conv, owner]);
  const setMsgs = useCallback((f: (m: AssistantMsg[]) => AssistantMsg[]) => setConv((c) => ({ owner, msgs: f(c.owner === owner ? c.msgs : []) })), [owner]);
  const [busy, setBusy] = useState(false);
  const server = s.mode === "server" && !!s.session && !isDemo(s.session);

  // 계정이 바뀌면 그 계정의 대화를 서버에서 불러온다(시연 계정·로그아웃은 빈 대화)
  useEffect(() => {
    if (!server) return;
    let live = true;
    fetch("/api/assistant/history", { credentials: "same-origin" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => live && d && setConv({ owner, msgs: d.messages }))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [server, owner]);

  const candidates = useMemo(() => {
    if (!s.profile) return [];
    // 규칙 엔진이 이 학생에게 고른 공고와 판정. 서버는 공고 내용을 DB에서 다시 읽는다
    return recommend(s.opportunities, s.profile, s.nowDate)
      .filter((r) => !r.opp.isVirtual)
      .slice(0, 6)
      .map((r) => ({ id: r.opp.id, status: r.verdict }));
  }, [s.opportunities, s.profile, s.nowDate]);

  const ask = useCallback(
    async (q: string, path: string) => {
      const oppId = path.startsWith("/opportunities/") ? decodeURIComponent(path.split("/")[2] ?? "") : null;
      const question = q.trim().slice(0, 300);
      if (!question || busy) return;
      const before = msgs;
      setMsgs((m) => [...m, { role: "user", text: question }]);
      setBusy(true);
      let reply: AssistantMsg;
      try {
        const r = await fetch("/api/assistant", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            question,
            path,
            oppId,
            candidates,
            nextSkill: s.careerPath?.recommendedQuest?.skillId ?? null,
            ...(server ? {} : { profile: s.profile, history: before.slice(-6).map(({ role, text }) => ({ role, text })) }),
          }),
        });
        const d = r.headers.get("content-type")?.includes("application/json") ? await r.json() : null;
        reply = r.ok && d ? d : { role: "bot", text: d?.detail ?? "지금은 답변을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요.", held: true };
      } catch {
        reply = { role: "bot", text: "서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요.", held: true };
      }
      setMsgs((m) => [...m, { ...reply, role: "bot" }]);
      setBusy(false);
    },
    [busy, msgs, setMsgs, candidates, s.careerPath, s.profile, server],
  );

  const clear = useCallback(() => {
    setMsgs(() => []);
    if (server) void fetch("/api/assistant/history", { method: "DELETE", credentials: "same-origin" });
  }, [server, setMsgs]);

  return <AssistantContext.Provider value={{ msgs, busy, saved: server, ask, clear }}>{children}</AssistantContext.Provider>;
}

const useAssistant = () => useContext(AssistantContext)!;

export function AssistantChat({ large = false }: { large?: boolean }) {
  const { msgs, busy, saved, ask, clear } = useAssistant();
  const { profile } = useStore();
  const path = usePathname();
  const [q, setQ] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (msgs.length) end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [msgs, busy]);
  const last = [...msgs].reverse().find((m) => m.role === "bot");
  const suggestions = last?.suggestions?.length ? last.suggestions : START;
  const send = (text: string) => {
    ask(text, path);
    setQ("");
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className={`min-h-0 flex-1 space-y-3 overflow-y-auto p-4 ${large ? "max-h-[26rem]" : ""}`}>
        {msgs.length === 0 && (
          <p className="text-sm text-ink/70">
            {profile
              ? "내 학과·학년·목표 직무와 스킬트리를 보고 답해요. 공고 내용은 원문 문단을 근거로 붙여요."
              : "로그인하거나 시연 계정으로 들어오면 내 프로필에 맞춰 답해요."}
          </p>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? (
            <p key={i} className="ml-auto w-fit max-w-[85%] rounded-lg bg-navy px-3 py-2 text-sm text-white">{m.text}</p>
          ) : (
            <div key={i} className={`max-w-[92%] rounded-lg border px-3 py-2 text-sm ${m.held ? "border-dashed border-line bg-paper" : "border-line bg-panel"}`}>
              <p className="whitespace-pre-line">{m.text}</p>
              {!!m.citations?.length && (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {m.citations.map((c) => (
                    <li key={c.oppId + c.sectionId}>
                      <Link href={`/opportunities/${encodeURIComponent(c.oppId)}`} className="rounded bg-gold px-1.5 py-0.5 text-[11px] font-bold text-on-gold hover:underline">
                        {c.title.slice(0, 18)} {c.sectionId}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ),
        )}
        {busy && <p className="text-sm text-ink/60">답변을 만드는 중…</p>}
        <div ref={end} />
      </div>
      <div className="border-t border-line p-3">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {suggestions.map((x) => (
            <button key={x} className="rounded-full border border-line px-2.5 py-1 text-xs hover:bg-paper" disabled={busy} onClick={() => send(x)}>
              {x}
            </button>
          ))}
        </div>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); send(q); }}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            maxLength={300}
            placeholder="진로·공고·준비할 것을 물어보세요"
            aria-label="챗봇에게 질문"
            className="min-w-0 flex-1 rounded-md border border-line bg-panel px-3 py-2 text-sm"
          />
          <button className="btn-primary !px-3" disabled={busy || !q.trim()} aria-label="보내기">
            <Send size={16} />
          </button>
        </form>
        <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-ink/55">
          <span>{saved ? "대화는 내 계정에 저장돼 어느 페이지에서든 이어져요." : "시연·비로그인 대화는 저장하지 않아요."}</span>
          {msgs.length > 0 && (
            <button className="flex items-center gap-1 hover:underline" onClick={clear}>
              <Trash2 size={11} /> 대화 지우기
            </button>
          )}
        </div>
        <AiNotice className="mt-1" />
      </div>
    </div>
  );
}

// 홈 화면 상단의 큰 챗봇
export function AssistantHero() {
  return (
    <section className="window flex flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b-2 border-edge bg-navy px-4 py-2 text-white">
        <Bot size={18} />
        <h2 className="font-bold">CUK Career AI에게 물어보기</h2>
      </div>
      <AssistantChat large />
    </section>
  );
}

// 다른 모든 페이지 왼쪽 아래의 챗봇 버튼
export function AssistantDock() {
  const path = usePathname();
  const { profile } = useStore();
  const [open, setOpen] = useState(false);
  if (path === "/" && profile) return null; // 홈에는 큰 챗봇이 있다
  if (path.startsWith("/print")) return null;
  return (
    <div className="fixed bottom-20 left-4 z-40 sm:bottom-6 print:hidden">
      {open ? (
        <div className="window flex h-[min(34rem,calc(100vh-8rem))] w-[min(24rem,calc(100vw-2rem))] flex-col overflow-hidden">
          <div className="flex items-center gap-2 border-b-2 border-edge bg-navy px-3 py-2 text-white">
            <Bot size={16} />
            <span className="flex-1 text-sm font-bold">CUK Career AI</span>
            <button onClick={() => setOpen(false)} aria-label="챗봇 닫기">
              <X size={16} />
            </button>
          </div>
          <AssistantChat />
        </div>
      ) : (
        <button className="btn-gold shadow-lg" onClick={() => setOpen(true)} aria-label="챗봇 열기">
          <MessageSquareText size={18} /> 물어보기
        </button>
      )}
    </div>
  );
}
