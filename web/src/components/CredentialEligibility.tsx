"use client";
import type { TreeNode } from "@/lib/engine";
import type { Profile } from "@/lib/types";
import { credentialProfileKey } from "@/lib/credentialEligibility";
import { useStore } from "@/lib/store";

export function CredentialEligibility({ node }: { node: TreeNode }) {
  const { profile, setProfile } = useStore();
  const assessment = node.credentialEligibility;
  if (!profile || !assessment) return null;
  const facts = profile.credentialFacts?.[node.skill];
  const current = facts?.profileKey === credentialProfileKey(profile);
  function save(update: NonNullable<Profile["credentialFacts"]>[string]) {
    if (!profile) return;
    setProfile({ ...profile, credentialFacts: { ...profile.credentialFacts,
      [node.skill]: { ...facts, ...update, profileKey: credentialProfileKey(profile) } } });
  }
  return <div className="mt-3 space-y-2 rounded border border-line p-2 text-xs">
    <p className="font-bold">{assessment.label}</p>
    <p>{assessment.reason}</p>
    <a href={assessment.officialUrl} target="_blank" rel="noreferrer" className="block underline">시행기관 응시요건 확인</a>
    <p className="text-ink/60">공식 기준 확인일 {assessment.checkedAt}</p>
    {assessment.clinical && <label className="block">인정 기준에 맞는 임상심리 수련·실무 이력이 있나요?
      <select className="input mt-1" value={facts?.clinicalPractice ?? ""}
        onChange={e => save({ clinicalPractice: (e.target.value || undefined) as "training_year" | "work_two_years" | "none" | undefined, eligibility: undefined })}>
        <option value="">아직 확인하지 않았어요</option>
        <option value="training_year">실습수련 1년 이상</option>
        <option value="work_two_years">실무경력 2년 이상</option>
        <option value="none">아직 해당 이력이 없어요</option>
      </select>
    </label>}
    {node.skill !== "SK-SQLD" && <label className="block">이번 시험의 전체 응시요건을 확인했나요?
      <select className="input mt-1" value={current ? facts?.eligibility ?? "" : ""}
        onChange={e => save({ eligibility: (e.target.value || undefined) as "confirmed" | "not_met" | undefined })}>
        <option value="">미확인</option>
        <option value="confirmed">공식 기준으로 충족 확인 · 자기 보고</option>
        <option value="not_met">현재 충족하지 못해요</option>
      </select>
    </label>}
    <p>취득 완료는 실제 자격 취득 후 기록하세요. 접수 기간은 시행기관에서 확인할 수 있어요.</p>
  </div>;
}
