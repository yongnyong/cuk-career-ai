"use client";
// 클라이언트 상태. 서버(api/) 연결 전까지 브라우저 localStorage에만 저장한다(개인정보 없음: 가명 ID·학과·학년만).
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { SEED_OPPORTUNITIES } from "./data/opportunities";
import { evaluate, latest, syncNotices, fmt } from "./engine";
import type { Notice, Opportunity, Profile, SkillState } from "./types";

export const DEMO_START = "2026-11-16T09:00:00+09:00";
const KEY = "cuk-career-ai:v1";

interface State {
  profile: Profile | null;
  now: string; // 가상 시계 (시연용)
  opportunities: Opportunity[];
  followed: string[];
  quests: Record<string, Record<string, boolean>>;
  notices: Notice[];
  newOpps: string[];
}

const initial = (): State => ({
  profile: null,
  now: DEMO_START,
  opportunities: SEED_OPPORTUNITIES,
  followed: [],
  quests: {},
  notices: [],
  newOpps: [],
});

interface Ctx extends State {
  ready: boolean; // localStorage 복원 완료 여부
  nowDate: Date;
  setProfile: (p: Profile) => void;
  setSkill: (skill: string, st: SkillState) => void;
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

  // 브라우저 저장소(외부 시스템)에서 한 번 복원한다
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setState({ ...initial(), ...JSON.parse(raw) });
    } catch {
      /* 저장소 사용 불가 시 기본값 */
    }
    setReady(true);
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

  // 상태 변경 후 알림 재계산
  const update = useCallback((fn: (s: State) => State) => {
    setState((prev) => {
      const s = fn(prev);
      return { ...s, notices: syncNotices(s.notices, s.opportunities, s.followed, new Date(s.now)) };
    });
  }, []);

  const api = useMemo<Ctx>(
    () => ({
      ...state,
      ready,
      nowDate: new Date(state.now),
      setProfile: (p) => update((s) => ({ ...s, profile: p })),
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
      deleteMyData: () =>
        update((s) => ({ ...s, profile: null, followed: [], quests: {}, notices: [], newOpps: [] })),
      resetDemo: () => update(() => initial()),
    }),
    [state, update, ready],
  );

  return <StoreCtx.Provider value={api}>{children}</StoreCtx.Provider>;
}

export function useStore() {
  const c = useContext(StoreCtx);
  if (!c) throw new Error("StoreProvider 밖에서 useStore 사용");
  return c;
}
