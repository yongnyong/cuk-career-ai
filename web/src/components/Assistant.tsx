"use client";
// 모든 페이지에서 같은 대화를 쓰는 개인 진로 비서(api/app/assistant).
// 로그인 계정은 기억·대화가 서버 DB에 저장되고, 시연 계정은 서버 메모리에 잠시 둔다(재시작하면 사라짐).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Brain, MessageSquareText, Send, Trash2, X } from "lucide-react";
import { useStore } from "@/lib/store";
import { recommend } from "@/lib/engine";
import type { Profile } from "@/lib/types";
import { AiNotice } from "./ui";

type OppRef = { id: string; title: string; mock: boolean; open: boolean };
export type AssistantMsg = { role: "user" | "bot"; text: string; opportunities?: OppRef[]; memoryUpdated?: boolean; needsConfirmation?: string[]; held?: boolean };
type Fact = { id: string; kind: string; value: string; source: string; progress?: string | null };
type ChatResult = { answer: string; memoryUpdated?: boolean; needsConfirmation?: string[]; opportunities?: OppRef[] };

// 스킬트리에서 지금 열어 둔 노드. skillId는 비서 카탈로그(직무 기본 노드)에 있는 노드만 넣는다(없는 ID는 비서가 답을 멈춘다)
export type AssistantNode = { name: string; skillId?: string };

const CONVERSATION = "main";
const START = ["나한테 맞는 공고 있어?", "다음에 뭘 준비하면 돼?", "Python 7일 학습 계획 짜줘"];
const KIND: Record<string, string> = {
  interest: "관심", goal: "목표", education: "학력", training: "교육", certification: "자격증", job: "근무", internship: "인턴",
  project: "프로젝트", activity: "활동", award: "수상", skill: "기술", department: "학과", grade: "학년", study_time: "공부 시간",
};
const noop = () => () => {};
const isDemo = (id: string | null) => !!id && id.startsWith("demo-");

// 지금 보는 화면을 비서에게 알린다. 레이아웃의 공급자에서 주소를 읽으면 동적 페이지를 미리 만들 수 없어 대화 창이 넘긴다
function screen(path: string, profile: Profile | null, node: AssistantNode | null) {
  const [first = "", second] = path.split("/").filter(Boolean);
  if (first === "opportunities" && second) return { page: "opportunities", opportunityId: decodeURIComponent(second) };
  if (first === "tree") return { page: "tree", ...(profile?.jobId ? { jobId: profile.jobId } : {}), ...(node?.skillId ? { skillId: node.skillId } : {}) };
  return { page: /^[a-z][a-z0-9-]{0,40}$/.test(first) ? first : "home" };
}

// 비서 답변의 **굵게**만 굵은 글씨로 보여준다(나머지는 글자 그대로. HTML로 해석하지 않는다)
function withBold(text: string) {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part));
}

const toMsg = (r: ChatResult): AssistantMsg => ({
  role: "bot", text: r.answer, opportunities: r.opportunities, memoryUpdated: r.memoryUpdated, needsConfirmation: r.needsConfirmation,
});

function errorText(d: unknown): string {
  const detail = (d as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof (detail as { message?: unknown }).message === "string") return (detail as { message: string }).message;
  return "지금은 답변을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요.";
}

type Ctx = {
  msgs: AssistantMsg[]; busy: boolean; saved: boolean; ask: (q: string, path: string) => void; clear: () => void;
  memory: Fact[] | null; loadMemory: () => void; forget: (id: string) => void;
  node: AssistantNode | null; setNode: (n: AssistantNode | null) => void; open: boolean; setOpen: (o: boolean) => void;
};
const AssistantContext = createContext<Ctx | null>(null);

export function AssistantProvider({ children }: { children: React.ReactNode }) {
  const s = useStore();
  const owner = s.session;
  const server = s.mode === "server" && !!owner && !isDemo(owner);
  // 대화는 계정(owner)별로 들고, 계정이 바뀌면 다른 계정의 대화를 보여주지 않는다
  const [conv, setConv] = useState<{ owner: string | null; msgs: AssistantMsg[] }>({ owner: null, msgs: [] });
  const msgs = useMemo(() => (conv.owner === owner ? conv.msgs : []), [conv, owner]);
  const setMsgs = useCallback((f: (m: AssistantMsg[]) => AssistantMsg[]) => setConv((c) => ({ owner, msgs: f(c.owner === owner ? c.msgs : []) })), [owner]);
  const [busy, setBusy] = useState(false);
  const [mem, setMem] = useState<{ owner: string | null; facts: Fact[] } | null>(null);
  const memory = mem?.owner === owner ? mem.facts : null;
  const [node, setNode] = useState<AssistantNode | null>(null);
  // 넓은 화면에서는 처음부터 열어 둔다. 휴대폰에서는 화면을 가리므로 닫아 둔다.
  const [open, setOpen] = useState(() => typeof window === "undefined" || window.matchMedia("(min-width: 640px)").matches);

  // 웹 규칙 엔진이 이 학생에게 고른 공고(직무·역량·전공 기준). 비서는 이 안에서 공고를 골라 조건을 다시 판정한다
  const focus = useMemo(
    () => (s.profile ? recommend(s.opportunities, s.profile, s.nowDate).filter((r) => !r.opp.isVirtual).slice(0, 8).map((r) => r.opp.id).join(",") : ""),
    [s.opportunities, s.profile, s.nowDate],
  );

  // 시연·비로그인: 서버가 HttpOnly 쿠키로 브라우저를 구분하고, 여기서는 시연 계정 이름만 보낸다(계정이 바뀌면 다른 대화)
  const headers = useCallback((): Record<string, string> => {
    const f: Record<string, string> = focus ? { "x-assistant-focus": focus } : {};
    if (server) return f;
    const h: Record<string, string> = { ...f, "x-demo-id": (owner ?? "guest").replace(/[^a-z0-9-]/g, "").slice(0, 40) || "guest" };
    const p = s.profile;
    if (p) {
      // 비서가 쓰는 항목만 보낸다(아이디·입학년도·지역·출생연도·점수는 보내지 않는다)
      const brief = { departmentId: p.departmentId, grade: p.grade, status: p.status, jobId: p.jobId, careerInterest: p.careerInterest, skills: p.skills, startup: { stage: p.startup?.stage } };
      h["x-demo-profile"] = btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(brief))));
    }
    return h;
  }, [server, owner, s.profile, focus]);

  const call = useCallback(
    (url: string, init: RequestInit = {}) =>
      fetch(`/api/assistant${url}`, { ...init, credentials: "same-origin", headers: { ...(init.body ? { "Content-Type": "application/json" } : {}), ...headers() } }),
    [headers],
  );

  // 계정이 바뀌면 그 계정의 대화를 서버에서 불러온다(없으면 빈 대화)
  useEffect(() => {
    if (!owner) return;
    let live = true;
    call(`/conversations/${CONVERSATION}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { messages: { message: string; result: ChatResult }[] } | null) => {
        if (live && d) setConv({ owner, msgs: d.messages.flatMap((m) => [{ role: "user" as const, text: m.message }, toMsg(m.result)]) });
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [owner, call]);

  const loadMemory = useCallback(() => {
    call("/memory")
      .then((r) => (r.ok ? r.json() : []))
      .then((facts: Fact[]) => setMem({ owner, facts }))
      .catch(() => setMem({ owner, facts: [] }));
  }, [call, owner]);

  const ask = useCallback(
    async (q: string, path: string) => {
      const message = q.trim().slice(0, 500);
      if (!message || busy) return;
      setMsgs((m) => [...m, { role: "user", text: message }]);
      setBusy(true);
      let reply: AssistantMsg;
      try {
        const r = await call("/chat", {
          method: "POST",
          body: JSON.stringify({ message, conversationId: CONVERSATION, requestId: `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`, context: screen(path, s.profile, node) }),
        });
        const d = r.headers.get("content-type")?.includes("application/json") ? await r.json() : null;
        reply = r.ok && d ? toMsg(d) : { role: "bot", text: errorText(d), held: true };
        if (r.ok && d?.memoryUpdated && memory) loadMemory();
      } catch {
        reply = { role: "bot", text: "서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요.", held: true };
      }
      setMsgs((m) => [...m, reply]);
      setBusy(false);
    },
    [busy, setMsgs, call, s.profile, node, memory, loadMemory],
  );

  const clear = useCallback(() => {
    setMsgs(() => []);
    void call(`/conversations/${CONVERSATION}`, { method: "DELETE" });
  }, [call, setMsgs]);

  const forget = useCallback(
    (id: string) => {
      setMem((m) => (m ? { ...m, facts: m.facts.filter((f) => f.id !== id) } : m));
      void call(`/memory/${encodeURIComponent(id)}`, { method: "DELETE" });
    },
    [call],
  );

  return <AssistantContext.Provider value={{ msgs, busy, saved: server, ask, clear, memory, loadMemory, forget, node, setNode, open, setOpen }}>{children}</AssistantContext.Provider>;
}

const useAssistant = () => useContext(AssistantContext)!;

// 스킬트리 화면이 열어 둔 노드를 비서에게 알린다(노드를 닫거나 화면을 떠나면 지운다)
export function useAssistantNode(node: AssistantNode | null) {
  const { setNode } = useAssistant();
  const name = node?.name;
  const skillId = node?.skillId;
  useEffect(() => {
    setNode(name ? { name, skillId } : null);
    return () => setNode(null);
  }, [name, skillId, setNode]);
}

// 노드 상세의 "이 노드 물어보기": 챗봇 창을 열고 이 노드를 주제로 바로 묻는다
export function AskNodeButton({ node }: { node: AssistantNode }) {
  const { ask, busy, setOpen } = useAssistant();
  const path = usePathname();
  return (
    <button
      className="btn-ghost mt-3 w-full justify-center text-xs"
      disabled={busy}
      onClick={() => { setOpen(true); ask(`'${node.name}' 노드는 어떻게 준비하면 돼?`, path); }}
    >
      <MessageSquareText size={14} /> 이 노드 AI에게 물어보기
    </button>
  );
}

function MemoryPanel() {
  const { memory, forget, saved } = useAssistant();
  if (!memory) return <p className="text-xs text-ink/60">불러오는 중…</p>;
  return (
    <div className="space-y-1.5 text-xs">
      <p className="text-ink/60">
        대화에서 직접 말한 내용만 기억해요. {saved ? "내 계정에 저장되고, 지우면 다음 답변부터 쓰지 않아요." : "시연 중에는 서버 메모리에만 잠시 둬요."}
      </p>
      {memory.length === 0 ? (
        <p className="text-ink/60">아직 기억한 내용이 없어요. 예: &quot;나 SQLD 준비 중이야&quot;, &quot;하루 30분 공부할 수 있어&quot;</p>
      ) : (
        <ul className="space-y-1">
          {memory.map((f) => (
            <li key={f.id} className="flex items-center gap-2 rounded border border-line bg-paper px-2 py-1">
              <span className="rounded bg-navy px-1.5 py-0.5 text-[10px] text-white">{KIND[f.kind] ?? f.kind}</span>
              <span className="flex-1">{f.value}</span>
              <button onClick={() => forget(f.id)} aria-label={`${f.value} 잊기`} className="text-ink/50 hover:text-ink">
                <Trash2 size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AssistantChat({ large = false }: { large?: boolean }) {
  const { msgs, busy, saved, ask, clear, loadMemory, node } = useAssistant();
  const { profile } = useStore();
  const path = usePathname();
  const [q, setQ] = useState("");
  const [showMemory, setShowMemory] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (msgs.length) end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [msgs, busy]);
  const send = (text: string) => {
    ask(text, path);
    setQ("");
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className={`min-h-0 flex-1 space-y-3 overflow-y-auto p-4 ${large ? "max-h-[26rem]" : ""}`}>
        {showMemory ? (
          <MemoryPanel />
        ) : (
          <>
            {msgs.length === 0 && (
              <p className="text-sm text-ink/70">
                {profile
                  ? "내 학과·학년·목표 직무·스킬트리와 대화에서 말한 내용을 기억해서 답해요. 공고 조건은 서버가 직접 판정해요."
                  : "로그인하거나 시연 계정으로 들어오면 내 프로필에 맞춰 답해요."}
              </p>
            )}
            {msgs.map((m, i) =>
              m.role === "user" ? (
                <p key={i} className="ml-auto w-fit max-w-[85%] rounded-lg bg-navy px-3 py-2 text-sm text-white">{m.text}</p>
              ) : (
                <div key={i} className={`max-w-[92%] rounded-lg border px-3 py-2 text-sm ${m.held ? "border-dashed border-line bg-paper" : "border-line bg-panel"}`}>
                  <p className="whitespace-pre-line">{withBold(m.text)}</p>
                  {!!m.needsConfirmation?.length && (
                    <ul className="mt-2 list-disc pl-4 text-xs text-ink/70">
                      {m.needsConfirmation.map((x) => <li key={x}>{x}</li>)}
                    </ul>
                  )}
                  {!!m.opportunities?.length && (
                    <ul className="mt-2 flex flex-wrap gap-1.5">
                      {m.opportunities.map((o) => (
                        <li key={o.id}>
                          <Link href={`/opportunities/${encodeURIComponent(o.id)}`} className="rounded bg-gold px-1.5 py-0.5 text-[11px] font-bold text-on-gold hover:underline">
                            {o.mock ? "[가상] " : ""}{o.title.slice(0, 22)}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                  {m.memoryUpdated && (
                    <button className="mt-2 flex items-center gap-1 text-[11px] text-ink/60 hover:underline" onClick={() => { loadMemory(); setShowMemory(true); }}>
                      <Brain size={11} /> 기억에 저장했어요 · 확인하기
                    </button>
                  )}
                </div>
              ),
            )}
            {busy && <p className="text-sm text-ink/60">답변을 만드는 중…</p>}
          </>
        )}
        <div ref={end} />
      </div>
      <div className="border-t border-line p-3">
        {node && path.startsWith("/tree") && !showMemory && (
          <p className="mb-2 truncate text-[11px] text-ink/60">지금 보는 노드: <strong>{node.name}</strong> · 이 노드 기준으로 답해요</p>
        )}
        {!showMemory && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {START.map((x) => (
              <button key={x} className="rounded-full border border-line px-2.5 py-1 text-xs hover:bg-paper" disabled={busy} onClick={() => send(x)}>
                {x}
              </button>
            ))}
          </div>
        )}
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); setShowMemory(false); send(q); }}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            maxLength={500}
            placeholder="진로·공고·공부 계획을 물어보세요"
            aria-label="챗봇에게 질문"
            className="min-w-0 flex-1 rounded-md border border-line bg-panel px-3 py-2 text-sm"
          />
          <button className="btn-primary !px-3" disabled={busy || !q.trim()} aria-label="보내기">
            <Send size={16} />
          </button>
        </form>
        <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-ink/55">
          <button className="flex items-center gap-1 hover:underline" onClick={() => { if (!showMemory) loadMemory(); setShowMemory(!showMemory); }}>
            <Brain size={11} /> {showMemory ? "대화로 돌아가기" : "AI가 기억하는 나"}
          </button>
          <span className="flex items-center gap-2">
            <span>{saved ? "내 계정에 저장" : "시연: 잠시만 보관"}</span>
            {msgs.length > 0 && !showMemory && (
              <button className="flex items-center gap-1 hover:underline" onClick={clear}>
                <Trash2 size={11} /> 대화 지우기
              </button>
            )}
          </span>
        </div>
        <AiNotice className="mt-1" />
      </div>
    </div>
  );
}

// 홈 화면의 큰 챗봇
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
  const { open, setOpen } = useAssistant();
  // 프로필은 브라우저 저장소에서 읽으므로, 서버 렌더와 어긋나지 않게 브라우저에서만 그린다
  const mounted = useSyncExternalStore(noop, () => true, () => false);
  if (!mounted) return null;
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
