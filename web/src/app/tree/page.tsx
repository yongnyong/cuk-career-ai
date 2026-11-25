"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps, type ReactFlowInstance } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AudioWaveform, Award, Check, ChevronRight, KeyRound, Network, Pencil, Plus, Printer, Rows3, Swords, Trash2, X, ZoomIn } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { OppCard } from "@/components/OppCard";
import { ProofField } from "@/components/ProofField";
import { listProofs, type ProofMeta } from "@/lib/files";
import { COMPACT_DIAMETER, Legend, NodeBox, StatusWindow } from "@/components/quest-ui";
import { AiNotice, DDay, TypeTag, VirtualTag } from "@/components/ui";
import { useStore } from "@/lib/store";
import { dday, recommend, type TreeNode } from "@/lib/engine";
import type { RecommendedQuest, TreeSignal } from "@/lib/types";
import { formatScore, jobById, meetsTarget, scaleOf, skillById } from "@/lib/data/catalog";
import { AskNodeButton, useAssistantNode } from "@/components/Assistant";
import { SkillWave } from "@/components/SkillWave";
import { questProgress } from "@/lib/quest";
import { questOutcome, recommendedTitle } from "@/lib/questOutcome";
import { careerInterestOf } from "@/lib/interest";
import { layoutProgression, progressionStage } from "@/lib/treeProgression";
import { MyNodeForm } from "@/components/MyNodeForm";
import { removeNode } from "@/lib/customTree";
import type { CustomNode } from "@/lib/types";
import { currentSemester, layoutFocus, layoutRadial, nodeWeights, RADIAL_RX, RADIAL_RY, type Advantage, type WeightTier } from "@/lib/treeRadial";

type SkillNodeData = { node: TreeNode; isNew: boolean; now: Date; proof: boolean; recommended: boolean; weight: WeightTier; radial: boolean; compact: boolean };
// 방사형에서는 간선을 노드 중심끼리 직선으로 잇는다
const CENTER_HANDLE = { top: "50%", left: "50%", opacity: 0 };

function SkillNode({ data }: NodeProps<Node<SkillNodeData>>) {
  // 원형 노드는 간선을 원의 중심에 잇는다
  const handle = data.compact ? { ...CENTER_HANDLE, top: COMPACT_DIAMETER[data.weight] / 2 } : data.radial ? CENTER_HANDLE : undefined;
  return (
    <>
      <Handle type="target" position={Position.Top} className="!border-0 !bg-edge" style={handle} />
      <NodeBox node={data.node} isNew={data.isNew} now={data.now} proof={data.proof} recommended={data.recommended} weight={data.weight} compact={data.compact} />
      <Handle type="source" position={Position.Bottom} className="!border-0 !bg-edge" style={handle} />
    </>
  );
}
type RingsData = { rings: { rx: number; ry: number }[]; sectors: { start: number; end: number }[]; width: number; height: number };
function RingsNode({ data }: NodeProps<Node<RingsData>>) {
  const cx = data.width / 2, cy = data.height / 2;
  return <svg width={data.width} height={data.height} className="pointer-events-none">
    {data.rings.map((r) => <ellipse key={r.rx} cx={cx} cy={cy} rx={r.rx} ry={r.ry} fill="none" stroke="#3d4680" strokeDasharray="4 6" />)}
    {data.sectors.length > 1 && data.sectors.map((sector) => <line key={sector.start} x1={cx} y1={cy}
      x2={cx + Math.cos(sector.start) * (cx - 10)} y2={cy + Math.sin(sector.start) * (cy - 10)} stroke="#2f3560" />)}
  </svg>;
}
function HubNode({ data }: NodeProps<Node<{ title: string; detail: string }>>) {
  return <div className="w-32 rounded-full border-2 border-go bg-paper px-3 py-2 text-center shadow-[0_0_24px_rgb(70_166_255/0.35)]">
    <Handle type="source" position={Position.Top} style={CENTER_HANDLE} />
    <p className="text-[11px] text-go">{data.detail}</p>
    <p className="text-sm font-bold leading-tight">{data.title}</p>
  </div>;
}
function SectorNode({ data }: NodeProps<Node<{ kind: string; count: number }>>) {
  return <span className="chip border border-line bg-panel px-2 py-1 text-xs text-ink/80">{data.kind} {data.count}</span>;
}
function AdvantageNode({ data }: NodeProps<Node<Advantage>>) {
  return <div className="w-48 rounded-md border-2 border-gold/70 bg-panel p-2 text-left">
    <Handle type="target" position={Position.Top} style={CENTER_HANDLE} />
    <p className="text-sm font-bold leading-tight">{data.label}</p>
    <p className="flex items-center gap-1 text-[11px] font-bold text-gold">
      {data.count > 0 ? <><KeyRound size={11} /> 공고 {data.count}건</> : <span className="font-normal text-ink/60">지금 열린 공고 없음</span>}
      {data.detail && <span className="font-normal text-ink/60">· {data.detail}</span>}
    </p>
    {data.orgs.length > 0 && <p className="mt-0.5 text-[11px] text-ink/70">{data.orgs.join(" · ")}</p>}
  </div>;
}
type StageData = { title: string; detail: string; width: number; count: number };
function StageNode({ data }: NodeProps<Node<StageData>>) {
  return <div style={{ width: data.width }} className="border-b border-go/40 bg-panel pb-3 text-ink">
    <p className="text-base font-bold">{data.title} <span className="text-xs font-normal text-ink/60">{data.count}개</span></p>
    <p className="mt-1 text-xs text-ink/65">{data.detail}</p>
  </div>;
}
const nodeTypes = { skill: SkillNode, stage: StageNode, rings: RingsNode, hub: HubNode, sector: SectorNode, advantage: AdvantageNode };

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
  const { tree, recommendedQuest, treeProgress } = s.careerPath!;
  const readyCount = tree.filter((node) => node.state === "none" && !node.locked).length;
  const recs = useMemo(() => recommend(s.opportunities, p, now), [s.opportunities, p, now]);
  const [sel, setSel] = useState<string | null>(null);
  const selNode = tree.find((n) => n.skill === sel);
  const outcome = selNode && questOutcome(selNode);
  // 비서 카탈로그에는 직무 기본 노드만 있다. 공고·활동에서 더해진 노드는 이름만 넘긴다
  const askNode = selNode ? { name: selNode.name, ...(jobById(p.jobId)?.nodes.some((n) => n.skill === selNode.skill) ? { skillId: selNode.skill } : {}) } : null;
  useAssistantNode(askNode);
  const selectedQuest = recommendedQuest?.skillId === sel ? recommendedQuest : null;
  const routedQuest = selectedQuest?.signals[0]?.preparation ? selectedQuest : undefined;
  const selectedRoutes = routedQuest?.signals ?? selNode?.preparationSignals;
  const newSet = useMemo(() => new Set(s.newOpps), [s.newOpps]);
  const questSkill = recommendedQuest?.skillId;
  const questNode = tree.find(n => n.skill === questSkill);
  const mode = careerInterestOf(p);
  const flow = useRef<ReactFlowInstance | null>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState(3);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setColumns(entry.contentRect.width < 500 ? 1 : 3));
    if (canvas.current) observer.observe(canvas.current);
    return () => observer.disconnect();
  }, []);
  const layout = useMemo(() => layoutProgression(tree, columns), [tree, columns]);
  const [view, setView] = useState<"wave" | "radial" | "steps">("wave");
  // 자세히 보기로 들어간 노드들. 마지막이 지금 가운데에 있는 노드
  const [focusPath, setFocusPath] = useState<string[]>([]);
  const trail = useMemo(() => focusPath.filter((id) => tree.some((n) => n.skill === id)), [focusPath, tree]);
  const focus = trail.length ? trail[trail.length - 1] : undefined;
  const weights = useMemo(() => nodeWeights(tree), [tree]);
  const radial = useMemo(() => layoutRadial(tree), [tree]);
  const focusLayout = useMemo(() => focus ? layoutFocus(tree, focus, s.opportunities, now, p.jobId) : null, [tree, focus, s.opportunities, now, p.jobId]);
  const centered = view === "radial" || !!focusLayout;
  const openFocus = (skill: string) => { setFocusPath((path) => [...path.filter((id) => id !== skill), skill]); setSel(skill); };
  const focusStage = (depth: number) => {
    const band = layout.bands.find(b => b.depth === depth);
    if (band) void flow.current?.fitView({ nodes: [{ id: `stage-${depth}` }, ...band.skills.slice(0, columns * 2).map(id => ({ id }))], padding: 0.15, maxZoom: 1, duration: 300 });
  };
  // 증빙 파일 목록(이 브라우저에만 저장)
  const [proofs, setProofs] = useState<Record<string, ProofMeta>>({});
  const loadProofs = useCallback(() => {
    listProofs(p.pseudoId).then(setProofs).catch(() => setProofs({}));
  }, [p.pseudoId]);
  useEffect(loadProofs, [loadProofs]);
  // 내가 추가한 노드는 완료 여부를 노드에 저장한다(직무 카탈로그 기록과 섞지 않는다)
  const myNodes = useMemo(() => p.myNodes?.[p.jobId] ?? [], [p.myNodes, p.jobId]);
  const saveMine = (nodes: CustomNode[]) => s.setProfile({ ...p, myNodes: { ...p.myNodes, [p.jobId]: nodes } });
  const setMineDone = (skill: string, done: boolean) => saveMine(myNodes.map((n) => (n.id === skill ? { ...n, done } : n)));
  const isMine = (skill: string) => myNodes.some((n) => n.id === skill);
  const markDone = (skill: string) => (isMine(skill) ? setMineDone(skill, true) : s.setSkill(skill, "self"));
  const cancel = (skill: string) => (isMine(skill) ? setMineDone(skill, false) : (s.setScore(skill, ""), s.setSkill(skill, "none")));
  // 내 노드 추가·수정 창: parent가 있으면 그 노드 다음에 붙인다
  const [editing, setEditing] = useState<{ parent?: string; node?: CustomNode } | null>(null);
  const saveEdited = (node: CustomNode) => {
    saveMine(myNodes.some((n) => n.id === node.id) ? myNodes.map((n) => (n.id === node.id ? node : n)) : [...myNodes, node]);
    setEditing(null);
    setSel(node.id);
  };

  const { nodes, edges } = useMemo(() => {
    const positionOf = (skill: string) => focusLayout ? focusLayout.positions.get(skill) : view === "radial" ? radial.positions.get(skill) : layout.positions.get(skill);
    const shown = tree.filter((n) => positionOf(n.skill));
    const nodes: Node[] = shown.map((n) => {
      return {
        id: n.skill,
        type: "skill",
        position: positionOf(n.skill)!,
        data: { node: n, isNew: n.opportunities.some((o) => newSet.has(o.id)), now, proof: !!proofs[n.skill], recommended: n.skill === questSkill, weight: weights.get(n.skill)?.tier ?? 2, radial: centered, compact: view === "radial" && !focusLayout },
      };
    });
    if (focusLayout) {
      const radii = [...focusLayout.rings.map((ring) => Math.hypot(focusLayout.positions.get(ring[0].skill)!.x, focusLayout.positions.get(ring[0].skill)!.y)), focusLayout.outer];
      const size = 2 * focusLayout.outer + 260;
      nodes.unshift({ id: "rings", type: "rings", position: { x: 0, y: 0 }, selectable: false, zIndex: -1, data: { rings: radii.map((r) => ({ rx: r, ry: r })), sectors: [], width: size, height: size } });
      nodes.push(...focusLayout.advantages.map((a) => ({ id: `adv-${a.id}`, type: "advantage", position: focusLayout.advantagePositions.get(a.id)!, selectable: false, data: a })));
    } else if (view === "radial") {
      const edge = radial.outer + 80;
      nodes.unshift({ id: "rings", type: "rings", position: { x: 0, y: 0 }, selectable: false, zIndex: -1, data: {
        rings: radial.rings.map(({ r }) => ({ rx: r * RADIAL_RX, ry: r * RADIAL_RY })), sectors: radial.sectors, width: 2 * edge * RADIAL_RX, height: 2 * edge * RADIAL_RY } });
      nodes.push({ id: "hub", type: "hub", position: { x: 0, y: 0 }, selectable: false, data: { title: jobById(p.jobId)?.name ?? "목표 직무", detail: mode === "startup" ? "창업 준비" : "목표 직무" } });
      nodes.push(...radial.sectors.map((sector) => {
        const angle = (sector.start + sector.end) / 2;
        return { id: `sector-${sector.kind}`, type: "sector", position: { x: Math.cos(angle) * (radial.outer + 100) * RADIAL_RX, y: Math.sin(angle) * (radial.outer + 100) * RADIAL_RY }, selectable: false, data: { kind: sector.kind, count: sector.count } };
      }));
    } else {
      nodes.push(...layout.bands.map(band => ({ id: `stage-${band.depth}`, type: "stage", position: { x: 0, y: band.y }, selectable: false, data: { ...progressionStage(band.depth, mode), width: band.width, count: band.skills.length } })));
    }
    const edges: Edge[] = shown.flatMap((n) =>
      [...n.prereq.map((q) => ({ id: `${q}-${n.skill}`, source: q, target: n.skill, animated: n.state === "none" && !n.locked, style: { stroke: n.locked ? "#4a5078" : "#7c6cff", strokeWidth: 2 } })),
       ...(n.sequence ?? []).map((q) => ({ id: `startup-${q}-${n.skill}`, source: q, target: n.skill, style: { stroke: '#7c6cff', strokeWidth: 1.5, strokeDasharray: '5 4' } }))],
    );
    const visible = new Set(shown.map((n) => n.skill));
    const kept: Edge[] = edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target));
    if (view === "radial" && !focusLayout) {
      // 선수가 없는 노드는 가운데 목표 직무에서 뻗어 나간다
      kept.push(...shown.filter((n) => ![...n.prereq, ...(n.sequence ?? [])].some((q) => visible.has(q)))
        .map((n) => ({ id: `hub-${n.skill}`, source: "hub", target: n.skill, style: { stroke: "#46a6ff", strokeWidth: 1, strokeDasharray: "2 6" } })));
    }
    if (focusLayout) {
      kept.push(...focusLayout.advantages.map((a) => ({ id: `adv-${a.id}`, source: focusLayout.center, target: `adv-${a.id}`, style: { stroke: "#f5c451", strokeWidth: 1.5, strokeDasharray: "5 4" } })));
    }
    for (const edge of kept) {
      if (centered) edge.type = "straight";
      else edge.markerEnd = { type: MarkerType.ArrowClosed, color: "#7c6cff" };
      edge.style = { ...edge.style, opacity: sel ? (edge.source === sel || edge.target === sel ? 1 : 0.12) : 0.4 };
    }
    return { nodes, edges: kept };
  }, [tree, layout, radial, focusLayout, view, centered, weights, p.jobId, mode, newSet, now, proofs, questSkill, sel]);

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
        <div className={`relative flex ${view !== "steps" || focusLayout ? "h-[760px]" : "h-[620px]"} min-w-0 flex-col overflow-hidden rounded-lg border-2 border-edge bg-panel`}>
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
            <Legend />
            <span className="text-xs text-ink/60">전체 {tree.length}개 · 지금 도전 {readyCount}개</span>
          </div>
          <div className="space-y-2 border-b border-line px-3 py-2">
            {focusLayout ? <>
              <nav className="flex flex-wrap items-center gap-1 text-xs" aria-label="자세히 보기 경로">
                <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => setFocusPath([])}>전체 트리</button>
                {trail.map((id, index) => <span key={id} className="flex items-center gap-1">
                  <ChevronRight size={12} className="text-ink/50" />
                  <button className={`btn-ghost !px-2 !py-1 text-xs ${index === trail.length - 1 ? "font-bold text-go" : ""}`} onClick={() => setFocusPath(trail.slice(0, index + 1))}>{tree.find((n) => n.skill === id)!.name}</button>
                </span>)}
              </nav>
              <p className="text-xs text-ink/70">
                안쪽 고리: 이 노드 다음에 열리는 노드{focusLayout.rings.length === 0 && "(아직 없어요)"} · 바깥 노란 카드: 이 역량이 쓰이는 직무와 공고를 낸 기관
                {focusLayout.advantages.length === 0 && " · 아직 연결된 직무나 공고가 없어요"}
              </p>
            </> : <>
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex overflow-hidden rounded-md border border-line text-xs" role="group" aria-label="트리 보기 방식">
                  <button className={`flex items-center gap-1 px-2 py-1 ${view === "wave" ? "bg-go text-white" : ""}`} aria-pressed={view === "wave"} onClick={() => setView("wave")}><AudioWaveform size={12} /> 파형</button>
                  <button className={`flex items-center gap-1 px-2 py-1 ${view === "radial" ? "bg-go text-white" : ""}`} aria-pressed={view === "radial"} onClick={() => setView("radial")}><Network size={12} /> 방사형</button>
                  <button className={`flex items-center gap-1 px-2 py-1 ${view === "steps" ? "bg-go text-white" : ""}`} aria-pressed={view === "steps"} onClick={() => setView("steps")}><Rows3 size={12} /> 단계별</button>
                </div>
                <p className="text-xs text-ink/70">
                  {view === "wave" ? "12시 1학년부터 시계방향으로 졸업까지 · 막대 길이는 중요도" : view === "radial" ? "가운데에서 바깥으로 기초 → 심화 · 방향은 분류" : "위에서 아래로 기초 → 심화 · 수행 권장 순서"}
                  {mode === "startup" && " · 점선은 권장 흐름"} · <span className="text-gold">큰 노드(★ 핵심)부터 찍으면 돼요</span>
                </p>
              </div>
              {view === "steps" && <div className="flex flex-wrap gap-1" aria-label="준비 단계 이동">
                {layout.bands.map((band, index) => <button key={band.depth} className="btn-ghost !px-2 !py-1 text-xs" onClick={() => focusStage(band.depth)}>{index + 1}. {progressionStage(band.depth, mode).title}</button>)}
              </div>}
            </>}
          </div>
          <div ref={canvas} className="min-h-0 flex-1">
            {tree.length === 0 ? <p className="p-5 text-sm text-ink/70">이 직무에 연결된 자격이나 작업물 퀘스트를 준비 중이에요.</p> : view === "wave" && !focusLayout ? <SkillWave
              tree={tree}
              weights={weights}
              current={currentSemester(p.grade, now)}
              title={jobById(p.jobId)?.name ?? "목표 직무"}
              subtitle={mode === "startup" ? "창업 준비" : "목표 직무"}
              recommended={questSkill}
              onPick={openFocus}
            /> : <ReactFlow
              key={mode + columns + view + (focus ?? "") + nodes.map((node) => node.id).sort().join("|")}
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              minZoom={0.2}
              nodeOrigin={centered ? [0.5, 0.5] : [0, 0]}
              fitViewOptions={centered ? { nodes: nodes.filter(n => n.id !== "rings"), padding: 0.08, maxZoom: 1 } : { nodes: nodes.filter(n => n.id === `stage-${layout.bands[0]?.depth}` || layout.bands[0]?.skills.slice(0, columns * 2).includes(n.id)), padding: 0.15, maxZoom: 1 }}
              onInit={(instance) => { flow.current = instance; }}
              panOnScroll={!centered}
              zoomOnScroll={centered}
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
              {focus !== selNode.skill && (
                <button className="btn-ghost mt-2 w-full !py-1 text-xs" onClick={() => openFocus(selNode.skill)}>
                  <ZoomIn size={12} /> 자세히 보기 · 다음 노드와 유리한 곳
                </button>
              )}
              {selNode.mine?.note && <p className="mt-2 rounded bg-paper px-2 py-1 text-xs">메모 · {selNode.mine.note}</p>}
              {editing && (editing.parent === selNode.skill || editing.node?.id === selNode.skill) ? (
                <MyNodeForm tree={tree} mine={myNodes} parent={editing.parent} initial={editing.node} onSave={saveEdited} onCancel={() => setEditing(null)} />
              ) : (
                <div className="mt-2 flex flex-wrap gap-1">
                  <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => setEditing({ parent: selNode.skill })}>
                    <Plus size={12} /> 이 다음에 내 노드 추가
                  </button>
                  {selNode.mine && (
                    <>
                      <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => setEditing({ node: myNodes.find((n) => n.id === selNode.skill) })}>
                        <Pencil size={12} /> 수정
                      </button>
                      <button className="btn-ghost !px-2 !py-1 text-xs text-danger" onClick={() => { if (window.confirm(`내 노드 ‘${selNode.name}’를 삭제할까요?`)) { saveMine(removeNode(myNodes, selNode.skill)); setSel(null); } }}>
                        <Trash2 size={12} /> 삭제
                      </button>
                    </>
                  )}
                </div>
              )}
              {askNode && <AskNodeButton node={askNode} />}
              {selNode.credentialOption && !selectedRoutes?.some(s => s.preparation?.action === selNode.credentialOption?.reason) &&
                <p className="mt-2 text-xs"><strong>직무와의 연결</strong> {selNode.credentialOption.reason}</p>}
              <p className="mt-1 text-xs text-go">{progressionStage(selNode.depth, mode).title}</p>
              {!!selNode.sequence?.length && <p className="mt-2 text-xs text-ink/70">먼저 준비하면 좋은 과제: {selNode.sequence.map(id => tree.find(n => n.skill === id)?.name).join(", ")} · 지원 자격과는 별개인 권장 순서예요.</p>}
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
                  <button className="btn-gold mt-3 w-full" onClick={() => markDone(selNode.skill)}>
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
            <div className="flex flex-wrap gap-2">
              <button className="btn-primary !py-1 text-xs" onClick={() => setEditing({})}>
                <Plus size={12} /> 내 노드 추가
              </button>
              <Link href="/print" className="btn-ghost !py-1 text-xs">
                <Printer size={12} /> 완료 내역·증빙 인쇄
              </Link>
            </div>
          </div>
          {editing && !editing.parent && !editing.node && (
            <div className="mt-2 rounded-md border border-go p-3">
              <p className="text-xs text-ink/70">‘토브넷 입사 준비’처럼 목표 회사나 나만의 계획을 노드로 더해요. 중요도(★)가 노드 크기가 되고, 완료하면 하양이 진화에도 반영돼요.</p>
              <MyNodeForm tree={tree} mine={myNodes} onSave={saveEdited} onCancel={() => setEditing(null)} />
            </div>
          )}
          <ul className="mt-2 divide-y divide-line">
            {tree.map((n, index) => {
              const done = n.state !== "none";
              return (
                <li key={n.skill} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                  {(index === 0 || tree[index - 1].depth !== n.depth) && <p className="w-full py-2 font-bold text-go">{progressionStage(n.depth, mode).title}</p>}
                  <span className={`grid size-6 shrink-0 place-items-center rounded ${done ? "bg-ok text-white" : "border border-line"}`}>
                    {done && <Check size={14} />}
                  </span>
                  <button className="min-w-0 flex-1 text-left hover:underline" onClick={() => setSel(n.skill)}>
                    <span className="font-semibold">{done && !proofs[n.skill] ? n.name : questOutcome(n)?.title ?? n.name}</span>
                    <span className="ml-1.5 text-xs text-ink/60">
                      {n.kind}
                      {n.required && " · 트랙 기본"}
                      {n.mine && " · 내 노드"}
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
                    <button className="btn-primary !py-1 text-xs" onClick={() => markDone(n.skill)}>
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
                추천 퀘스트 · <button type="button" className="font-bold hover:underline" onClick={() => setSel(questNode.skill)}>{recommendedTitle(questNode, recommendedQuest)}</button>
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
