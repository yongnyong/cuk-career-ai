"use client";
import { useState } from "react";
import { Check, Lock, Play } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { HallOfFame } from "@/components/HallOfFame";
import { EvolutionOverlay, HayangFigure, TitleBadge, useTitles } from "@/components/Hayang";
import { useStore } from "@/lib/store";
import { careerInterestOf } from "@/lib/interest";
import { hayangImage, HOME_PROOFS, jobsWearing, OUTFIT_LABEL, OUTFITS, outfitFor, STAGE_FROM, stageTitle, type HayangStage } from "@/lib/hayang";
import { RARITY_LABEL, type Rarity } from "@/lib/titles";

const STAGES: HayangStage[] = [1, 2, 3, 4, 5];
const STAGE_NAME = { 1: "과잠 새내기", 2: "취업", 3: "명품백", 4: "자동차", 5: "내 집 마련" } as const;
const RARITIES: Rarity[] = ["legend", "epic", "rare", "common"];

function HayangBook() {
  const s = useStore();
  const p = s.profile!;
  const outfit = outfitFor(p.jobId, careerInterestOf(p) === "startup");
  const { titles, equipped, evolution: evo } = useTitles();
  const stage = evo.stage;
  const [replay, setReplay] = useState(false);
  const replayFrom = Math.max(1, stage - 1) as HayangStage;
  const replayTo = Math.max(2, stage) as HayangStage;

  return (
    <div className="space-y-6">
      <section className="window flex flex-wrap items-center gap-8 p-6">
        <HayangFigure stage={stage} outfit={outfit} size="lg" />
        <div className="min-w-60 flex-1 space-y-2">
          <p className="text-sm text-ink/65">하양이 도감 · 노드 {evo.done}/{evo.total} 완료({evo.pct}%)</p>
          <h1 className="text-2xl font-bold">{stageTitle(stage, outfit)}</h1>
          {equipped && <p className="flex items-center gap-2 text-sm">장착한 칭호 <TitleBadge title={equipped} /></p>}
          <p className="text-sm text-ink/70">
            {stage === 5 ? "최종 진화까지 마쳤어요!"
              : stage === 4 ? `내 집 마련은 노드 ${STAGE_FROM[4]}% 완료에 증빙 인증 ${HOME_PROOFS}개가 있어야 해요. 남은 것: 노드 ${evo.toNext}개, 인증 ${evo.proofsNeeded}개. 스킬트리 노드에 결과물이나 자격증을 첨부하면 인증돼요.`
              : `노드 ${evo.toNext}개만 더 완료하면 ‘${STAGE_NAME[(stage + 1) as HayangStage]}’ 단계로 진화해요.`}
          </p>
          <button className="btn-primary" onClick={() => setReplay(true)}><Play size={14} /> 진화 모션 보기</button>
        </div>
      </section>

      <section className="card p-5">
        <h2 className="font-bold">진화 단계 <span className="text-sm font-normal text-ink/60">{OUTFIT_LABEL[outfit]} 하양이</span></h2>
        <ol className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
          {STAGES.map((st) => {
            const open = st <= stage;
            return (
              <li key={st} className={`flex flex-col items-center gap-2 rounded-lg border p-4 ${st === stage ? "border-go bg-go/10" : "border-line"}`}>
                <div className={open ? "" : "opacity-40 brightness-0 invert-[.35]"}><HayangFigure stage={st} outfit={outfit} size="sm" /></div>
                <p className="text-center text-sm font-bold">{st}. {STAGE_NAME[st]}</p>
                <p className="flex items-center gap-1 text-xs text-ink/60">
                  {open ? <><Check size={12} className="text-ok" /> {st === stage ? "지금 단계" : "달성"}</> : <><Lock size={12} /> 노드 {STAGE_FROM[st - 1]}% 완료{st === 5 && ` + 인증 ${HOME_PROOFS}개`}</>}
                </p>
              </li>
            );
          })}
        </ol>
      </section>

      <HallOfFame profile={p} onMentor={(id) => s.setProfile({ ...p, mentorId: id })} />

      <section className="card p-5">
        <h2 className="font-bold">칭호 <span className="text-sm font-normal text-ink/60">{titles.filter((t) => t.earned).length} / {titles.length} 획득 · 얻은 칭호를 눌러 장착</span></h2>
        {RARITIES.map((rarity) => (
          <div key={rarity} className="mt-4">
            <h3 className="text-xs font-bold text-ink/60">{RARITY_LABEL[rarity]}</h3>
            <ul className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {titles.filter((t) => t.rarity === rarity).map((t) => {
                const on = equipped?.id === t.id;
                return (
                  <li key={t.id}>
                    <button
                      disabled={!t.earned}
                      onClick={() => s.setProfile({ ...p, title: t.id })}
                      className={`flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm ${on ? "border-gold bg-gold/10" : "border-line"} ${t.earned ? "hover:border-go" : "cursor-not-allowed opacity-50"}`}
                    >
                      <span className="space-y-1">
                        {t.earned ? <TitleBadge title={t} /> : <span className="flex items-center gap-1 font-bold"><Lock size={12} /> {t.name}</span>}
                        <span className="block text-xs text-ink/60">{t.how}{t.progress && ` · ${t.progress}`}</span>
                      </span>
                      {on && <span className="shrink-0 text-xs font-bold text-gold">장착 중</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </section>

      <section className="card p-5">
        <h2 className="font-bold">착장 도감 <span className="text-sm font-normal text-ink/60">목표 직무에 따라 2단계부터 입어요</span></h2>
        <ul className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-7">
          <li className={`flex flex-col items-center gap-1 rounded-lg border p-3 text-center ${stage === 1 ? "border-go bg-go/10" : "border-line"}`}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={hayangImage(1, outfit)} alt="" className="h-32 object-contain" />
            <p className="text-sm font-bold">새내기</p>
            <p className="text-[11px] text-ink/60">모두 과잠으로 시작</p>
          </li>
          {OUTFITS.map((o) => (
            <li key={o} className={`flex flex-col items-center gap-1 rounded-lg border p-3 text-center ${o === outfit ? "border-gold bg-gold/10" : "border-line"}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={hayangImage(2, o)} alt="" className="h-32 object-contain" />
              <p className="text-sm font-bold">{OUTFIT_LABEL[o]}{o === outfit && <span className="ml-1 text-[11px] text-gold">내 착장</span>}</p>
              <p className="text-[11px] leading-tight text-ink/60">{jobsWearing(o).join(", ")}</p>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[11px] text-ink/50">하양이는 가톨릭대학교 캐릭터예요. 직업 착장은 학교 허락을 받아 만든 2차 창작이에요.</p>
      </section>

      {replay && <EvolutionOverlay from={replayFrom} to={replayTo} outfit={outfit} newTitle={titles.find((t) => t.id === ({ 2: "job", 3: "car", 4: "home" } as const)[replayTo as 2 | 3 | 4])} onClose={() => setReplay(false)} />}
    </div>
  );
}

export default function HayangPage() {
  return (
    <RequireProfile>
      <HayangBook />
    </RequireProfile>
  );
}
