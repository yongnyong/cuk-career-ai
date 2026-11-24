"use client";
import { useMemo, useState } from "react";
import { Copy, Plus, Star, Trash2, X } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { SkillWave } from "@/components/SkillWave";
import { useStore } from "@/lib/store";
import { emptyTree, fromCareerTree, KINDS, LIMITS, newNode, removeNode, toTreeNodes, wouldCycle } from "@/lib/customTree";
import { currentSemester, nodeWeights } from "@/lib/treeRadial";
import { jobById } from "@/lib/data/catalog";
import type { CustomNode, CustomTree, SkillKind } from "@/lib/types";

function TreeBuilder() {
  const s = useStore();
  const p = s.profile!;
  const trees = p.customTrees ?? [];
  const [selected, setSelected] = useState<string | null>(trees[0]?.id ?? null);
  const [focus, setFocus] = useState<string | null>(null);
  const tree = trees.find((t) => t.id === selected) ?? trees[0];
  const view = useMemo(() => (tree ? toTreeNodes(tree) : null), [tree]);

  const save = (next: CustomTree[]) => s.setProfile({ ...p, customTrees: next });
  const saveTree = (t: CustomTree) => save(trees.map((x) => (x.id === t.id ? { ...t, updatedAt: s.nowDate.toISOString() } : x)));
  const setNodes = (nodes: CustomNode[]) => tree && saveTree({ ...tree, nodes });
  const patch = (id: string, change: Partial<CustomNode>) => tree && setNodes(tree.nodes.map((n) => (n.id === id ? { ...n, ...change } : n)));
  const add = (t: CustomTree) => { save([...trees, t]); setSelected(t.id); };

  const copyCareer = () => {
    const career = s.careerPath?.tree ?? [];
    const job = jobById(p.jobId)?.name ?? "내 직무";
    add(fromCareerTree(`${job} 트리 (복사본)`, job, career, nodeWeights(career), s.nowDate));
  };

  return (
    <div className="space-y-4">
      <section className="window p-5">
        <h1 className="text-xl font-bold">내 트리 만들기</h1>
        <p className="mt-1 text-sm text-ink/70">‘토브넷 입사 루트’처럼 목표 회사나 직무까지 가는 길을 직접 설계해요. 노드마다 중요도(★)를 정하면 원형 파형의 막대 길이로 보여요.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {trees.map((t) => (
            <button key={t.id} className={`chip border px-3 py-1.5 text-sm ${t.id === tree?.id ? "border-go bg-go/15 text-go" : "border-line"}`} onClick={() => setSelected(t.id)}>
              {t.title || "제목 없음"} <span className="text-xs text-ink/60">{t.nodes.filter((n) => n.done).length}/{t.nodes.length}</span>
            </button>
          ))}
          <button className="btn-primary !py-1.5 text-sm" disabled={trees.length >= LIMITS.trees} onClick={() => add(emptyTree(s.nowDate))}><Plus size={14} /> 빈 트리</button>
          <button className="btn-ghost !py-1.5 text-sm" disabled={trees.length >= LIMITS.trees || !s.careerPath?.tree.length} onClick={copyCareer}><Copy size={14} /> 지금 스킬트리 복사해서 시작</button>
        </div>
      </section>

      {!tree || !view ? (
        <p className="card p-6 text-sm text-ink/70">아직 만든 트리가 없어요. ‘빈 트리’로 처음부터 만들거나, 지금 스킬트리를 복사해서 고쳐 써 보세요.</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <section className="card space-y-3 p-4">
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="text-xs font-bold text-ink/70">트리 이름
                <input className="input mt-1" maxLength={LIMITS.name} value={tree.title} onChange={(e) => saveTree({ ...tree, title: e.target.value })} placeholder="예: 토브넷 입사 루트" />
              </label>
              <label className="text-xs font-bold text-ink/70">목표 회사·직무 (원 가운데)
                <input className="input mt-1" maxLength={LIMITS.name} value={tree.goal} onChange={(e) => saveTree({ ...tree, goal: e.target.value })} placeholder="예: 토브넷 · 사업개발" />
              </label>
            </div>
            <ol className="space-y-2">
              {view.nodes.map((v) => {
                const n = tree.nodes.find((x) => x.id === v.skill)!;
                const candidates = tree.nodes.filter((o) => !n.prereq.includes(o.id) && !wouldCycle(tree.nodes, n.id, o.id));
                return (
                  <li key={n.id} id={`node-${n.id}`} className={`space-y-2 rounded-md border p-2 ${focus === n.id ? "border-go bg-go/10" : "border-line"}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <input type="checkbox" className="size-4 accent-[#2fd39a]" checked={n.done} onChange={(e) => patch(n.id, { done: e.target.checked })} aria-label={`${n.name} 완료`} />
                      <input className="input min-w-36 flex-1 !py-1" maxLength={LIMITS.name} value={n.name} onChange={(e) => patch(n.id, { name: e.target.value })} aria-label="노드 이름" />
                      <select className="input w-24 !py-1" value={n.kind} onChange={(e) => patch(n.id, { kind: e.target.value as SkillKind })} aria-label="분류">
                        {KINDS.map((k) => <option key={k}>{k}</option>)}
                      </select>
                      <span className="flex" role="radiogroup" aria-label="중요도">
                        {([1, 2, 3] as const).map((w) => (
                          <button key={w} role="radio" aria-checked={n.weight === w} aria-label={`중요도 ${w}`} onClick={() => patch(n.id, { weight: w })}>
                            <Star size={18} className={w <= n.weight ? "text-gold" : "text-ink/30"} fill={w <= n.weight ? "currentColor" : "none"} />
                          </button>
                        ))}
                      </span>
                      <button className="text-ink/50 hover:text-danger" aria-label={`${n.name} 삭제`} onClick={() => setNodes(removeNode(tree.nodes, n.id))}><Trash2 size={16} /></button>
                    </div>
                    <div className="flex flex-wrap items-center gap-1 text-xs">
                      <span className="text-ink/60">먼저 할 노드</span>
                      {n.prereq.map((q) => (
                        <span key={q} className="chip border border-line px-2 py-0.5">
                          {tree.nodes.find((o) => o.id === q)?.name}
                          <button aria-label="선수 노드 빼기" onClick={() => patch(n.id, { prereq: n.prereq.filter((x) => x !== q) })}><X size={12} /></button>
                        </span>
                      ))}
                      {candidates.length > 0 && (
                        <select className="input w-auto !py-0.5 text-xs" value="" onChange={(e) => e.target.value && patch(n.id, { prereq: [...n.prereq, e.target.value] })} aria-label="선수 노드 추가">
                          <option value="">+ 추가</option>
                          {candidates.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                        </select>
                      )}
                    </div>
                    <input className="input !py-1 text-xs" maxLength={LIMITS.note} value={n.note ?? ""} onChange={(e) => patch(n.id, { note: e.target.value })} placeholder="준비 팁·메모 (나중에 공유할 때 함께 보여요)" aria-label="메모" />
                  </li>
                );
              })}
            </ol>
            <div className="flex flex-wrap justify-between gap-2">
              <button className="btn-primary" disabled={tree.nodes.length >= LIMITS.nodes} onClick={() => setNodes([...tree.nodes, newNode()])}><Plus size={14} /> 노드 추가</button>
              <button className="btn-ghost text-danger" onClick={() => { if (window.confirm(`‘${tree.title}’ 트리를 삭제할까요? 되돌릴 수 없어요.`)) { save(trees.filter((t) => t.id !== tree.id)); setSelected(null); } }}>
                <Trash2 size={14} /> 트리 삭제
              </button>
            </div>
          </section>

          <section className="card flex h-[640px] flex-col overflow-hidden lg:sticky lg:top-20">
            <p className="border-b border-line px-3 py-2 text-xs text-ink/70">미리보기 · 막대 길이 = 중요도(★), 선수 관계 순서대로 1학년부터 배치 · 막대를 누르면 왼쪽 노드로 이동</p>
            <div className="min-h-0 flex-1">
              {view.nodes.length ? (
                <SkillWave
                  key={tree.id}
                  tree={view.nodes}
                  weights={view.weights}
                  current={currentSemester(p.grade, s.nowDate)}
                  title={tree.goal || tree.title || "내 트리"}
                  subtitle="내가 만든 트리"
                  onPick={(id) => { setFocus(id); document.getElementById(`node-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }); }}
                />
              ) : <p className="p-5 text-sm text-ink/70">노드를 추가하면 여기에 원형 파형으로 보여요.</p>}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export default function TreesPage() {
  return (
    <RequireProfile>
      <TreeBuilder />
    </RequireProfile>
  );
}
