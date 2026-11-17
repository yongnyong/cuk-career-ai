"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ClipboardCheck, Loader2, Sparkles } from "lucide-react";
import { COLLEGES, DEPARTMENTS, DEPARTMENT_SOURCE, getDepartment } from "@/lib/data/departments";
import { jobById } from "@/lib/data/catalog";
import { diagnosisItems, gradeStage, jobsFor, matchJobs } from "@/lib/engine";
import { useStore } from "@/lib/store";
import { useMounted } from "@/lib/useMounted";
import type { Profile, SkillState } from "@/lib/types";

const STEPS = ["기본 정보", "보유 역량 진단", "목표", "준비 시간"];
const YEARS = Array.from({ length: 12 }, (_, i) => 2026 - i);

const blank: Profile = {
  pseudoId: "",
  admissionYear: 2026,
  campus: "성심",
  departmentId: "",
  grade: 1,
  status: "재학",
  jobId: "",
  interests: [],
  weeklyHours: 5,
  targetTerm: "2027 하계",
  skills: {},
  createdAt: "",
};

function Form({ start }: { start: Profile }) {
  const { session, setProfile } = useStore();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [college, setCollege] = useState("");
  const [f, setF] = useState<Profile>(start);

  const dept = getDepartment(f.departmentId);
  const maxGrade = dept && ["medicine", "pharmacy"].includes(dept.field) ? 6 : 4;
  const stage = gradeStage(f.grade);
  const groups = useMemo(() => (f.departmentId ? diagnosisItems(f.departmentId, f.grade) : []), [f.departmentId, f.grade]);
  const matches = useMemo(() => matchJobs(f.skills, f.departmentId), [f.skills, f.departmentId]);
  const heldCount = Object.values(f.skills).filter((x) => x !== "none").length;
  const job = jobById(f.jobId);
  const canNext = [!!f.departmentId, true, !!f.jobId, true][step];

  const toggle = (skill: string) => {
    const next: Record<string, SkillState> = { ...f.skills };
    if ((next[skill] ?? "none") === "none") next[skill] = "self";
    else delete next[skill];
    setF({ ...f, skills: next });
  };

  const finish = () => {
    setLoading(true);
    // 서버 연결 시: POST /api/profile → Gemini가 경로 설명 생성(노드는 직무 그래프 내 ID만 허용)
    setTimeout(() => {
      setProfile({ ...f, pseudoId: session ?? f.pseudoId, createdAt: f.createdAt || new Date().toISOString() });
      router.push("/tree");
    }, 1200);
  };

  if (loading)
    return (
      <div className="card mx-auto mt-10 max-w-md p-10 text-center">
        <Loader2 className="mx-auto animate-spin text-accent" size={32} />
        <p className="mt-4 font-medium">AI가 경로 초안을 만들고 있어요</p>
        <p className="mt-1 text-sm text-slate-500">목표 직무의 역량 그래프에서 노드를 고르고, 지금 열린 공고를 연결하는 중…</p>
      </div>
    );

  return (
    <div className="mx-auto max-w-3xl">
      <div className="card p-6">
        <ol className="mb-6 flex gap-2 text-xs">
          {STEPS.map((s, i) => (
            <li key={s} className={`flex-1 rounded-full py-1 text-center ${i <= step ? "bg-navy text-white" : "bg-slate-100 text-slate-500"}`}>
              {i + 1}. {s}
            </li>
          ))}
        </ol>

        {step === 0 && (
          <div className="space-y-4">
            <h1 className="text-xl font-bold">{session}님, 기본 정보를 알려 주세요</h1>
            <p className="text-sm text-slate-500">
              학과와 학년에 맞춰 체크할 항목을 골라 드려요. 학번은 입학년도만 받고, 개인을 알아볼 수 있는 학번 전체·이름·연락처는 받지 않아요.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                대학·계열
                <select
                  className="input mt-1"
                  value={college}
                  onChange={(e) => {
                    setCollege(e.target.value);
                    setF({ ...f, departmentId: "" });
                  }}
                >
                  <option value="">전체</option>
                  {COLLEGES.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                학과
                <select
                  className="input mt-1"
                  value={f.departmentId}
                  onChange={(e) => {
                    const d = getDepartment(e.target.value);
                    setF({ ...f, departmentId: e.target.value, campus: d?.campus ?? "성심" });
                  }}
                >
                  <option value="">선택하세요</option>
                  {DEPARTMENTS.filter((d) => !college || d.college === college).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.campus}교정)
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                학년
                <select className="input mt-1" value={f.grade} onChange={(e) => setF({ ...f, grade: +e.target.value })}>
                  {Array.from({ length: maxGrade }, (_, i) => i + 1).map((g) => (
                    <option key={g} value={g}>
                      {g}학년
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                학번 (입학년도)
                <select className="input mt-1" value={f.admissionYear} onChange={(e) => setF({ ...f, admissionYear: +e.target.value })}>
                  {YEARS.map((y) => (
                    <option key={y} value={y}>
                      {String(y).slice(2)}학번 ({y}년 입학)
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                학적
                <select className="input mt-1" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value as Profile["status"] })}>
                  <option>재학</option>
                  <option>휴학</option>
                  <option>졸업예정</option>
                </select>
              </label>
            </div>
            <p className="text-xs text-slate-400">
              학과·학년·학적은 본인이 입력한 값이며 학교 시스템으로 확인한 정보가 아니에요. 학과 목록 출처:{" "}
              <a href={DEPARTMENT_SOURCE.url} target="_blank" rel="noreferrer" className="underline">
                {DEPARTMENT_SOURCE.label}
              </a>{" "}
              ({DEPARTMENT_SOURCE.checkedAt} 확인)
            </p>
          </div>
        )}

        {step === 1 && dept && (
          <div className="space-y-4">
            <h1 className="flex items-center gap-2 text-xl font-bold">
              <ClipboardCheck className="text-accent" size={22} /> 지금 가지고 있는 것을 체크해 주세요
            </h1>
            <div className="rounded-lg bg-navy/5 px-4 py-3 text-sm">
              <b>
                {dept.name} {f.grade}학년 · {stage.stage} 단계
              </b>
              <p className="text-slate-600">{stage.tip}</p>
            </div>
            <p className="text-sm text-slate-500">
              {dept.name} 학생이 많이 준비하는 항목을 골랐어요. 체크한 항목은 &lsquo;자기 보고&rsquo;로 저장되고, 점수·증빙 파일은 받지 않아요.
            </p>
            {groups.map((g) => (
              <section key={g.kind}>
                <h2 className="mb-1.5 flex items-center gap-2 text-sm font-bold">
                  {g.kind}
                  {g.focus && <span className="chip bg-accent/15 text-accent">{f.grade}학년에 챙기면 좋아요</span>}
                </h2>
                <div className="flex flex-wrap gap-1.5">
                  {g.skills.map((sk) => {
                    const on = (f.skills[sk.id] ?? "none") !== "none";
                    return (
                      <button
                        key={sk.id}
                        type="button"
                        aria-pressed={on}
                        onClick={() => toggle(sk.id)}
                        className={`rounded-full border px-3 py-1.5 text-sm transition ${
                          on ? "border-edge bg-navy text-white" : "border-slate-300 bg-panel text-slate-700 hover:border-slate-500"
                        }`}
                      >
                        {on ? "✓ " : ""}
                        {sk.name}
                      </button>
                    );
                  })}
                </div>
              </section>
            ))}
            <p className="rounded-lg bg-paper px-4 py-2 text-sm">
              체크한 항목 <b>{heldCount}개</b>
              {heldCount === 0 && " — 아직 없어도 괜찮아요. 다음 단계에서 시작할 경로를 골라요."}
            </p>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <h1 className="text-xl font-bold">어떤 일을 해 보고 싶나요?</h1>
            <p className="text-sm text-slate-500">
              학과 홈페이지의 진로 안내를 바탕으로 만든 &lsquo;학과 테크&rsquo;가 있으면 먼저 보여드려요. 전공은 출발점일 뿐이라 어떤 직무든 고를 수 있어요.
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {matches.map((m) => (
                <button
                  key={m.job.id}
                  onClick={() => setF({ ...f, jobId: m.job.id, interests: f.interests.filter((x) => x !== m.job.id) })}
                  className={`rounded-lg border p-3 text-left text-sm transition ${
                    f.jobId === m.job.id ? "border-edge bg-navy/5 ring-2 ring-navy/20" : "border-slate-200 hover:border-slate-400"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-1.5 font-medium">
                    {m.job.name}
                    {m.own && <span className="chip bg-gold text-on-gold">학과 테크</span>}
                    {m.major && <span className="chip bg-accent/15 text-accent">전공 연계</span>}
                    {m.have > 0 && (
                      <span className="chip bg-emerald-100 text-emerald-700">
                        보유 {m.have}/{m.total}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500">{m.job.summary}</div>
                </button>
              ))}
            </div>
            {job && (
              <div>
                <p className="mb-2 text-sm font-medium">함께 관심 있는 분야 (선택)</p>
                <div className="flex flex-wrap gap-1.5">
                  {jobsFor(f.departmentId).filter((j) => j.id !== f.jobId).map((j) => {
                    const on = f.interests.includes(j.id);
                    return (
                      <button
                        key={j.id}
                        onClick={() => setF({ ...f, interests: on ? f.interests.filter((x) => x !== j.id) : [...f.interests, j.id] })}
                        className={`chip border ${on ? "border-edge bg-navy text-white" : "border-slate-300 bg-panel text-slate-600"}`}
                      >
                        {j.name}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <h1 className="text-xl font-bold">얼마나, 언제까지 준비할까요?</h1>
            <label className="block text-sm">
              주당 준비 시간: <b>{f.weeklyHours}시간</b>
              <input
                type="range"
                min={1}
                max={20}
                value={f.weeklyHours}
                onChange={(e) => setF({ ...f, weeklyHours: +e.target.value })}
                className="mt-2 w-full accent-[#1d2b48]"
              />
            </label>
            <label className="block text-sm">
              희망 시기
              <select className="input mt-1" value={f.targetTerm} onChange={(e) => setF({ ...f, targetTerm: e.target.value })}>
                {["2027 동계", "2027 하계", "2027 동계 이후", "졸업 후"].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
          </div>
        )}

        <div className="mt-6 flex justify-between">
          <button className="btn-ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>
            이전
          </button>
          {step < 3 ? (
            <button className="btn-primary" disabled={!canNext} onClick={() => setStep(step + 1)}>
              {step === 0 ? "보유 역량 진단하기" : "다음"}
            </button>
          ) : (
            <button className="btn bg-accent text-white" onClick={finish}>
              <Sparkles size={16} /> AI 경로 만들기
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Onboarding() {
  const { session, profile, ready } = useStore();
  const router = useRouter();
  const mounted = useMounted();
  useEffect(() => {
    if (ready && !session) router.replace("/signup");
  }, [ready, session, router]);
  if (!mounted || !ready || !session) return null;
  // 기존 프로필이 있으면 그 값에서 시작(다시 설정)
  return <Form key={session} start={profile ?? blank} />;
}
