"use client";

import { Check, ChevronDown, ChevronRight, FileText, Lock } from "lucide-react";
import type { TreeNode } from "@/lib/engine";
import { EMPLOYMENT_SECTIONS, STARTUP_SECTIONS, employmentSection, startupSection, type TreeMode } from "@/lib/treeProgression";
import { questOutcome } from "@/lib/questOutcome";

export function StepsRoadmap({ tree, mode, selected, recommended, onPick }: {
  tree: TreeNode[];
  mode: TreeMode;
  selected: string | null;
  recommended?: string;
  onPick: (id: string) => void;
}) {
  const tasks = tree.filter(node => !node.groupChildren);
  const portfolios = tasks.filter(node => node.portfolioSources || node.skill === "SK-PORT");
  const portfolioIds = new Set(portfolios.map(node => node.skill));
  const completed = tasks.filter(node => node.state !== "none" && !portfolioIds.has(node.skill));
  const available = tasks.filter(node => node.state === "none" && !portfolioIds.has(node.skill));
  const groups = mode === "employment" ? EMPLOYMENT_SECTIONS.map(title => ({
    title, nodes: available.filter(node => employmentSection(node) === title),
  })) : STARTUP_SECTIONS.map(title => ({
    title, nodes: available.filter(node => startupSection(node) === title),
  }));

  function card(node: TreeNode) {
    const done = node.state !== "none";
    const status = done ? "완료" : node.locked ? "선행 과제 확인" : node.credentialEligibility?.label;
    return <button key={node.skill} type="button" aria-pressed={selected === node.skill}
      onClick={() => onPick(node.skill)}
      className={`group flex min-h-28 w-full flex-col rounded-xl border p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-go ${selected === node.skill ? "border-go bg-go/10" : "border-line bg-paper/40 hover:border-go/60 hover:bg-go/5"}`}>
      <span className="mb-3 flex min-h-4 items-center gap-2 text-[11px] font-semibold">
        {done ? <span className="flex items-center gap-1 text-ok"><Check size={12} />완료</span>
          : node.skill === recommended ? <span className="text-go">추천 퀘스트</span>
            : node.credentialPriority ? <span className="text-go">{node.credentialPriority.label}</span>
              : <span className="text-ink/50">{node.portfolioSources ? "대표 작업물 모으기" : "준비 전"}</span>}
        <ChevronRight size={14} className="ml-auto shrink-0 text-ink/40 group-hover:text-go" />
      </span>
      <span className="line-clamp-2 text-sm font-bold leading-relaxed">{questOutcome(node)?.title ?? node.name}</span>
      {status && !done && <span className="mt-3 flex items-center gap-1 text-xs text-ink/60">{node.locked && <Lock size={11} />}{status}</span>}
      {node.score && <span className="mt-2 text-xs text-ink/60">{node.score}</span>}
    </button>;
  }

  function grid(nodes: TreeNode[]) {
    return <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{nodes.map(card)}</div>;
  }

  return <div className="space-y-8 p-4 sm:p-6" aria-label="단계별 준비 로드맵">
    {groups.map(group => {
      const language = group.title === "공통 역량" && tree.find(node => node.groupChildren);
      const nodes = group.nodes.filter(node => !node.groupParent);
      const credentials = group.title === "직무 자격증";
      return <section key={group.title} className="space-y-4">
        <div className="flex items-center gap-3 border-b border-line pb-3">
          <h2 className="text-base font-bold">{group.title}</h2>
          <span className="text-xs text-ink/50">{group.nodes.length}개 준비 중</span>
        </div>
        {credentials ? <div className="space-y-4">
          {[1, 2, 3].map(rank => {
            const choices = nodes.filter(node => (node.credentialPriority?.rank ?? 2) === rank);
            if (!choices.length) return null;
            const title = rank === 1 ? "우선 검토" : rank === 2 ? "선택 준비" : "장기·심화 목표";
            return rank === 1 ? <div key={rank} className="space-y-3"><h3 className="text-sm font-semibold text-go">{title}</h3>{grid(choices)}</div>
              : <details key={rank} open={rank === 2 && !nodes.some(node => node.credentialPriority?.rank === 1)} className="rounded-xl border border-line p-4">
                <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold"><ChevronDown size={14} />{title}<span className="ml-auto text-xs font-normal text-ink/50">{choices.length}개</span></summary>
                <div className="mt-4">{grid(choices)}</div>
              </details>;
          })}
        </div> : <>
          {group.title === "프로젝트·포트폴리오" && <h3 className="text-sm font-semibold text-go">추천 프로젝트</h3>}
          {group.title === "공통 역량" ? <div className="space-y-3">{nodes.map(card)}</div> : grid(nodes)}
          {language && <details className="rounded-xl border border-line bg-paper/40 p-4">
            <summary className="flex cursor-pointer list-none items-center gap-2 font-bold text-sm"><ChevronDown size={14} />어학<span className="ml-auto text-xs font-normal text-ink/50">시험 선택</span></summary>
            <p className="mb-3 mt-2 text-xs text-ink/60">목표 직무와 공고에 맞는 시험을 선택하세요.</p>
            {grid(tree.filter(node => node.groupParent === language.skill))}
          </details>}
          {nodes.length === 0 && !language && <p className="text-sm text-ink/50">이 영역의 준비를 완료했어요.</p>}
        </>}
        {group.title === "프로젝트·포트폴리오" && portfolios.map(node => <div key={node.skill} className="mt-6 rounded-xl border border-go/40 bg-go/5 p-4">
          <h3 className="mb-2 flex items-center gap-2 font-bold"><FileText size={16} />포트폴리오 작성</h3>
          <p className="mb-3 text-xs text-ink/60">{node.portfolioSources ? `완료한 프로젝트 ${node.portfolioSources.filter(id => completed.some(item => item.skill === id)).length}개 중 대표 작업물을 골라 하나의 포트폴리오로 정리하세요.` : "대표 작업물을 골라 하나의 포트폴리오로 정리하세요."}</p>
          {card(node)}
        </div>)}
      </section>;
    })}
    {completed.length > 0 && <details className="rounded-xl border border-ok/30 p-4">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-bold"><Check size={15} className="text-ok" />완료한 준비<span className="ml-auto text-xs text-ink/50">{completed.length}개</span><ChevronDown size={14} /></summary>
      <div className="mt-4">{grid(completed)}</div>
    </details>}
  </div>;
}
