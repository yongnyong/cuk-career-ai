"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps, type ReactFlowInstance } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Award, Check, KeyRound, Printer, Swords, X } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { OppCard } from "@/components/OppCard";
import { ProofField } from "@/components/ProofField";
import { listProofs, type ProofMeta } from "@/lib/files";
import { Legend, NodeBox, StatusWindow } from "@/components/quest-ui";
import { AiNotice, DDay, TypeTag, VirtualTag } from "@/components/ui";
import { useStore } from "@/lib/store";
import { countsTowardTrack, dday, recommend, type TreeNode } from "@/lib/engine";
import type { RecommendedQuest, TreeSignal, TreeDomain } from "@/lib/types";
import { formatScore, jobById, meetsTarget, scaleOf, skillById } from "@/lib/data/catalog";
import { AskNodeButton, useAssistantNode } from "@/components/Assistant";
import { questProgress } from "@/lib/quest";
import { questOutcome, recommendedTitle } from "@/lib/questOutcome";
import { careerInterestOf } from "@/lib/interest";
import { routeFor, layoutProgression, progressionStage } from "@/lib/treeProgression";

import { layoutKey, layoutTree, type TreeLayout } from "@/lib/treeLayout";

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
type StageData = { title: string; detail: string; width: number; count: number };
function StageNode({ data }: NodeProps<Node<StageData>>) {
  return <div style={{ width: data.width }} className="border-b border-go/40 bg-panel pb-3 text-ink">
    <p className="text-base font-bold">{data.title} <span className="text-xs font-normal text-ink/60">{data.count}개</span></p>
    <p className="mt-1 text-xs text-ink/65">{data.detail}</p>
  </div>;
}
const nodeTypes = { skill: SkillNode, stage: StageNode };

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

function StartupDetail({ node, recommended }: { node: TreeNode; recommended: boolean }) {
  const definition = node.startup!;
  const labels: Record<string, string> = { required: '필수 제출', optional: '선택 제출', conditional: '조건부 제출', needs_review: '확인 필요' };
  const stages: Record<string, string> = { application: '신청 단계', finalist: '본선·발표평가 단계', agreement: '선정·협약 단계' };
  const refs = [...new Map(definition.references.map((r) => [`${r.posting_id}:${r.basis}:${r.necessity}:${r.stage}`, r])).values()];
  const openIds = new Set(node.opportunities.map((o) => o.startup?.postingId));
  refs.sort((a, b) => Number(openIds.has(b.posting_id)) - Number(openIds.has(a.posting_id)));
  return <div className="mt-3 space-y-3 text-xs">
    <p className="font-bold text-go">{recommended ? '추천 퀘스트' : '창업 준비 과제'}</p>
    <p className="text-ink/60">양식 구성과 심사 대비에 활용하는 연결이에요. 공고마다 적용 조건을 확인해 주세요.</p>
    {refs.map((r) => <div key={r.id} className="space-y-1 border-t border-line pt-2">
      <p className="font-semibold">{r.basis === 'submission' ? labels[r.necessity] : r.basis === 'form_section' ? '신청 양식 항목' : '심사 대비 과제'}
        {stages[r.stage] && ` · ${stages[r.stage]}`}</p>
      {r.deadline_date && <p>자료 제출 기한 {r.deadline_date}</p>}
      {r.condition_text && <p>{r.condition_text}</p>}
      <blockquote className="whitespace-pre-line text-ink/75">{r.quote}</blockquote>
      <a href={r.source_url} target="_blank" rel="noreferrer" className="block underline">{node.evidence?.find((e) => e.reference.id === r.posting_id)?.reference.historical && '지난 공고 · '}{r.posting_title}{r.source_page && ` · 첨부 ${r.source_page}쪽`}</a>
      <Link href={`/opportunities/startup-${r.posting_id}`} className="block text-go underline">공고 상세와 제출물 보기</Link>
    </div>)}
  </div>;
}

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
        {laterGoal && <div><dt className="font-semibold">후속 단계 완료 기준</dt><dd>{plan.completion}</dd></div>}
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
  const { tree: allTree, recommendedQuest, treeProgress } = s.careerPath!;
  const mode = careerInterestOf(p);
  const [domain, setDomain] = useState<TreeDomain>("specialist");
  const tree = useMemo(() => mode === "startup" ? allTree : allTree.filter(n => routeFor(n).domain === domain), [allTree, mode, domain]);
  const openNode = (id: string) => {
    const node = allTree.find(n => n.skill === id);
    if (node && mode === "employment") setDomain(routeFor(node).domain);
    setSel(id);
    requestAnimationFrame(() => requestAnimationFrame(() => { void flow.current?.fitView({ nodes: [{ id }], maxZoom: 1, duration: 300, padding: 0.5 }); }));
  };
  const readyCount = tree.filter((node) => node.state === "none" && !node.locked).length;
  const recs = useMemo(() => recommend(s.opportunities, p, now), [s.opportunities, p, now]);
  const [sel, setSel] = useState<string | null>(null);
  const selNode = allTree.find((n) => n.skill === sel);
  const outcome = selNode && questOutcome(selNode);
  // 비서 카탈로그에는 직무 기본 노드만 있다. 공고·활동에서 더해진 노드는 이름만 넘긴다
  const askNode = selNode ? { name: selNode.name, ...(jobById(p.jobId)?.nodes.some((n) => n.skill === selNode.skill) ? { skillId: selNode.skill } : {}) } : null;
  useAssistantNode(askNode);
  const selectedQuest = recommendedQuest?.skillId === sel ? recommendedQuest : null;
  const routedQuest = selectedQuest?.signals[0]?.preparation ? selectedQuest : undefined;
  const selectedRoutes = routedQuest?.signals ?? selNode?.preparationSignals;
  const newSet = useMemo(() => new Set(s.newOpps), [s.newOpps]);
  const questSkill = recommendedQuest?.skillId;
  const questNode = allTree.find(n => n.skill === questSkill);
  const flow = useRef<ReactFlowInstance | null>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState(3);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setColumns(entry.contentRect.width < 500 ? 1 : 3));
    if (canvas.current) observer.observe(canvas.current);
    return () => observer.disconnect();
  }, []);
  const graphKey = layoutKey(tree);
  const [arranged, setArranged] = useState<{ key: string; layout: TreeLayout } | null>(null);
  const [layoutError, setLayoutError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    const structure: TreeNode[] = JSON.parse(graphKey).map(([skill, depth, prereq, sequence]: [string, number, string[], string[]]) =>
      ({ skill, depth, prereq, sequence } as TreeNode));
    void layoutTree(structure).then(layout => {
      if (!cancelled) { setArranged({ key: graphKey, layout }); setLayoutError(false); }
    }).catch(() => { if (!cancelled) setLayoutError(true); });
    return () => { cancelled = true; };
  }, [graphKey]);
  const fallback = useMemo(() => layoutProgression(tree, columns), [tree, columns]);
  const layout = arranged?.key === graphKey ? arranged.layout : fallback;
  const focusStage = (depth: number) => {
    const band = layout.bands.find(b => b.depth === depth);
    if (band) void flow.current?.fitView({ nodes: band.skills.slice(0, columns * 2).map(id => ({ id })), padding: 0.3, maxZoom: 1, duration: 300 });
  };
  // 증빙 파일 목록(이 브라우저에만 저장)
  const [proofs, setProofs] = useState<Record<string, ProofMeta>>({});
  const loadProofs = useCallback(() => {
    listProofs(p.pseudoId).then(setProofs).catch(() => setProofs({}));
  }, [p.pseudoId]);
  useEffect(loadProofs, [loadProofs]);
  const cancel = (skill: string) => (s.setScore(skill, ""), s.setSkill(skill, "none"));

  const { nodes, edges } = useMemo(() => {
    const visibleIds = new Set(tree.map(n => n.skill));
    const nodes: Node[] = tree.map((n) => {
      return {
        id: n.skill,
        type: "skill",
        position: layout.positions.get(n.skill)!,
        data: { node: n, isNew: n.opportunities.some((o) => newSet.has(o.id)), now, proof: !!proofs[n.skill], recommended: n.skill === questSkill },
      };
    });
    nodes.push(...layout.bands.map(band => ({ id: `stage-${band.depth}`, type: "stage", position: { x: 0, y: band.y }, selectable: false, data: { ...progressionStage(band.depth, mode, domain), width: band.width, count: band.skills.length } })));
    const edges: Edge[] = tree.flatMap((n) =>
      [...n.prereq.filter(q => visibleIds.has(q)).map((q) => ({ id: `${q}-${n.skill}`, source: q, target: n.skill, animated: n.state === "none" && !n.locked, style: { stroke: n.locked ? "#4a5078" : "#7c6cff", strokeWidth: 2 } })),
       ...(n.sequence ?? []).filter(q => visibleIds.has(q)).map((q) => ({ id: `startup-${q}-${n.skill}`, source: q, target: n.skill, style: { stroke: '#7c6cff', strokeWidth: 1.5, strokeDasharray: '5 4' } }))],
    );
    for (const edge of edges) {
      edge.type = "smoothstep";
      edge.markerEnd = { type: MarkerType.ArrowClosed, color: "#7c6cff" };
      edge.style = { ...edge.style, opacity: sel ? (edge.source === sel || edge.target === sel ? 1 : 0.12) : 0.4 };
    }
    return { nodes, edges };
  }, [tree, layout, mode, domain, newSet, now, proofs, questSkill, sel]);

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
            {mode === "employment" && <div role="tablist" aria-label="스킬트리 영역" className="flex gap-2">
              {(["common", "specialist"] as const).map(value => {
                const group = allTree.filter(n => routeFor(n).domain === value);
                const core = group.filter(countsTowardTrack);
                const pct = core.length ? Math.round(core.reduce((sum, n) => sum + (n.state === "verified" ? 1 : n.state === "self" ? 0.6 : 0), 0) / core.length * 100) : 0;
                return <button key={value} role="tab" aria-selected={domain === value} className={domain === value ? "btn-primary text-xs" : "btn-ghost text-xs"} onClick={() => { setDomain(value); setSel(null); }}>
                  {value === "common" ? "공통 역량" : "전공·직무 전문"} · {group.length}개 · {pct}%
                </button>;
              })}
            </div>}
            <span className="text-xs text-ink/60">현재 영역 {tree.length}개 · 지금 도전 {readyCount}개</span>
          </div>
          <div className="space-y-2 border-b border-line px-3 py-2">
            <p className="text-xs text-ink/70">위에서 아래로 준비 → 응용 → 전문 · 실선은 선행 조건, 점선은 권장 순서 · 같은 높이는 병행 가능</p>
            {layoutError && <p role="status" className="text-xs text-ink/70">기본 단계 배치로 표시 중이에요.</p>}
            <div className="flex flex-wrap gap-1" aria-label="준비 단계 이동">
              {layout.bands.map((band, index) => <button key={band.depth} className="btn-ghost !px-2 !py-1 text-xs" onClick={() => focusStage(band.depth)}>{index + 1}. {progressionStage(band.depth, mode, domain).title}</button>)}
            </div>
          </div>
          <div ref={canvas} className="min-h-0 flex-1">
            {tree.length === 0 ? <p className="p-5 text-sm text-ink/70">이 직무에 연결된 자격이나 작업물 퀘스트를 준비 중이에요.</p> : <ReactFlow
              key={mode + domain + columns + String(arranged?.key === graphKey) + nodes.map((node) => node.id).sort().join("|")}
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              minZoom={0.2}
              fitViewOptions={{ nodes: nodes.filter(n => sel ? n.id === sel : layout.bands[0]?.skills.slice(0, columns * 2).includes(n.id)), padding: 0.3, maxZoom: 1 }}
              onInit={(instance) => { flow.current = instance; }}
              panOnScroll
              zoomOnScroll={false}
              onNodeClick={(_, n) => { if (n.type === "skill") setSel(n.id); }}
              nodesDraggable={false}
              colorMode="dark"
            >
              <Background gap={24} color="#2a2f52" />
              <Controls showInteractive={false} />
            </ReactFlow>}
          </div>

          {selNode && outcome && (
            <div key={selNode.skill} className="window absolute bottom-3 right-3 z-10 max-h-[70%] w-72 overflow-y-auto p-4">
              <button className="absolute right-2 top-2 text-slate-400" onClick={() => setSel(null)} aria-label="닫기">
                <X size={16} />
              </button>
              <p className="pr-4 text-xs text-slate-500">{selNode.name} · {outcome.label}</p>
              <h3 className="font-bold">{outcome.title}</h3>
              <p className="mt-2 text-xs"><strong>완료 기준</strong> {outcome.completion}</p>
              {askNode && <AskNodeButton node={askNode} />}
              {selNode.commonExamOption && !countsTowardTrack(selNode) && <p className="mt-2 text-xs text-ink/70">목표에 맞으면 선택하세요. 취득 결과를 기록하면 추가 경험치를 받아요.</p>}
              {selNode.credentialOption && !selectedRoutes?.some(s => s.preparation?.action === selNode.credentialOption?.reason) &&
                <p className="mt-2 text-xs"><strong>직무와의 연결</strong> {selNode.credentialOption.reason}</p>}
              <p className="mt-1 text-xs text-go">{progressionStage(selNode.depth, mode, mode === "employment" ? routeFor(selNode).domain : undefined).title}</p>
              {[...selNode.prereq, ...selNode.sequence ?? []].some(id => allTree.some(n => n.skill === id && mode === "employment" && routeFor(n).domain !== domain)) &&
                <div className="mt-2 space-y-1 text-xs"><p>다른 트리에서 이어지는 준비</p>{[...new Set([...selNode.prereq, ...selNode.sequence ?? []])].map(id => allTree.find(n => n.skill === id)).filter(n => n && mode === "employment" && routeFor(n).domain !== domain).map(n => n &&
                  <button key={n.skill} className="block text-go underline" onClick={() => openNode(n.skill)}>{routeFor(n).domain === "common" ? "공통 역량" : "전공·직무 전문"} · {n.name} · {n.state === "none" ? "준비 전" : "완료"}</button>)}</div>}
              {selNode.route?.reason && <p className="mt-2 text-xs text-ink/70">{selNode.route.reason}</p>}
              {!!selNode.sequence?.length && <p className="mt-2 text-xs text-ink/70">먼저 준비하면 좋은 과제: {selNode.sequence.map(id => allTree.find(n => n.skill === id)?.name).join(", ")} · 지원 자격과는 별개인 권장 순서예요.</p>}
              {selNode.startup && <StartupDetail node={selNode} recommended={!!selectedQuest} />}
              {!selNode.startup && selectedQuest && !routedQuest && (
                <QuestDetail node={selNode} quest={selectedQuest} loadAction={s.getQuestAction} showAction={!selectedRoutes?.length && !selNode.practice} />
              )}
              {!selNode.startup && !!selectedRoutes?.length && <PreparationDetail node={selNode} signals={selectedRoutes} quest={routedQuest} />}
              {!selNode.startup && !selectedQuest && !selectedRoutes?.length && !!selNode.evidence?.length && (
                <div className="mt-2 space-y-1 text-xs"><EvidenceLinks signals={selNode.evidence} /></div>
              )}
              {selNode.practice && (
                <div className="mt-2 space-y-1 border-l-2 border-line pl-2 text-xs">
                  <p className="font-bold">직무 연습 제안{selNode.prereq.length > 0 && ` · ${skillById(selNode.prereq[0])?.name}`}</p>
                  <p>{selNode.practice.action}</p>
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
                    <Check size={16} /> {proofs[selNode.skill] ? "완료 · 결과물 첨부" : "보유 역량으로 완료 처리됨"}
                  </p>
                  <button className="btn-ghost mt-2 !py-1 text-xs" onClick={() => cancel(selNode.skill)}>
                    완료 취소
                  </button>
                </>
              )}
              <ProofField owner={p.pseudoId} skill={selNode.skill} proof={proofs[selNode.skill]} onChange={loadProofs} />
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
            {tree.map((n, index) => {
              const done = n.state !== "none";
              return (
                <li key={n.skill} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                  {(index === 0 || tree[index - 1].depth !== n.depth) && <p className="w-full py-2 font-bold text-go">{progressionStage(n.depth, mode, domain).title}</p>}
                  <span className={`grid size-6 shrink-0 place-items-center rounded ${done ? "bg-ok text-white" : "border border-line"}`}>
                    {done && <Check size={14} />}
                  </span>
                  <button className="min-w-0 flex-1 text-left hover:underline" onClick={() => openNode(n.skill)}>
                    <span className="font-semibold">{done && !proofs[n.skill] ? n.name : questOutcome(n)?.title ?? n.name}</span>
                    <span className="ml-1.5 text-xs text-ink/60">
                      {n.kind}
                      {n.required && " · 트랙 기본"}
                      {n.score && ` · ${formatScore(n.skill, n.score)}`}
                      {proofs[n.skill] && " · 증빙 첨부"}
                      {!done && n.locked && " · 선행 작업 준비 필요"}
                    </span>
                  </button>
                  {done ? (
                    <button className="btn-ghost !py-1 text-xs" onClick={() => cancel(n.skill)}>
                      완료 취소
                    </button>
                  ) : scaleOf(n.skill) ? (
                    <button className="btn-primary !py-1 text-xs" onClick={() => openNode(n.skill)}>
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
          <p className="mt-2 text-xs text-ink/60">노드를 누르면 완료 기준을 확인하고 작업물이나 취득 증빙을 붙일 수 있어요.</p>
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
            {questNode && recommendedQuest && (
              <p className="mt-3 text-sm">
                추천 퀘스트 · <button type="button" className="font-bold hover:underline" onClick={() => openNode(questNode.skill)}>{recommendedTitle(questNode, recommendedQuest)}</button>
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
