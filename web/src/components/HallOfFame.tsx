"use client";
import { useState } from "react";
import { Check, Crown, ExternalLink, Star } from "lucide-react";
import { fameFor, fameTree, mentorScore, type FameEntry } from "@/lib/data/hallOfFame";
import { skillById } from "@/lib/data/catalog";
import { getDepartment } from "@/lib/data/departments";
import { toTreeNodes } from "@/lib/customTree";
import type { Profile } from "@/lib/types";

/** 명예의 전당: 공개 이력으로 정리한 선배·전문가의 길과 멘토 따라잡기 점수 */
export function HallOfFame({ profile, onMentor }: { profile: Profile; onMentor: (id: string | undefined) => void }) {
  const { mine, others } = fameFor(profile.departmentId);
  // 다른 학과 인물은 펼쳤을 때만 보인다. 멘토로 지정한 인물은 늘 보인다
  const [showOthers, setShowOthers] = useState(false);
  const shown = [...mine, ...others.filter((e) => showOthers || e.id === profile.mentorId)];
  const [openId, setOpenId] = useState(profile.mentorId ?? mine[0]?.id);
  const entry = shown.find((e) => e.id === openId) ?? shown[0];
  if (!entry) return null;
  const dept = getDepartment(profile.departmentId)?.name;
  const steps = toTreeNodes(fameTree(entry, profile.skills)).nodes;
  const byId = new Map(entry.nodes.map((n) => [n.id, n]));
  const score = mentorScore(entry, profile.skills);
  const isMentor = profile.mentorId === entry.id;

  return (
    <section className="card p-5">
      <h2 className="flex items-center gap-1.5 font-bold"><Crown size={16} className="text-gold" /> 명예의 전당 <span className="text-sm font-normal text-ink/60">따라 걷고 싶은 길을 멘토로 지정해 보세요</span></h2>
      <div className="mt-4 grid gap-4 lg:grid-cols-[260px_1fr]">
        <ul className="space-y-2">
          {shown.map((e: FameEntry) => {
            const s = mentorScore(e, profile.skills);
            return (
              <li key={e.id}>
                {e === others.find((o) => shown.includes(o)) && <p className="mb-2 mt-3 text-xs text-ink/60">다른 학과</p>}
                <button onClick={() => setOpenId(e.id)} className={`flex w-full items-center gap-3 rounded-md border p-3 text-left ${e.id === entry.id ? "border-go bg-go/10" : "border-line hover:border-go"}`}>
                  <span className="grid size-11 shrink-0 place-items-center rounded-full bg-gradient-to-br from-gold to-[#f08a5d] font-display text-lg text-on-gold">{e.name[0]}</span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-1 font-bold">{e.name}
                      {profile.mentorId === e.id && <span className="text-[10px] text-gold">내 멘토</span>}
                    </span>
                    <span className="block truncate text-xs text-ink/60">{e.role}</span>
                    <span className="mt-0.5 flex flex-wrap gap-1 text-[10px]">
                      <span className="rounded border border-line px-1">{e.field}</span>
                      {e.departments.includes(profile.departmentId) && <span className="rounded bg-go/20 px-1 text-go">{dept} 추천</span>}
                    </span>
                  </span>
                  {s.linked > 0 && <span className="text-right text-xs"><b className="block text-base text-gold">{s.score}</b>점</span>}
                </button>
              </li>
            );
          })}
          {others.length > 0 && (
            <li>
              <button className="btn-ghost w-full !py-1 text-xs" onClick={() => setShowOthers((v) => !v)}>
                {showOthers ? "내 학과 인물만 보기" : `다른 학과 인물도 보기 (${others.length})`}
              </button>
            </li>
          )}
        </ul>

        <div className="space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h3 className="text-lg font-bold">{entry.name} <span className="text-sm font-normal text-ink/60">{entry.role}</span></h3>
              <p className="mt-1 text-sm text-ink/80">{entry.summary}</p>
            </div>
            <button className={isMentor ? "btn-ghost" : "btn-gold"} onClick={() => onMentor(isMentor ? undefined : entry.id)}>
              {isMentor ? "멘토 해제" : "멘토로 지정"}
            </button>
          </div>
          {score.linked > 0 && <div className="rounded-md bg-paper p-3">
            <p className="text-sm">{entry.name}까지 <b className="text-gold">{score.score}점</b> <span className="text-xs text-ink/60">· 내 트리와 이어지는 단계 {score.done}/{score.linked} 완료 · 중요도(★)와 인증 여부 반영</span></p>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-line"><div className="h-full bg-gradient-to-r from-go to-gold" style={{ width: `${score.score}%` }} /></div>
          </div>}
          <ol className="relative space-y-2 border-l-2 border-line pl-4">
            {steps.map((step) => {
              const n = byId.get(step.skill)!;
              const mine = n.skill ? skillById(n.skill)?.name : undefined;
              return (
                <li key={n.id} className="relative">
                  <span className={`absolute -left-[23px] top-1.5 grid size-3.5 place-items-center rounded-full ${step.state !== "none" ? "bg-ok" : "border-2 border-line bg-panel"}`} />
                  <p className="flex flex-wrap items-center gap-1.5 text-sm font-bold">
                    {n.name}
                    <span className="flex">{[1, 2, 3].map((w) => <Star key={w} size={11} className={w <= n.weight ? "text-gold" : "text-ink/25"} fill={w <= n.weight ? "currentColor" : "none"} />)}</span>
                    <span className="text-[10px] font-normal text-ink/60">{n.kind}</span>
                  </p>
                  <p className="text-xs text-ink/75">{n.detail}</p>
                  {mine && (
                    <p className={`mt-0.5 flex items-center gap-1 text-[11px] ${step.state !== "none" ? "text-ok" : "text-go"}`}>
                      {step.state !== "none" ? <Check size={11} /> : "→"} 내 트리에서는 ‘{mine}’{step.state !== "none" ? " 완료" : "부터 시작"}
                    </p>
                  )}
                </li>
              );
            })}
          </ol>
          <p className="text-[11px] text-ink/50">
            공개된 이력을 바탕으로 정리한 예시 트리이며 본인이 작성하거나 검토한 것이 아니에요. 출처: <a href={entry.source.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline">{entry.source.label} <ExternalLink size={10} /></a>
            {entry.more?.map((m) => (
              <span key={m.url}> · <a href={m.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline">{m.label} <ExternalLink size={10} /></a></span>
            ))}
          </p>
        </div>
      </div>
    </section>
  );
}
