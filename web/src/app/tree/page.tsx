"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Award, KeyRound, Swords, X } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { OppCard } from "@/components/OppCard";
import { Legend, NodeBox, StatusWindow } from "@/components/quest-ui";
import { AiNotice, DDay, TypeTag, VirtualTag } from "@/components/ui";
import { useStore } from "@/lib/store";
import { buildTree, dday, nextNode, recommend, type TreeNode } from "@/lib/engine";
import { formatScore, meetsTarget, scaleOf, skillById } from "@/lib/data/catalog";
import { questProgress } from "@/lib/quest";

type SkillNodeData = { node: TreeNode; isNew: boolean; now: Date };

function SkillNode({ data }: NodeProps<Node<SkillNodeData>>) {
  return (
    <>
      <Handle type="target" position={Position.Top} className="!border-0 !bg-edge" />
      <NodeBox node={data.node} isNew={data.isNew} now={data.now} />
      <Handle type="source" position={Position.Bottom} className="!border-0 !bg-edge" />
    </>
  );
}
const nodeTypes = { skill: SkillNode };

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
  const tree = useMemo(() => buildTree(p, s.opportunities, now), [p, s.opportunities, now]);
  const recs = useMemo(() => recommend(s.opportunities, p, now), [s.opportunities, p, now]);
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
        position: { x: row * 215, y: n.depth * 130 + 50 },
        data: { node: n, isNew: n.opportunities.some((o) => newSet.has(o.id)), now },
      };
    });
    const edges: Edge[] = tree.flatMap((n) =>
      n.prereq.map((q) => ({ id: `${q}-${n.skill}`, source: q, target: n.skill, animated: n.state === "none" && !n.locked, style: { stroke: n.locked ? "#4a5078" : "#7c6cff", strokeWidth: 2 } })),
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
      <StatusWindow profile={p}>
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
        <div className="relative h-[620px] overflow-hidden rounded-lg border-2 border-edge bg-panel">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.12, maxZoom: 1.1 }}
            onNodeClick={(_, n) => setSel(n.id)}
            nodesDraggable={false}
            colorMode="dark"
          >
            <Background gap={24} color="#2a2f52" />
            <Controls showInteractive={false} />
          </ReactFlow>
          <div className="absolute inset-x-0 top-0 flex flex-wrap items-center justify-between gap-2 border-b border-line bg-panel/90 px-3 py-2">
            <Legend />
            <span className="text-xs text-ink/60">노드를 누르면 상태를 바꾸고 연결된 기회를 볼 수 있어요</span>
          </div>

          {selNode && (
            <div className="window absolute right-3 top-14 z-10 w-72 p-4">
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
              {skillById(selNode.skill)?.srcUrl && (
                <a href={skillById(selNode.skill)!.srcUrl} target="_blank" rel="noreferrer" className="block text-xs underline">
                  출처: 학과 홈페이지 안내
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
              <div className="mt-3 flex gap-1.5">
                {selNode.state === "none" ? (
                  <button className="btn-primary !py-1 text-xs" onClick={() => s.setSkill(selNode.skill, "self")}>
                    완료로 표시
                  </button>
                ) : (
                  <button className="btn-ghost !py-1 text-xs" onClick={() => (s.setScore(selNode.skill, ""), s.setSkill(selNode.skill, "none"))}>
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
              <Swords size={16} className="text-go" /> 오늘의 퀘스트
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
