"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";
import type { OpportunityExplanation } from "@/lib/types";

export function OpportunityReason({ id }: { id: string }) {
  const { session, opportunitySearch, explainOpportunity } = useStore();
  const key = JSON.stringify([session, opportunitySearch.query, id]);
  const [saved, setSaved] = useState<{ key: string; result: OpportunityExplanation | null }>();
  const [busy, setBusy] = useState(false);
  const result = saved?.key === key ? saved.result : undefined;
  const load = async () => {
    setBusy(true);
    const response = await explainOpportunity(id);
    setSaved({ key, result: response });
    setBusy(false);
  };
  return <div className="mt-3 space-y-2">
    <button className="btn-ghost text-sm" disabled={busy} onClick={() => void load()}>
      {busy ? "공고 근거를 확인하는 중…" : "내 목표와 연결되는 근거 보기"}
    </button>
    {result === null && <p role="alert" className="text-sm text-danger">근거를 읽지 못했어요. 다시 시도해 주세요.</p>}
    {result && result.items.length === 0 && <p className="text-sm">공고가 변경됐거나 확인할 원문이 부족해요. 원문을 확인해 주세요.</p>}
    {result?.items.filter(item => item.postingId === id).map(item => <div key={item.postingId} className="space-y-2 text-sm">
      {([["목표와 연결되는 근거", item.related], ["확인할 원문", item.checks]] as const).map(([title, sources]) =>
        sources.length > 0 && <div key={title}>
          <p className="font-semibold">{title}</p>
          {sources.map(source => <blockquote key={source.sectionId} className="mt-1 border-l-2 border-line pl-3">
            <p className="text-xs text-ink/60">{source.sectionId.startsWith("title:") ? "공고 제목" : "공고 원문"}</p>
            <p className="whitespace-pre-line">{source.quote}</p>
            <a href={source.sourceUrl} target="_blank" rel="noreferrer" className="text-xs underline">원문 확인 · 버전 {source.version}</a>
          </blockquote>)}
        </div>)}
    </div>)}
  </div>;
}

