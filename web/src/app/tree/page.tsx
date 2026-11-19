"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Award, Check, KeyRound, Printer, Swords, X } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { OppCard } from "@/components/OppCard";
import { ProofField } from "@/components/ProofField";
import { listProofs, type ProofMeta } from "@/lib/files";
import { Legend, NodeBox, StatusWindow } from "@/components/quest-ui";
import { AiNotice, DDay, TypeTag, VirtualTag } from "@/components/ui";
import { useStore } from "@/lib/store";
import { dday, recommend, type TreeNode } from "@/lib/engine";
import type { RecommendedQuest, TreeSignal } from "@/lib/types";
import { formatScore, meetsTarget, scaleOf, skillById } from "@/lib/data/catalog";
import { questProgress } from "@/lib/quest";

type SkillNodeData = { node: TreeNode; isNew: boolean; now: Date; proof: boolean; recommended: boolean };

function SkillNode({ data }: NodeProps<Node<SkillNodeData>>) {
  return (
    <>
      <Handle type="target" position={Position.Top} className="!border-0 !bg-edge" />
      <NodeBox node={data.node} isNew={data.isNew} now={data.now} proof={data.proof} recommended={data.recommended} />
      <Handle type="source" position={Position.Bottom} className="!border-0 !bg-edge" />
    </>
  );
}
const nodeTypes = { skill: SkillNode };

const ACTION_TEXT: Record<string, string> = {
  review_record: "보유 기록과 시험·자격의 인정 조건을 비교해 보세요.",
  review_source: "원문에서 인정되는 선택지와 유효기간을 확인해 보세요.",
  practice_gap: "부족한 영역의 연습 문제를 풀고 틀린 유형을 기록해 보세요.",
  diagnose: "예제나 모의 문항으로 현재 준비 수준을 점검해 보세요.",
  first_exercise: "입문 예제를 하나 골라 직접 끝까지 해 보세요.",
  outline: "작은 실습이나 프로젝트 주제를 하나 정하고 첫 결과물의 범위를 적어 보세요.",
  review_scope: "공식 안내에서 시험 범위와 응시 조건을 확인해 보세요.",
  review_activity: "활동 원문에서 모집 대상과 진행 내용을 확인해 보세요.",
};
const BASIS_LABEL = { required: "공고 필수", preferred: "공고 우대", school: "학과 진로표", activity: "학습 활동" };

function EvidenceLinks({ signals }: { signals: TreeSignal[] }) {
  const [first, next] = signals;
  if (!first) return null;
  const firstEmployer = first.reference.organization?.trim();
  const otherEmployer = firstEmployer && signals.find(({ reference }) =>
    reference.organization?.trim() && reference.organization.trim() !== firstEmployer);
  const second = otherEmployer || next;
  return (second ? [first, second] : [first]).map(({ reference, basis }) => (
    <div key={reference.id} className="space-y-0.5">
      {reference.quote ? (
        <>
          <p className="font-semibold">{BASIS_LABEL[basis]} 원문</p>
          <blockquote className="text-ink/75">“{reference.quote}”</blockquote>
        </>
      ) : reference.summary ? (
        <>
          <p className="font-semibold">{BASIS_LABEL[basis]} · 검수 요약</p>
          <p className="text-ink/75">{reference.summary}</p>
        </>
      ) : null}
      <a href={reference.url} target="_blank" rel="noreferrer" className="block break-words underline">
        {reference.historical && "지난 공고 · "}
        {reference.sourceKind === "platform_repost" && "재게시 · "}
        {reference.organization && !reference.title.includes(reference.organization) && `${reference.organization} · `}
        {reference.title}
        {reference.sectionId && ` ${reference.sectionId}`}
      </a>
    </div>
  ));
}

function PreparationDetail({ node, signals, quest }: {
  node: TreeNode; signals: TreeSignal[]; quest?: RecommendedQuest;
}) {
  const source = signals[0];
  const plan = source?.preparation;
  if (!plan) return null;
  const related = signals.filter((signal) => signal.preparation?.kind === plan.kind && signal.preparation.action === plan.action);
  const employers = new Set(related.map((signal) => signal.reference.organization?.trim()).filter(Boolean));
  const laterGoal = quest?.reasonCode === "prerequisite" ? skillById(quest.targetSkill!)?.name ?? "후속 역량" : undefined;
  return (
    <div className="mt-2 space-y-1 border-l-2 border-go pl-2 text-xs">
      <p className="font-bold text-go">{quest ? "추천 퀘스트" : "공고 기반 준비 방법"}</p>
      {laterGoal && <p>지금은 ‘{node.name}’부터 시작해요. ‘{laterGoal}’을 준비하는 데 필요한 선수 단계예요.</p>}
      <EvidenceLinks signals={related} />
      <p>{plan.kind === "direct"
        ? "공고에 명시된 항목을 준비하는 과제예요."
        : `공고에 나온 역량을 준비하는 방법으로 ‘${laterGoal ?? node.name}’을 추천해요.`}</p>
      {employers.size > 1 && <p className="text-ink/70">이 준비 방법과 연결된 기업 {employers.size}곳</p>}
      <dl className="space-y-1 pt-1">
        <div>
          <dt className="font-semibold">{laterGoal ? `‘${laterGoal}’ 단계에서 할 일` : "서비스가 제안하는 행동"}</dt>
          <dd>{plan.action}</dd>
        </div>
        <div>
          <dt className="font-semibold">{laterGoal ? "후속 단계 완료 기준" : "완료 기준"}</dt>
          <dd>{plan.completion}</dd>
        </div>
      </dl>
    </div>
  );
}

function QuestDetail({ node, quest, loadAction, showAction }: {
  node: TreeNode; quest: RecommendedQuest; loadAction: (() => Promise<string | undefined>) | null; showAction: boolean;
}) {
  const source = quest.signals[0];
  const prerequisite = quest.reasonCode === "prerequisite";
  const targetName = prerequisite ? skillById(quest.targetSkill!)?.name ?? "후속 역량" : node.name;
  const [result, setResult] = useState<{ request: typeof loadAction; actionId?: string }>();
  useEffect(() => {
    if (!showAction || !loadAction) return;
    let current = true;
    void loadAction().then((actionId) => {
      if (current) setResult({ request: loadAction, actionId });
    });
    return () => { current = false; };
  }, [loadAction, showAction]);
  const reason = prerequisite
    ? `지금은 ‘${node.name}’부터 시작해요. 다음 목표는 ‘${targetName}’예요.`
    : quest.reasonCode === "score_target"
      ? `현재 기록이 학과 권장 기준(${formatScore(node.skill, node.target)})에 아직 못 미쳐요.`
      : source?.minimum && quest.actionKind === "improve"
        ? `현재 기록이 자료의 기준(${formatScore(node.skill, source.minimum)})에 아직 못 미쳐요.`
        : source?.reference.scope === "posting" ? "여러 모집 부문의 공고에 나온 역량이에요. 목표 직무에 적용되는지 원문에서 확인해 보세요."
          : source ? `${BASIS_LABEL[source.basis]} 자료에 이 역량이 나와요.` : "선택한 직무의 기본 준비 단계예요.";
  const fallback = quest.actionKind === "verify" ? source?.basis === "activity" ? "review_activity" : "review_record"
    : quest.actionKind === "improve" ? "practice_gap"
    : node.kind === "어학" || node.kind === "자격증" ? "review_scope" : "first_exercise";
  const actionId = result?.request === loadAction ? result?.actionId : undefined;
  return (
    <div className="mt-2 space-y-1 border-l-2 border-go pl-2 text-xs">
      <p className="font-bold text-go">추천 퀘스트</p>
      <p>{reason}</p>
      <EvidenceLinks signals={quest.signals} />
      {showAction && <p>{(actionId && Object.hasOwn(ACTION_TEXT, actionId) ? ACTION_TEXT[actionId] : undefined) ?? ACTION_TEXT[fallback]}</p>}
    </div>
  );
}

// 점수제(TOEIC 등)·등급제(OPIc, JLPT 등) 자격: 점수나 등급을 적으면 완료로 표시한다
function ScoreField({ skill, value, target, onSave }: { skill: string; value?: string; target?: string; onSave: (v: string) => void }) {
  const sc = scaleOf(skill)!;
  const [v, setV] = useState(value ?? "");
  const valid = "grades" in sc ? true : v === "" || (Number(v) >= sc.min && Number(v) <= sc.max);
  const ok = meetsTarget(skill, value, target);
  return (
    <div className="mt-3 space-y-1 text-xs">
      <label className="block font-bold text-slate-600" htmlFor="score-input">
        {"grades" in sc ? "내 등급" : `내 점수 (${sc.min}~${sc.max}${sc.unit})`}
      </label>
      <div className="flex gap-1.5">
        {"grades" in sc ? (
          <select id="score-input" className="input !py-1" value={v} onChange={(e) => setV(e.target.value)}>
            <option value="">아직 없음</option>
            {sc.grades.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        ) : (
          <input id="score-input" className="input !py-1" inputMode="numeric" value={v} onChange={(e) => setV(e.target.value.replace(/\D/g, ""))} />
        )}
        <button className="btn-primary !py-1 text-xs" disabled={!valid} onClick={() => onSave(v)}>
          저장
        </button>
      </div>
      {!valid && <p className="text-danger">범위 안의 점수를 입력해 주세요.</p>}
      {target && (
        <p className={ok === false ? "text-warn" : "text-slate-500"}>
          학과 권장: {formatScore(skill, target)} 이상
          {ok === true && " · 충족"}
          {ok === false && " · 아직 못 미쳐요"}
        </p>
      )}
    </div>
  );
}

function TreeView() {
  const s = useStore();
  const p = s.profile!;
  const now = s.nowDate;
  const { tree, recommendedQuest, treeProgress } = s.careerPath!;
  const readyCount = tree.filter((node) => node.state === "none" && !node.locked).length;
  const recs = useMemo(() => recommend(s.opportunities, p, now), [s.opportunities, p, now]);
  const [sel, setSel] = useState<string | null>(null);
  const selNode = tree.find((n) => n.skill === sel);
  const selectedQuest = recommendedQuest?.skillId === sel ? recommendedQuest : null;
  const routedQuest = selectedQuest?.signals[0]?.preparation ? selectedQuest : undefined;
  const selectedRoutes = routedQuest?.signals ?? selNode?.preparationSignals;
  const newSet = useMemo(() => new Set(s.newOpps), [s.newOpps]);
  const questSkill = recommendedQuest?.skillId;
  // 증빙 파일 목록(이 브라우저에만 저장)
  const [proofs, setProofs] = useState<Record<string, ProofMeta>>({});
  const loadProofs = useCallback(() => {
    listProofs(p.pseudoId).then(setProofs).catch(() => setProofs({}));
  }, [p.pseudoId]);
  useEffect(loadProofs, [loadProofs]);
  const cancel = (skill: string) => (s.setScore(skill, ""), s.setSkill(skill, "none"));

  const { nodes, edges } = useMemo(() => {
    const counts: number[] = [];
    for (const n of tree) counts[n.depth] = (counts[n.depth] ?? 0) + 1;
    const columns = 4;
    const offsets: number[] = [0];
    for (let depth = 0; depth < counts.length; depth++) {
      offsets.push(offsets[depth] + Math.ceil(counts[depth] / columns));
    }
    const seen: number[] = [];
    const nodes: Node<SkillNodeData>[] = tree.map((n) => {
      const index = seen[n.depth] ?? 0;
      seen[n.depth] = index + 1;
      const row = Math.floor(index / columns);
      const width = Math.min(columns, counts[n.depth] - row * columns);
      return {
        id: n.skill,
        type: "skill",
        position: { x: (index % columns - (width - 1) / 2) * 207, y: (offsets[n.depth] + row) * 128 + 50 },
        data: { node: n, isNew: n.opportunities.some((o) => newSet.has(o.id)), now, proof: !!proofs[n.skill], recommended: n.skill === questSkill },
      };
    });
    const edges: Edge[] = tree.flatMap((n) =>
      n.prereq.map((q) => ({ id: `${q}-${n.skill}`, source: q, target: n.skill, animated: n.state === "none" && !n.locked, style: { stroke: n.locked ? "#4a5078" : "#7c6cff", strokeWidth: 2 } })),
    );
    return { nodes, edges };
  }, [tree, newSet, now, proofs, questSkill]);

  const newOpp = s.opportunities.find((o) => newSet.has(o.id) && tree.some((n) => n.opportunities.includes(o)));
  const activeQuest = s.followed
    .map((id) => s.opportunities.find((o) => o.id === id)!)
    .filter((o) => o && dday(o, now) >= 0)
    .sort((a, b) => dday(a, now) - dday(b, now))[0];
  const qp = activeQuest ? questProgress(activeQuest, s.quests[activeQuest.id]) : null;

  return (
    <div className="space-y-4">
      <StatusWindow profile={p} treeProgress={treeProgress}>
        {newOpp && (
          <Link
            href={`/opportunities/${newOpp.id}`}
            onClick={() => s.clearNew()}
            className="unlock chip border-2 border-edge bg-gold px-3 py-1.5 text-on-gold"
          >
            <KeyRound size={12} /> 새 기회 열림 · {newOpp.title} · D-{dday(newOpp, now)}
          </Link>
        )}
      </StatusWindow>

      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="relative flex h-[620px] min-w-0 flex-col overflow-hidden rounded-lg border-2 border-edge bg-panel">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
            <Legend />
            <span className="text-xs text-ink/60">전체 {tree.length}개 · 지금 도전 {readyCount}개</span>
          </div>
          <div className="min-h-0 flex-1">
            <ReactFlow
              key={nodes.map((node) => node.id).sort().join("|")}
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              minZoom={0.2}
              fitViewOptions={{ padding: 0.12, maxZoom: 1.1 }}
              onNodeClick={(_, n) => setSel(n.id)}
              nodesDraggable={false}
              colorMode="dark"
            >
              <Background gap={24} color="#2a2f52" />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>

          {selNode && (
            <div className="window absolute right-3 top-14 z-10 max-h-[calc(100%_-_4.5rem)] w-72 overflow-y-auto p-4">
              <button className="absolute right-2 top-2 text-slate-400" onClick={() => setSel(null)} aria-label="닫기">
                <X size={16} />
              </button>
              <p className="text-xs text-slate-500">{selNode.kind}</p>
              <h3 className="font-bold">{selNode.name}</h3>
              {selectedQuest && !routedQuest && (
                <QuestDetail key={selNode.skill} node={selNode} quest={selectedQuest} loadAction={s.getQuestAction} showAction={!selectedRoutes?.length && !selNode.practice} />
              )}
              {!!selectedRoutes?.length && <PreparationDetail node={selNode} signals={selectedRoutes} quest={routedQuest} />}
              {!selectedQuest && !selectedRoutes?.length && !!selNode.evidence?.length && (
                <div className="mt-2 space-y-1 text-xs"><EvidenceLinks signals={selNode.evidence} /></div>
              )}
              {selNode.practice && (
                <div className="mt-2 space-y-1 border-l-2 border-line pl-2 text-xs">
                  <p className="font-bold">직무 연습 제안{selNode.prereq.length > 0 && ` · ${skillById(selNode.prereq[0])?.name}`}</p>
                  <p>{selNode.practice.action}</p>
                  <p><strong>완료 기준</strong> {selNode.practice.completion}</p>
                </div>
              )}
              {skillById(selNode.skill)?.officialUrl && (
                <a href={skillById(selNode.skill)!.officialUrl} target="_blank" rel="noreferrer" className="text-xs underline">
                  공식 안내 확인
                </a>
              )}
              {skillById(selNode.skill)?.srcUrl && (
                <a href={skillById(selNode.skill)!.srcUrl} target="_blank" rel="noreferrer" className="block text-xs underline">
                  출처: {skillById(selNode.skill)!.from === "커리어넷" ? "커리어넷 학과정보" : "학과 홈페이지 안내"}
                </a>
              )}
              {scaleOf(selNode.skill) && (
                <ScoreField
                  key={selNode.skill}
                  skill={selNode.skill}
                  value={selNode.score}
                  target={selNode.target}
                  onSave={(v) => s.setScore(selNode.skill, v)}
                />
              )}
              {selNode.state === "none" ? (
                !scaleOf(selNode.skill) && (
                  <button className="btn-gold mt-3 w-full" onClick={() => s.setSkill(selNode.skill, "self")}>
                    <Check size={16} /> 완료로 표시
                  </button>
                )
              ) : (
                <>
                  <p className="mt-3 flex items-center gap-1 rounded-md bg-emerald-100 px-2 py-1.5 text-sm font-bold text-emerald-700">
                    <Check size={16} /> 완료한 노드예요
                  </p>
                  <ProofField owner={p.pseudoId} skill={selNode.skill} proof={proofs[selNode.skill]} onChange={loadProofs} />
                  <button className="btn-ghost mt-2 !py-1 text-xs" onClick={() => cancel(selNode.skill)}>
                    완료 취소
                  </button>
                </>
              )}
              <p className="mt-1 text-[11px] text-slate-400">완료 표시는 자기 보고이며 검증된 자격과 구분돼요.</p>
              <h4 className="mt-3 text-xs font-bold text-slate-600">이 노드에서 열린 기회</h4>
              <ul className="mt-1 space-y-1">
                {selNode.opportunities.length === 0 && <li className="text-xs text-slate-400">지금 열린 기회가 없어요</li>}
                {selNode.opportunities.map((o) => (
                  <li key={o.id}>
                    <Link href={`/opportunities/${o.id}`} className="flex items-center gap-1 text-xs hover:underline">
                      <TypeTag type={o.type} /> {o.title} <DDay opp={o} now={now} />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <section className="card p-4 lg:col-start-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-bold">
              노드 체크리스트 <span className="text-sm font-normal text-ink/60">완료 {tree.filter((n) => n.state !== "none").length} / {tree.length}</span>
            </h2>
            <Link href="/print" className="btn-ghost !py-1 text-xs">
              <Printer size={12} /> 완료 내역·증빙 인쇄
            </Link>
          </div>
          <ul className="mt-2 divide-y divide-line">
            {tree.map((n) => {
              const done = n.state !== "none";
              return (
                <li key={n.skill} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                  <span className={`grid size-6 shrink-0 place-items-center rounded ${done ? "bg-ok text-white" : "border border-line"}`}>
                    {done && <Check size={14} />}
                  </span>
                  <button className="min-w-0 flex-1 text-left hover:underline" onClick={() => setSel(n.skill)}>
                    <span className="font-semibold">{n.name}</span>
                    <span className="ml-1.5 text-xs text-ink/60">
                      {n.kind}
                      {n.required && " · 트랙 기본"}
                      {n.score && ` · ${formatScore(n.skill, n.score)}`}
                      {proofs[n.skill] && " · 증빙 첨부"}
                      {!done && n.locked && " · 앞 단계를 먼저 권장"}
                    </span>
                  </button>
                  {done ? (
                    <button className="btn-ghost !py-1 text-xs" onClick={() => cancel(n.skill)}>
                      완료 취소
                    </button>
                  ) : scaleOf(n.skill) ? (
                    <button className="btn-primary !py-1 text-xs" onClick={() => setSel(n.skill)}>
                      점수·등급 입력
                    </button>
                  ) : (
                    <button className="btn-primary !py-1 text-xs" onClick={() => s.setSkill(n.skill, "self")}>
                      <Check size={14} /> 완료로 표시
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
          <p className="mt-2 text-xs text-ink/60">완료한 노드를 누르면 자격증·수료증 파일을 붙일 수 있어요.</p>
        </section>

        <aside className="space-y-4 lg:col-start-2 lg:row-span-2 lg:row-start-1">
          <div className="card p-4">
            <h2 className="flex items-center gap-1.5 font-bold">
              <Swords size={16} className="text-go" /> 퀘스트
            </h2>
            {activeQuest && qp ? (
              <Link href={`/opportunities/${activeQuest.id}`} className="mt-2 block rounded-md bg-paper p-3 text-sm hover:brightness-95">
                <div className="flex items-center gap-1">
                  {activeQuest.isVirtual && <VirtualTag />} <DDay opp={activeQuest} now={now} />
                </div>
                <p className="mt-1 font-medium">{activeQuest.title} 지원 준비</p>
                <div className="mt-1 h-1.5 rounded-full bg-slate-200">
                  <div className="h-full rounded-full bg-ok" style={{ width: `${(qp.done / qp.total) * 100}%` }} />
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {qp.done}/{qp.total} 완료 · 다음: {qp.items.find((i) => !s.quests[activeQuest.id]?.[i]) ?? "모두 완료"}
                </p>
              </Link>
            ) : (
              <p className="mt-2 text-sm text-slate-500">아래 기회 카드에서 &lsquo;지원 퀘스트 시작&rsquo;을 누르면 여기에 나타나요.</p>
            )}
            {questSkill && (
              <p className="mt-3 text-sm">
                추천 퀘스트 · <button type="button" className="font-bold hover:underline" onClick={() => setSel(questSkill)}>{skillById(questSkill)?.name}</button>
              </p>
            )}
            <p className="mt-3 flex items-center gap-1 text-xs text-slate-500">
              <Award size={12} /> 배지는 확인된 행동만 기록해요 · 공개 순위 없음
            </p>
          </div>

          <div>
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="font-bold">이번 주 기회 카드</h2>
              <Link href="/opportunities" className="text-xs underline">
                전체 보기
              </Link>
            </div>
            <div className="space-y-2">
              {recs.slice(0, 3).map((r) => (
                <OppCard key={r.opp.id} r={r} now={now} isNew={newSet.has(r.opp.id)} />
              ))}
              {recs.length === 0 && <p className="text-sm text-slate-500">지금 조건에 맞는 열린 기회가 없어요.</p>}
            </div>
            <AiNotice className="mt-2" />
          </div>
        </aside>
      </div>
    </div>
  );
}

export default function TreePage() {
  return (
    <RequireProfile>
      <TreeView />
    </RequireProfile>
  );
}
