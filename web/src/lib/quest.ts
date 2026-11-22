import type { Opportunity } from "./types";

// 공고문 서류 줄을 체크리스트 항목으로 다듬는다: 번호·"(양식)" 표시를 떼고, 안내 문장(*·※로 시작)은 뺀다
function cleanDocs(docs: string[]) {
  const out: string[] = [];
  for (const raw of docs) {
    if (/^[*※]/.test(raw.trim())) continue;
    const d = raw
      .replace(/^\s*\d+[.)]\s*/, "")
      .replace(/^\(양식\)\s*/, "")
      .trim()
      .slice(0, 50);
    if (d.length > 1 && !out.includes(d)) out.push(d);
  }
  return out.slice(0, 6);
}

// 지원 퀘스트 체크리스트. "공식 신청처 이동"은 신청 완료가 아니라 이동 기록일 뿐이다.
export function questItems(o: Opportunity) {
  if (o.startup) return ['원문 확인', '지원 자격 확인',
    ...[...new Set(o.startup.requirements.filter((r) => r.necessity === 'required' && r.stage === 'application').map((r) => `${r.document_type} 준비`))],
    '공고별 선택·조건부 제출물 확인', '공식 신청처 이동'];
  const docs = cleanDocs(o.documents).map((d) => `${d} 준비`);
  if (o.type !== "창업지원") return ["원문 확인", "조건 점검", ...docs, "공식 신청처 이동"];
  // 창업지원: 사업계획서와 증빙이 준비의 중심이다(기획서 4.3). 공고문에 서류 목록이 있으면 그것을 따른다
  const hasPlan = docs.some((d) => d.includes("사업계획서"));
  return [
    "원문 확인",
    "조건 점검",
    "사업 아이템을 한 문장으로 정리",
    ...(hasPlan ? [] : ["사업계획서 초안 작성"]),
    ...(docs.length ? docs : ["증빙 서류 확인 (공고문 기준: 사업자등록증·재학증명서 등)"]),
    "공식 신청처 이동",
  ];
}

export function questProgress(o: Opportunity, state: Record<string, boolean> | undefined) {
  const items = questItems(o);
  const done = items.filter((i) => state?.[i]).length;
  return { items, done, total: items.length };
}
