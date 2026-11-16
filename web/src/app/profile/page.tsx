"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Award, BadgeCheck, Trash2 } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { useStore } from "@/lib/store";
import { progress } from "@/lib/engine";
import { jobById, skillById } from "@/lib/data/catalog";
import { getDepartment } from "@/lib/data/departments";
import { questProgress } from "@/lib/quest";

function Body() {
  const s = useStore();
  const router = useRouter();
  const p = s.profile!;
  const job = jobById(p.jobId)!;
  const dept = getDepartment(p.departmentId);
  const prog = progress(p);
  const held = Object.entries(p.skills).filter(([, st]) => st !== "none");
  const questBadges = s.followed
    .map((id) => s.opportunities.find((o) => o.id === id))
    .filter((o) => o && questProgress(o, s.quests[o.id]).done === questProgress(o, s.quests[o.id]).total);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="card p-5">
        <h1 className="text-xl font-bold">내 정보</h1>
        <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm sm:grid-cols-3">
          {[
            ["가명 ID", p.pseudoId],
            ["소속", `${dept?.college} ${dept?.name}`],
            ["학년·학적", `${p.grade}학년 · ${p.status}`],
            ["목표 직무", job.name],
            ["주당 준비", `${p.weeklyHours}시간`],
            ["희망 시기", p.targetTerm],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs text-slate-500">{k}</dt>
              <dd className="font-medium">{v}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-3 flex items-center gap-3">
          <span className="font-bold text-navy">Lv.{prog.level}</span>
          <div className="h-2 flex-1 rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-navy" style={{ width: `${prog.pct}%` }} />
          </div>
          <span className="text-xs text-slate-500">EXP {prog.pct}%</span>
        </div>
        <Link href="/onboarding" className="btn-ghost mt-4">
          목표·소속 다시 설정
        </Link>
      </div>

      <div className="card p-5">
        <h2 className="font-bold">보유 역량</h2>
        <p className="text-xs text-slate-500">
          자기 보고와 검증된 자격을 구분해요. 시연에서는 증빙 확인을 버튼으로 대신하며, 증빙 파일·점수는 저장하지 않아요.
        </p>
        <ul className="mt-3 space-y-2">
          {held.length === 0 && <li className="text-sm text-slate-500">아직 완료한 노드가 없어요.</li>}
          {held.map(([id, st]) => {
            const sk = skillById(id);
            if (!sk) return null;
            return (
              <li key={id} className="flex flex-wrap items-center gap-2 rounded-lg bg-paper px-3 py-2 text-sm">
                <span className="font-medium">{sk.name}</span>
                <span className="text-xs text-slate-400">{sk.kind}</span>
                {st === "verified" ? (
                  <span className="chip bg-emerald-100 text-emerald-700">
                    <BadgeCheck size={12} /> 검증됨
                  </span>
                ) : (
                  <span className="chip bg-slate-200 text-slate-600">자기 보고</span>
                )}
                {sk.verifiable && (
                  <button
                    className="btn-ghost ml-auto !py-1 text-xs"
                    onClick={() => s.setSkill(id, st === "verified" ? "self" : "verified")}
                  >
                    {st === "verified" ? "검증 해제" : "증빙 확인(시연)"}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="card p-5">
        <h2 className="flex items-center gap-1.5 font-bold">
          <Award size={16} className="text-accent" /> 배지
        </h2>
        <p className="text-xs text-slate-500">경쟁이 아닌 성장 기록이에요. 공개 순위와 연속 접속 보상은 없어요.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {held.length > 0 && <span className="chip bg-navy px-3 py-1 text-white">첫 노드 완료</span>}
          {s.followed.length > 0 && <span className="chip bg-navy px-3 py-1 text-white">첫 지원 퀘스트 시작</span>}
          {questBadges.map((o) => (
            <span key={o!.id} className="chip bg-accent px-3 py-1 text-white">
              서류 점검 완료 · {o!.title}
            </span>
          ))}
          {held.length === 0 && s.followed.length === 0 && <span className="text-sm text-slate-500">아직 배지가 없어요.</span>}
        </div>
        <p className="mt-2 text-xs text-slate-400">배지는 능력 점수가 아니라 확인한 준비 행동을 뜻해요.</p>
      </div>

      <div className="card border-red-200 p-5">
        <h2 className="font-bold text-danger">내 데이터 삭제</h2>
        <p className="mt-1 text-sm text-slate-600">프로필·퀘스트·알림 기록을 모두 지워요. 되돌릴 수 없어요.</p>
        <button
          className="btn mt-3 bg-danger text-white"
          onClick={() => {
            if (confirm("프로필과 모든 기록을 삭제할까요? 되돌릴 수 없어요.")) {
              s.deleteMyData();
              router.push("/");
            }
          }}
        >
          <Trash2 size={16} /> 모두 삭제
        </button>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <RequireProfile>
      <Body />
    </RequireProfile>
  );
}
