"use client";
import { useState } from "react";
import { Star, X } from "lucide-react";
import { KINDS, LIMITS, newNode, wouldCycle } from "@/lib/customTree";
import type { TreeNode } from "@/lib/engine";
import type { CustomNode, SkillKind } from "@/lib/types";

/** 스킬트리에 내 노드를 추가하거나 고치는 작은 창. parent가 있으면 그 노드를 먼저 할 노드로 넣고 시작한다 */
export function MyNodeForm({ tree, mine, parent, initial, onSave, onCancel }: {
  tree: TreeNode[];
  mine: CustomNode[];
  parent?: string;
  initial?: CustomNode;
  onSave: (node: CustomNode) => void;
  onCancel: () => void;
}) {
  const [node, setNode] = useState<CustomNode>(() => initial ?? { ...newNode(""), prereq: parent ? [parent] : [] });
  const patch = (change: Partial<CustomNode>) => setNode((n) => ({ ...n, ...change }));
  const candidates = tree.filter((o) => o.skill !== node.id && !node.prereq.includes(o.skill) && !wouldCycle(mine, node.id, o.skill));
  const full = !initial && mine.length >= LIMITS.nodes;
  const name = node.name.trim();

  return (
    <form
      className="mt-2 space-y-2 text-xs"
      onSubmit={(e) => { e.preventDefault(); if (name && !full) onSave({ ...node, name }); }}
    >
      <input className="input !py-1" autoFocus maxLength={LIMITS.name} value={node.name} onChange={(e) => patch({ name: e.target.value })} placeholder="예: 토브넷 직무 인터뷰" aria-label="노드 이름" />
      <div className="flex flex-wrap items-center gap-2">
        <select className="input w-24 !py-1" value={node.kind} onChange={(e) => patch({ kind: e.target.value as SkillKind })} aria-label="분류">
          {KINDS.map((k) => <option key={k}>{k}</option>)}
        </select>
        <span className="flex items-center gap-1" role="radiogroup" aria-label="중요도">
          <span className="text-ink/60">중요도</span>
          {([1, 2, 3] as const).map((w) => (
            <button type="button" key={w} role="radio" aria-checked={node.weight === w} aria-label={`중요도 ${w}`} onClick={() => patch({ weight: w })}>
              <Star size={16} className={w <= node.weight ? "text-gold" : "text-ink/30"} fill={w <= node.weight ? "currentColor" : "none"} />
            </button>
          ))}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1">
        <span className="text-ink/60">먼저 할 노드</span>
        {node.prereq.map((q) => (
          <span key={q} className="chip border border-line px-2 py-0.5">
            {tree.find((o) => o.skill === q)?.name ?? q}
            <button type="button" aria-label="먼저 할 노드 빼기" onClick={() => patch({ prereq: node.prereq.filter((x) => x !== q) })}><X size={12} /></button>
          </span>
        ))}
        {candidates.length > 0 && (
          <select className="input w-auto max-w-full !py-0.5 text-xs" value="" onChange={(e) => e.target.value && patch({ prereq: [...node.prereq, e.target.value] })} aria-label="먼저 할 노드 추가">
            <option value="">+ 추가</option>
            {candidates.map((o) => <option key={o.skill} value={o.skill}>{o.name}</option>)}
          </select>
        )}
      </div>
      <input className="input !py-1" maxLength={LIMITS.note} value={node.note ?? ""} onChange={(e) => patch({ note: e.target.value })} placeholder="준비 팁·메모" aria-label="메모" />
      {full && <p className="text-danger">내 노드는 직무마다 {LIMITS.nodes}개까지 만들 수 있어요.</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn-gold !py-1 text-xs" disabled={!name || full}>{initial ? "저장" : "추가"}</button>
        <button type="button" className="btn-ghost !py-1 text-xs" onClick={onCancel}>취소</button>
      </div>
    </form>
  );
}
