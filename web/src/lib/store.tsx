"use client";
// 클라이언트 상태.
// - 서버 모드: 계정·세션은 API 서버가 관리하고(HttpOnly 쿠키), 내 데이터는 서버에 저장한다.
// - 로컬 모드: API 서버에 닿지 않을 때의 대체 동작. 계정이 이 브라우저 안에서만 유효하다(비밀번호는 salt+PBKDF2 해시).
// 공고 목록과 가상 시계는 아직 브라우저에만 있다.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { SEED_OPPORTUNITIES } from "./data/opportunities";
import { applyOverrides, type CatalogOverrides } from "./data/catalog";
import { evaluate, latest, syncNotices, fmt } from "./engine";
import type { Notice, Opportunity, Profile, SkillState } from "./types";

export const DEMO_START = "2026-11-16T09:00:00+09:00";
const KEY = "cuk-career-ai:v2";

interface UserData {
  profile: Profile | null;
  followed: string[];
  quests: Record<string, Record<string, boolean>>;
  notices: Notice[];
  newOpps: string[];
}
interface Account {
  salt: string;
  hash: string; // 시연용 계정은 빈 문자열(비밀번호 없음)
  data: UserData;
}
const isCollected = (o: Opportunity) => /^(cuk|kst|w24|man)-/.test(o.id); // 서버 수집 공고(학교 공지·K-Startup·고용24)
// 실제 공고가 있으면 실제 계정에는 가상 공고를 보여주지 않는다(시연용 계정은 둘 다 본다)
const visibleOpps = (s: { opportunities: Opportunity[]; session: string | null }, isAdmin: boolean) =>
  !isAdmin && !isDemo(s.session) && s.opportunities.some(isCollected) ? s.opportunities.filter((o) => !o.isVirtual) : s.opportunities;
const isDemo = (id: string | null) => !!id && id.startsWith("demo-"); // 시연용 계정은 서버에 저장하지 않는다

// API 호출. 서버에 닿지 않거나 JSON이 아니면 null(= 서버 없음)
async function call(path: string, method = "GET", body?: unknown) {
  try {
    const r = await fetch("/api" + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      credentials: "same-origin",
    });
    if (!r.headers.get("content-type")?.includes("application/json")) return null;
    return { ok: r.ok, status: r.status, data: await r.json() };
  } catch {
    return null;
  }
}
const errorOf = (data: { detail?: unknown }) => (typeof data.detail === "string" ? data.detail : "요청을 처리하지 못했어요.");
// 서버가 준 내 데이터에서 아는 필드만 꺼낸다
const fromServer = (st: Partial<UserData> | null): UserData => ({ ...emptyUser(), ...(st ? pickKeys(st) : {}) });
const pickKeys = (st: Partial<UserData>): Partial<UserData> => ({
  ...(st.profile !== undefined && { profile: st.profile }),
  ...(Array.isArray(st.followed) && { followed: st.followed }),
  ...(st.quests && { quests: st.quests }),
  ...(Array.isArray(st.notices) && { notices: st.notices }),
  ...(Array.isArray(st.newOpps) && { newOpps: st.newOpps }),
});

const emptyUser = (): UserData => ({ profile: null, followed: [], quests: {}, notices: [], newOpps: [] });
const pickUser = (s: State): UserData => ({
  profile: s.profile,
  followed: s.followed,
  quests: s.quests,
  notices: s.notices,
  newOpps: s.newOpps,
});

async function hashPassword(salt: string, pw: string) {
  // 느린 KDF(PBKDF2)로 무차별 대입을 어렵게 한다. 서버 연결 시에는 서버에서 argon2로 처리한다.
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(pw), "PBKDF2", false, ["deriveBits"]);
  const buf = await crypto.subtle.deriveBits({ name: "PBKDF2", salt: enc.encode(salt), iterations: 600_000, hash: "SHA-256" }, key, 256);
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
}

interface State {
  session: string | null; // 로그인한 아이디
  users: Record<string, Account>;
  profile: Profile | null;
  now: string; // 가상 시계 (시연용)
  opportunities: Opportunity[];
  followed: string[];
  quests: Record<string, Record<string, boolean>>;
  notices: Notice[];
  newOpps: string[];
}

const initial = (): State => ({
  session: null,
  users: {},
  profile: null,
  now: DEMO_START,
  opportunities: SEED_OPPORTUNITIES,
  followed: [],
  quests: {},
  notices: [],
  newOpps: [],
});

interface Ctx extends State {
  ready: boolean; // 저장소 복원과 서버 세션 확인 완료 여부
  mode: "server" | "local";
  isAdmin: boolean;
  catalog: CatalogOverrides; // 관리자가 고친 직무·스킬
  catalogVersion: number;
  saveCatalog: (next: CatalogOverrides) => Promise<string | null>;
  // 관리자 계정: 실제·가상 공고를 모두 보고 서버 현황을 볼 수 있다
  nowDate: Date;
  signup: (id: string, pw: string) => Promise<string | null>; // 실패 시 사유 반환
  login: (id: string, pw: string) => Promise<string | null>;
  loginDemo: (id: string, profile: Profile) => void;
  logout: () => void;
  setProfile: (p: Profile) => void;
  setSkill: (skill: string, st: SkillState) => void;
  setScore: (skill: string, value: string) => void; // 점수·등급 저장(값이 있으면 완료로 표시)
  follow: (oppId: string) => void;
  unfollow: (oppId: string) => void;
  toggleQuest: (oppId: string, item: string) => void;
  setNow: (iso: string) => void;
  addOpportunity: (o: Opportunity) => void;
  approve: (oppId: string) => void;
  correctDeadline: (oppId: string, newDeadline: string) => void;
  clearNew: () => void;
  deleteMyData: () => void;
  resetDemo: () => void;
}

const StoreCtx = createContext<Ctx | null>(null);

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<State>(initial);
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState<"server" | "local">("local");
  // 관리자가 고친 테크트리. 바뀔 때마다 catalogVersion을 올려 화면을 다시 그린다
  const [catalog, setCatalog] = useState<CatalogOverrides>({ skills: {}, jobs: {} });
  const [catalogVersion, setCatalogVersion] = useState(0);
  const [isAdmin, setIsAdmin] = useState(false); // 서버가 알려준 관리자 여부(저장하지 않는다)

  // 브라우저 저장소(외부 시스템)에서 한 번 복원한다
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        // 저장된 공고 목록에 없는 가상 공고(나중에 추가된 것)는 채워 넣는다
        const have = new Set((saved.opportunities ?? []).map((o: Opportunity) => o.id));
        const opportunities = [...(saved.opportunities ?? []), ...SEED_OPPORTUNITIES.filter((o) => !have.has(o.id))];
        setState({ ...initial(), ...saved, opportunities });
      }
    } catch {
      /* 저장소 사용 불가 시 기본값 */
    }
    // 서버 세션 확인: 200이면 서버 데이터로 시작, 401이면 로그아웃 상태, 응답이 없으면 로컬 모드
    Promise.all([call("/me"), call("/catalog")]).then(([r, c]) => {
      if (c?.ok && c.data && typeof c.data === "object") {
        applyOverrides(c.data);
        setCatalog({ skills: c.data.skills ?? {}, jobs: c.data.jobs ?? {} });
        setCatalogVersion((v) => v + 1);
      }
      if (r && (r.ok || r.status === 401)) {
        setMode("server");
        setIsAdmin(r.ok && r.data.admin === true);
        setState((s) =>
          r.ok ? { ...s, ...fromServer(r.data.state), session: r.data.id, now: new Date().toISOString() } : isDemo(s.session) ? s : { ...s, ...emptyUser(), session: null },
        );
      }
      setReady(true);
    });
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (!ready) return;
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      /* 무시 */
    }
  }, [state, ready]);

  // 서버 모드: 내 데이터가 바뀌면 잠시 모아 서버에 저장
  const { session, profile, followed, quests, notices, newOpps } = state;
  useEffect(() => {
    if (!ready || mode !== "server" || !session || isDemo(session)) return;
    const t = setTimeout(() => call("/me/state", "PUT", { state: { profile, followed, quests, notices, newOpps } }), 600);
    return () => clearTimeout(t);
  }, [ready, mode, session, profile, followed, quests, notices, newOpps]);

  // 상태 변경 후 알림 재계산
  const update = useCallback((fn: (s: State) => State) => {
    setState((prev) => {
      let s = fn(prev);
      s = { ...s, notices: syncNotices(s.notices, s.opportunities, s.followed, new Date(s.now), s.quests) };
      // 로그인 중이면 계정별 데이터에 반영
      if (s.session && s.users[s.session])
        s = { ...s, users: { ...s.users, [s.session]: { ...s.users[s.session], data: pickUser(s) } } };
      return s;
    });
  }, []);

  // 서버가 수집한 실제 공고. 이전에 받아 둔 실제 공고는 서버 목록으로 바꿔 끼운다
  useEffect(() => {
    if (!ready) return;
    call("/opportunities").then((r) => {
      if (r?.ok && Array.isArray(r.data))
        update((s) => ({ ...s, opportunities: [...s.opportunities.filter((o) => !isCollected(o)), ...r.data] }));
    });
  }, [ready, update]);

  const api = useMemo<Ctx>(
    () => ({
      ...state,
      opportunities: visibleOpps(state, isAdmin),
      isAdmin,
      catalog,
      catalogVersion,
      saveCatalog: async (next) => {
        const r = await call("/admin/catalog", "PUT", next);
        if (!r?.ok) return r ? errorOf(r.data) : "서버에 연결하지 못했어요.";
        applyOverrides(next);
        setCatalog(next);
        setCatalogVersion((v) => v + 1);
        return null;
      },
      ready,
      mode,
      nowDate: new Date(state.now),
      signup: async (id, pw) => {
        if (mode === "server") {
          const r = await call("/auth/signup", "POST", { id, password: pw });
          if (!r) return "서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요.";
          if (!r.ok) return errorOf(r.data);
          setIsAdmin(r.data.admin === true);
          update((s) => ({ ...s, ...emptyUser(), session: r.data.id, now: new Date().toISOString() }));
          return null;
        }
        if (!/^[a-z0-9_]{4,16}$/.test(id)) return "아이디는 영문 소문자·숫자 4~16자로 입력해 주세요.";
        if (pw.length < 6) return "비밀번호는 6자 이상으로 입력해 주세요.";
        if (state.users[id]) return "이미 사용 중인 아이디예요.";
        const salt = crypto.randomUUID();
        const hash = await hashPassword(salt, pw);
        update((s) => ({ ...s, ...emptyUser(), session: id, users: { ...s.users, [id]: { salt, hash, data: emptyUser() } } }));
        return null;
      },
      login: async (id, pw) => {
        if (mode === "server") {
          const r = await call("/auth/login", "POST", { id, password: pw });
          if (!r) return "서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요.";
          if (!r.ok) return errorOf(r.data);
          setIsAdmin(r.data.admin === true);
          update((s) => ({ ...s, ...fromServer(r.data.state), session: r.data.id, now: new Date().toISOString() }));
          return null;
        }
        const acc = state.users[id];
        const fail = "아이디 또는 비밀번호가 맞지 않아요.";
        if (!acc || !acc.hash) return fail;
        if ((await hashPassword(acc.salt, pw)) !== acc.hash) return fail;
        update((s) => ({ ...s, ...acc.data, session: id }));
        return null;
      },
      loginDemo: (id, profile) =>
        update((s) => ({
          ...s,
          ...emptyUser(),
          ...(s.users[id]?.data ?? { profile }),
          session: id,
          now: DEMO_START,
          users: s.users[id] ? s.users : { ...s.users, [id]: { salt: "", hash: "", data: emptyUser() } },
        })),
      logout: () => {
        if (mode === "server" && !isDemo(state.session)) void call("/auth/logout", "POST");
        setIsAdmin(false);
        update((s) => ({ ...s, ...emptyUser(), session: null }));
      },
      setProfile: (p) => update((s) => ({ ...s, profile: p })),
      setScore: (skill, value) =>
        update((s) => {
          if (!s.profile) return s;
          const scores = { ...s.profile.scores };
          if (value) scores[skill] = value;
          else delete scores[skill];
          const cur = s.profile.skills[skill] ?? "none";
          const skills = { ...s.profile.skills, [skill]: value ? (cur === "none" ? "self" : cur) : cur };
          return { ...s, profile: { ...s.profile, skills, scores } };
        }),
      setSkill: (skill, st) =>
        update((s) => (s.profile ? { ...s, profile: { ...s.profile, skills: { ...s.profile.skills, [skill]: st } } } : s)),
      follow: (id) => update((s) => (s.followed.includes(id) ? s : { ...s, followed: [...s.followed, id] })),
      unfollow: (id) =>
        update((s) => ({
          ...s,
          followed: s.followed.filter((x) => x !== id),
          notices: s.notices.map((n) => (n.oppId === id && n.status === "scheduled" ? { ...n, status: "cancelled" } : n)),
        })),
      toggleQuest: (id, item) =>
        update((s) => ({ ...s, quests: { ...s.quests, [id]: { ...s.quests[id], [item]: !s.quests[id]?.[item] } } })),
      setNow: (iso) => update((s) => ({ ...s, now: iso })),
      addOpportunity: (o) =>
        update((s) => {
          const matched =
            s.profile && (o.jobs.includes(s.profile.jobId) || o.jobs.length === 0) && evaluate(o, s.profile).overall !== "fail";
          const notices = matched
            ? [
                ...s.notices,
                {
                  id: `${o.id}:1:새 기회`,
                  oppId: o.id,
                  version: 1,
                  kind: "새 기회" as const,
                  fireAt: s.now,
                  message: `[새 기회] ${o.title} — 내 스킬트리에 연결됐어요. 마감 ${fmt(latest(o).deadline)}`,
                  status: "sent" as const,
                  idempotencyKey: `${o.id}:1:새 기회`,
                },
              ]
            : s.notices;
          return { ...s, opportunities: [...s.opportunities, o], newOpps: [...s.newOpps, o.id], notices };
        }),
      approve: (id) =>
        update((s) => ({ ...s, opportunities: s.opportunities.map((o) => (o.id === id ? { ...o, reviewed: true } : o)) })),
      correctDeadline: (id, nd) =>
        update((s) => ({
          ...s,
          opportunities: s.opportunities.map((o) => {
            if (o.id !== id) return o;
            const v = latest(o);
            const sections = o.sections.map((sec) =>
              sec.id === "§5" ? { ...sec, text: sec.text.replace(/접수 마감: [^.]+까지/, `접수 마감: ${fmt(nd)}까지`) } : sec,
            );
            return {
              ...o,
              sections,
              versions: [
                ...o.versions,
                {
                  version: v.version + 1,
                  checkedAt: s.now,
                  deadline: nd,
                  changes: [{ field: "마감", before: fmt(v.deadline), after: fmt(nd) }],
                },
              ],
            };
          }),
        })),
      clearNew: () => update((s) => ({ ...s, newOpps: [] })),
      deleteMyData: () => {
        if (mode === "server" && !isDemo(state.session)) void call("/me", "DELETE");
        update((s) => {
          const users = { ...s.users };
          if (s.session) delete users[s.session];
          return { ...s, ...emptyUser(), session: null, users };
        });
      },
      resetDemo: () => update(() => initial()),
    }),
    [state, update, ready, mode, isAdmin, catalog, catalogVersion],
  );

  return <StoreCtx.Provider value={api}>{children}</StoreCtx.Provider>;
}

export function useStore() {
  const c = useContext(StoreCtx);
  if (!c) throw new Error("StoreProvider 밖에서 useStore 사용");
  return c;
}
