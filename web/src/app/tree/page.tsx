"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Award, Lock, Sparkles, Swords, X } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { OppCard } from "@/components/OppCard";
import { AiNotice, DDay, TypeTag, VirtualTag } from "@/components/ui";
import { useStore } from "@/lib/store";
import { buildTree, dday, nextNode, progress, recommend, type TreeNode } from "@/lib/engine";
import { jobById, skillById } from "@/lib/data/catalog";
import { getDepartment } from "@/lib/data/departments";
import { questProgress } from "@/lib/quest";

type SkillNodeData = { node: TreeNode; isNew: boolean; now: Date };

function SkillNode({ data }: NodeProps<Node<SkillNodeData>>) {
  const { node, isNew, now } = data;
  const done = node.state !== "none";
  const opps = node.opportunities;
  const soonest = opps.length ? Math.min(...opps.map((o) => dday(o, now))) : null;
  return (
    <div
      className={`w-48 rounded-lg border-2 bg-white px-3 py-2 text-left text-sm shadow-sm ${
        done ? "border-navy" : node.locked ? "border-dashed border-slate-300 text-slate-400" : "border-slate-300"
      } ${opps.length ? (isNew ? "!border-accent ring-4 ring-accent/30" : "!border-danger") : ""}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-400" />
      <div className="flex items-center gap-1 font-bold">
        {node.locked && <Lock size={12} />}
        {node.name}
      </div>
      <div className="text-[11px] text-slate-500">
        {node.state === "verified" ? "검증됨" : node.state === "self" ? "완료 (자기 보고)" : node.locked ? "선행 노드 필요" : node.required ? "필수 노드" : "선택 노드"}
      </div>
      {opps.length > 0 && (
        <div className={`mt-1 text-[11px] font-bold ${isNew ? "text-accent" : "text-danger"}`}>
          {isNew ? "새 기회 열림" : `기회 ${opps.length}건`} · D-{soonest}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-slate-400" />
    </div>
  );
}
const nodeTypes = { skill: SkillNode };

function TreeView() {
  const s = useStore();
  const p = s.profile!;
  const now = s.nowDate;
  const job = jobById(p.jobId)!;
  const dept = getDepartment(p.departmentId);
  const tree = useMemo(() => buildTree(p, s.opportunities, now), [p, s.opportunities, now]);
  const recs = useMemo(() => recommend(s.opportunities, p, now), [s.opportunities, p, now]);
  const prog = progress(p);
  const [sel, setSel] = useState<string | null>(null);
  const selNode = tree.find((n) => n.skill === sel);
  const newSet = new Set(s.newOpps);

  const { nodes, edges } = useMemo(() => {
    const perDepth: Record<number, number> = {};
    const nodes: Node<SkillNodeData>[] = tree.map((n) => {
      const row = (perDepth[n.depth] = (perDepth[n.depth] ?? -1) + 1);
      return {
        id: n.skill,
        type: "skill",
        position: { x: row * 215, y: n.depth * 115 },
        data: { node: n, isNew: n.opportunities.some((o) => newSet.has(o.id)), now },
      };
    });
    const edges: Edge[] = tree.flatMap((n) =>
      n.prereq.map((q) => ({ id: `${q}-${n.skill}`, source: q, target: n.skill, animated: n.state === "none" && !n.locked })),
    );
    return { nodes, edges };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree, s.newOpps, now]);

  const newOpp = s.opportunities.find((o) => newSet.has(o.id) && tree.some((n) => n.opportunities.includes(o)));
  const next = nextNode(p);
  const activeQuest = s.followed
    .map((id) => s.opportunities.find((o) => o.id === id)!)
    .filter((o) => o && dday(o, now) >= 0)
    .sort((a, b) => dday(a, now) - dday(b, now))[0];
  const qp = activeQuest ? questProgress(activeQuest, s.quests[activeQuest.id]) : null;

  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-4 p-4">
        <div>
          <p className="text-xs text-slate-500">
            {dept?.name} {p.grade}학년 · {p.pseudoId}
          </p>
          <h1 className="text-lg font-bold">
            나의 스킬트리 · 목표: <span className="text-navy">{job.name}</span>
          </h1>
        </div>
        <div className="flex min-w-48 flex-1 items-center gap-3">
          <span className="font-bold text-navy">Lv.{prog.level}</span>
          <div className="h-2.5 flex-1 rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-navy transition-all" style={{ width: `${prog.pct}%` }} />
          </div>
          <span className="text-xs text-slate-500">EXP {prog.pct}%</span>
        </div>
        {newOpp && (
          <Link
            href={`/opportunities/${newOpp.id}`}
            onClick={() => s.clearNew()}
            className="chip animate-pulse border border-danger bg-red-50 px-3 py-1.5 text-danger"
          >
            <Sparkles size={12} /> 새 기회 열림 · {newOpp.title} · D-{dday(newOpp, now)}
          </Link>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="card relative h-[600px] overflow-hidden">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.12, maxZoom: 1.1 }}
            onNodeClick={(_, n) => setSel(n.id)}
            nodesDraggable={false}
          >
            <Background gap={20} color="#e2e8f0" />
            <Controls showInteractive={false} />
          </ReactFlow>
          <p className="absolute bottom-2 left-12 text-[11px] text-slate-400">노드를 눌러 상태를 바꾸고 연결된 기회를 확인하세요</p>

          {selNode && (
            <div className="absolute right-3 top-3 z-10 w-72 rounded-xl border border-slate-200 bg-white p-4 shadow-lg">
              <button className="absolute right-2 top-2 text-slate-400" onClick={() => setSel(null)} aria-label="닫기">
                <X size={16} />
              </button>
              <p className="text-xs text-slate-500">{selNode.kind}</p>
              <h3 className="font-bold">{selNode.name}</h3>
              {skillById(selNode.skill)?.officialUrl && (
                <a href={skillById(selNode.skill)!.officialUrl} target="_blank" rel="noreferrer" className="text-xs underline">
                  공식 안내 확인
                </a>
              )}
              <div className="mt-3 flex gap-1.5">
                {selNode.state === "none" ? (
                  <button className="btn-primary !py-1 text-xs" onClick={() => s.setSkill(selNode.skill, "self")}>
                    완료로 표시
                  </button>
                ) : (
                  <button className="btn-ghost !py-1 text-xs" onClick={() => s.setSkill(selNode.skill, "none")}>
                    완료 취소
                  </button>
                )}
              </div>
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

        <aside className="space-y-4">
          <div className="card p-4">
            <h2 className="flex items-center gap-1.5 font-bold">
              <Swords size={16} className="text-accent" /> 오늘의 퀘스트
            </h2>
            {activeQuest && qp ? (
              <Link href={`/opportunities/${activeQuest.id}`} className="mt-2 block rounded-lg bg-paper p-3 text-sm hover:bg-slate-100">
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
            {next && (
              <p className="mt-3 text-sm">
                다음 노드: <b>{skillById(next.skill)?.name}</b>{" "}
                <span className="text-xs text-slate-500">(주 {p.weeklyHours}시간 기준)</span>
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
