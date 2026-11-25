"use client";
import { useEffect, useMemo, useState } from "react";
import { Handshake, Link2, Swords } from "lucide-react";
import { useStore } from "@/lib/store";
import { buildCareerPath } from "@/lib/engine";
import { PERSONAS } from "@/lib/data/personas";
import { careerInterestOf } from "@/lib/interest";
import { evolution, outfitFor, stageTitle } from "@/lib/hayang";
import { decodeDuelist, duel, duelistOf, encodeDuelist, type Duelist, type Together } from "@/lib/duel";
import { HayangFigure } from "@/components/Hayang";

const FRIEND_KEY = "duel-friend";

function Fighter({ who, side }: { who: Duelist; side: "left" | "right" }) {
  const outfit = outfitFor(who.jobId, who.startup);
  const evo = evolution(who.nodes.map((n) => ({ state: n.done ? "self" : "none" })));
  return (
    <div className={`duel-in-${side} flex min-w-0 flex-1 flex-col items-center text-center`}>
      <div className={side === "right" ? "-scale-x-100" : ""}><HayangFigure stage={evo.stage} outfit={outfit} size="sm" /></div>
      <p className="mt-1 truncate text-sm font-bold">{who.name}</p>
      <p className="text-[11px] leading-tight text-ink/60">{who.desc}</p>
      <p className="text-[11px] text-ink/60">{stageTitle(evo.stage, outfit)} · 노드 {evo.done}/{evo.total}</p>
    </div>
  );
}

function togetherText(item: Together, other: string) {
  if (item.type === "both") return { tag: "같이 시작", text: item.name, hint: "둘 다 아직이에요. 날짜를 정해 같이 해요." };
  if (item.type === "teach") return { tag: "내가 도와주기", text: item.name, hint: `내가 먼저 해 봤어요. ${other}에게 알려 줄 수 있어요.` };
  if (item.type === "learn") return { tag: "물어보기", text: item.name, hint: `${other}이(가) 먼저 해 봤어요. 어떻게 했는지 물어봐요.` };
  return { tag: `${item.kind} 짝`, text: `${item.mine} ↔ ${item.theirs}`, hint: "서로 다른 준비지만 같은 분류예요. 일정을 맞춰 같이 해요." };
}

/** 홈의 스킬트리 대전. 승패는 내지 않고, 두 트리를 비교해 둘이 같이 하면 좋은 일을 보여 준다 */
export function Duel() {
  const s = useStore();
  const p = s.profile!;
  const now = s.nowDate;
  const [friend, setFriend] = useState<Duelist | null>(null);
  const [picked, setPicked] = useState<string>("");
  const [copied, setCopied] = useState(false);

  // 친구가 보낸 링크(?vs=)로 들어왔으면 그 트리를 상대로 둔다. 한 번 받은 친구는 이 브라우저에 남겨 둔다
  useEffect(() => {
    const t = window.setTimeout(() => {
      try {
        const code = new URLSearchParams(window.location.search).get("vs");
        const found = decodeDuelist(code ?? localStorage.getItem(FRIEND_KEY) ?? "");
        if (!found) return;
        if (code) localStorage.setItem(FRIEND_KEY, code);
        setFriend(found);
        if (code) setPicked("friend");
      } catch { /* 저장소 없음 */ }
    }, 0);
    return () => window.clearTimeout(t);
  }, []);

  const me = useMemo(() => duelistOf(p.pseudoId, "나", p.jobId, careerInterestOf(p) === "startup", s.careerPath?.tree ?? []), [p, s.careerPath]);
  const rivals = useMemo(() => {
    const demo = PERSONAS.filter((x) => x.profile.pseudoId !== p.pseudoId).map((x) => ({
      id: x.id,
      who: duelistOf(x.label, x.desc, x.profile.jobId, careerInterestOf(x.profile) === "startup", buildCareerPath(x.profile, s.opportunities, now, [], s.startupCatalog).tree),
    }));
    return friend ? [{ id: "friend", who: { ...friend, desc: friend.desc || "친구" } }, ...demo] : demo;
  }, [p.pseudoId, s.opportunities, s.startupCatalog, now, friend]);
  const rival = (rivals.find((x) => x.id === picked) ?? rivals[0])?.who;
  const result = useMemo(() => rival && duel(me, rival), [me, rival]);
  if (!rival || !result || me.nodes.length === 0) return null;

  const share = async () => {
    const url = `${window.location.origin}/?vs=${encodeDuelist({ ...me, desc: "친구" })}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch { window.prompt("이 주소를 복사해 친구에게 보내세요", url); }
  };
  const pct = (x: { done: number; total: number }) => (x.total ? (x.done / x.total) * 100 : 0);

  return (
    <section className="window overflow-hidden" aria-label="스킬트리 대전">
      <div className="flex flex-wrap items-center gap-2 border-b-2 border-edge bg-navy px-4 py-2 text-white">
        <h2 className="flex items-center gap-1.5 font-bold"><Swords size={16} /> 스킬트리 대전</h2>
        <span className="text-xs text-white/75">이기고 지는 것보다, 둘이 같이 하면 좋은 걸 찾아요</span>
        <button className="btn-ghost ml-auto !border-white/40 !px-2 !py-1 text-xs !text-white" onClick={share}>
          <Link2 size={13} /> {copied ? "복사했어요" : "내 대전 링크 복사"}
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5 px-4 pt-3">
        {rivals.map((x) => (
          <button key={x.id} onClick={() => setPicked(x.id)} aria-pressed={x.who === rival}
            className={`chip border px-2 py-1 text-xs ${x.who === rival ? "border-gold bg-gold font-bold text-on-gold" : "border-line bg-panel"}`}>
            {x.id === "friend" ? `친구 ${x.who.name}` : `${x.who.name} · 시연 계정`}
          </button>
        ))}
      </div>

      <div key={rival.name + rival.jobId} className="grid gap-4 p-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,4fr)]">
        <div>
          <div className="flex items-end gap-2">
            <Fighter who={me} side="left" />
            <span className="duel-vs pb-10 font-display text-3xl text-gold">VS</span>
            <Fighter who={rival} side="right" />
          </div>
          <ul className="mt-3 space-y-1.5">
            {result.axes.map((axis) => (
              <li key={axis.kind} className="grid grid-cols-[1fr_4.5rem_1fr] items-center gap-2 text-[11px]">
                <span className="flex h-3 justify-end overflow-hidden rounded-full bg-line">
                  <span className="duel-bar block h-full rounded-full bg-go" style={{ width: `${pct(axis.me)}%` }} />
                </span>
                <span className="text-center font-bold">{axis.kind}<span className="block font-normal text-ink/60">{axis.me.done}/{axis.me.total} · {axis.other.done}/{axis.other.total}</span></span>
                <span className="flex h-3 overflow-hidden rounded-full bg-line">
                  <span className="duel-bar block h-full rounded-full bg-gold" style={{ width: `${pct(axis.other)}%` }} />
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-md border-2 border-ok/60 bg-panel p-3">
          <h3 className="flex items-center gap-1.5 font-bold text-ok"><Handshake size={16} /> 둘이 같이 하면 좋은 것</h3>
          <ul className="mt-2 space-y-2">
            {result.together.map((item, index) => {
              const t = togetherText(item, rival.name);
              return (
                <li key={index} className="duel-item text-sm" style={{ animationDelay: `${0.5 + index * 0.12}s` }}>
                  <span className="chip mr-1.5 bg-ok/15 px-1.5 py-0.5 text-[11px] font-bold text-ok">{t.tag}</span>
                  <span className="font-semibold">{t.text}</span>
                  <span className="block text-[11px] text-ink/60">{t.hint}</span>
                </li>
              );
            })}
            {result.together.length === 0 && <li className="text-sm text-ink/60">겹치는 준비가 아직 없어요. 다른 상대를 골라 보세요.</li>}
          </ul>
          <div className="mt-3 border-t border-line pt-2">
            <p className="text-[11px] text-ink/70">둘이 합쳐 노드 <b className="text-ink">{result.team.done}</b>/{result.team.total} 완료</p>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-line">
              <div className="duel-bar h-full rounded-full bg-gradient-to-r from-go via-ok to-gold" style={{ width: `${pct(result.team)}%` }} />
            </div>
          </div>
        </div>
      </div>
      <p className="px-4 pb-3 text-[11px] text-ink/50">시연 계정은 가상의 학생이에요. 링크에는 닉네임과 트리 진행 상황만 담기고 서버에 저장되지 않아요.</p>
    </section>
  );
}
