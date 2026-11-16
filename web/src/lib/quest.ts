import type { Opportunity } from "./types";

// 지원 퀘스트 체크리스트. "공식 신청처 이동"은 신청 완료가 아니라 이동 기록일 뿐이다.
export function questItems(o: Opportunity) {
  return ["원문 확인", "조건 점검", ...o.documents.map((d) => `${d} 준비`), "공식 신청처 이동"];
}

export function questProgress(o: Opportunity, state: Record<string, boolean> | undefined) {
  const items = questItems(o);
  const done = items.filter((i) => state?.[i]).length;
  return { items, done, total: items.length };
}
