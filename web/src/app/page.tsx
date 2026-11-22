"use client";
import { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronRight, KeyRound, Swords } from "lucide-react";
import { useStore } from "@/lib/store";
import { useMounted } from "@/lib/useMounted";
import { buildCareerPath, dday, recommend } from "@/lib/engine";
import { DEPARTMENTS } from "@/lib/data/departments";
import { PERSONAS } from "@/lib/data/personas";
import { recommendedTitle } from "@/lib/questOutcome";
import { questProgress } from "@/lib/quest";
import { Legend, NodeBox, StatusWindow } from "@/components/quest-ui";
import { OppCard } from "@/components/OppCard";
import { AiNotice, DDay } from "@/components/ui";

const STEPS = [
  { title: "학과·학년·가진 것을 고른다", text: "이름과 학번은 묻지 않아요. 1분이면 끝나요." },
  { title: "목표 직무까지 스킬트리가 생긴다", text: "어학, 자격증, 프로젝트가 순서대로 이어져요." },
  { title: "공고가 올라오면 노드에서 기회가 열린다", text: "지원 자격은 충족, 미충족, 확인 필요로 나눠 알려줘요." },
];

function Landing() {
  const s = useStore();
  const router = useRouter();
  const demo = PERSONAS[0];
  const now = s.nowDate;
  const rows = useMemo(() => {
    const { tree } = buildCareerPath(demo.profile, s.opportunities, now, []);
    const byDepth: (typeof tree)[] = [];
    for (const n of tree) (byDepth[n.depth] ??= []).push(n);
    return byDepth;
  }, [demo, now, s.opportunities]);

  return (
    <div className="space-y-12">
      <section className="grid items-center gap-8 pt-4 lg:grid-cols-[5fr_6fr]">
        <div>
          <h1 className="font-display text-4xl leading-tight sm:text-5xl">
            공지는 올라왔는데
            <br />
            나만 몰랐다
          </h1>
          <p className="mt-4 max-w-md text-ink/75">
            가톨릭대학교 {DEPARTMENTS.length}개 학과 누구나, 목표 직무를 고르면 준비할 것들이 스킬트리로 이어져요. 현장실습과 창업지원 공고가
            올라오면 내 트리의 해당 노드에서 기회가 열려요.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href={s.session ? "/onboarding" : "/signup"} className="btn-gold">
              내 스킬트리 만들기
            </Link>
            <button className="btn-ghost" onClick={() => {
              s.loginDemo(demo.id, demo.profile);
              router.push("/tree");
            }}>
              {demo.label}의 트리로 둘러보기
            </button>
          </div>
        </div>

        <div className="window overflow-hidden">
          <div className="flex items-center justify-between border-b-2 border-edge bg-navy px-4 py-2 text-sm text-white">
            <span className="font-bold">{demo.label}의 스킬트리</span>
            <span className="text-white/70">{demo.desc}</span>
          </div>
          <div className="space-y-3 overflow-x-auto bg-paper p-4">
            {rows.map((row, i) => (
              <div key={i} className="flex flex-wrap justify-center gap-3">
                {row.map((n) => (
                  <NodeBox key={n.skill} node={n} now={now} />
                ))}
              </div>
            ))}
          </div>
          <div className="border-t-2 border-edge px-4 py-2">
            <Legend />
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-bold">이렇게 써요</h2>
        <ol className="mt-3 grid gap-x-8 gap-y-4 border-t-2 border-edge pt-4 sm:grid-cols-3">
          {STEPS.map((x, i) => (
            <li key={x.title}>
              <span className="font-display text-2xl text-ink/40">{i + 1}</span>
              <h3 className="font-bold">{x.title}</h3>
              <p className="mt-1 text-sm text-ink/70">{x.text}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function Today() {
  const s = useStore();
  const p = s.profile!;
  const now = s.nowDate;
  const recs = useMemo(() => recommend(s.opportunities, p, now), [s.opportunities, p, now]);
  const urgent = [...recs].sort((a, b) => dday(a.opp, now) - dday(b.opp, now)).slice(0, 3);
  const { recommendedQuest: next, treeProgress, tree } = s.careerPath!;
  const nextNode = next && tree.find(n => n.skill === next.skillId);
  const quests = s.followed
    .map((id) => s.opportunities.find((o) => o.id === id))
    .filter((o) => o !== undefined && dday(o, now) >= 0)
    .map((o) => o!)
    .sort((a, b) => dday(a, now) - dday(b, now));
  const fresh = s.opportunities.filter((o) => s.newOpps.includes(o.id));

  return (
    <div className="space-y-8">
      <StatusWindow profile={p} treeProgress={treeProgress}>
        <Link href="/tree" className="btn-primary">
          스킬트리 열기 <ChevronRight size={16} />
        </Link>
      </StatusWindow>

      {fresh.length > 0 && (
        <section className="unlock rounded-lg border-2 border-edge bg-gold text-on-gold p-4">
          <h2 className="flex items-center gap-1.5 font-bold">
            <KeyRound size={16} /> 새 기회가 열렸어요
          </h2>
          <ul className="mt-2 space-y-1">
            {fresh.map((o) => (
              <li key={o.id}>
                <Link href={`/opportunities/${o.id}`} onClick={() => s.clearNew()} className="flex items-center gap-2 text-sm font-semibold underline">
                  {o.title} <DDay opp={o} now={now} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        <section>
          <h2 className="border-b-2 border-edge pb-2 text-lg font-bold">오늘 할 일</h2>
          <ul className="divide-y divide-line">
            {next && nextNode && (
              <li>
                <Link href="/tree" className="flex items-center gap-3 py-3 hover:bg-panel">
                  <span className="grid size-9 shrink-0 place-items-center rounded bg-go text-white">
                    <Swords size={18} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs text-ink/60">추천 퀘스트</span>
                    <span className="block font-bold">{recommendedTitle(nextNode, next)}</span>
                  </span>
                  <ChevronRight size={18} className="text-ink/40" />
                </Link>
              </li>
            )}
            {quests.map((o) => {
              const qp = questProgress(o, s.quests[o.id]);
              return (
                <li key={o.id}>
                  <Link href={`/opportunities/${o.id}`} className="flex items-center gap-3 py-3 hover:bg-panel">
                    <span className="grid size-9 shrink-0 place-items-center rounded bg-gold text-on-gold">
                      <KeyRound size={18} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1.5 text-xs text-ink/60">
                        지원 퀘스트 {qp.done}/{qp.total} <DDay opp={o} now={now} />
                      </span>
                      <span className="block truncate font-bold">{o.title}</span>
                      <span className="exp mt-1 block !h-2">
                        <span className="block h-full bg-ok" style={{ width: `${(qp.done / qp.total) * 100}%` }} />
                      </span>
                    </span>
                    <ChevronRight size={18} className="text-ink/40" />
                  </Link>
                </li>
              );
            })}
            {!next && quests.length === 0 && (
              <li className="py-3 text-sm text-ink/60">
                {tree.length > 0 && tree.every((node) => node.state !== "none")
                  ? "트리의 모든 노드를 완료했어요."
                  : "지금 추천할 노드가 없어요."}
              </li>
            )}
          </ul>
          {quests.length === 0 && (
            <p className="mt-2 text-sm text-ink/60">기회 카드에서 &lsquo;지원 퀘스트 시작&rsquo;을 누르면 준비 목록이 여기에 생겨요.</p>
          )}
        </section>

        <section>
          <div className="flex items-baseline justify-between border-b-2 border-edge pb-2">
            <h2 className="text-lg font-bold">마감이 가까운 기회</h2>
            <Link href="/opportunities" className="text-sm font-semibold underline">
              전체 보기
            </Link>
          </div>
          <div className="mt-3 space-y-2">
            {urgent.map((r) => (
              <OppCard key={r.opp.id} r={r} now={now} isNew={s.newOpps.includes(r.opp.id)} />
            ))}
            {urgent.length === 0 && <p className="text-sm text-ink/60">지금 조건에 맞는 열린 기회가 없어요.</p>}
          </div>
          <AiNotice className="mt-2" />
        </section>
      </div>
    </div>
  );
}

export default function Home() {
  const s = useStore();
  const mounted = useMounted();
  return mounted && s.ready && s.profile ? <Today /> : <Landing />;
}
