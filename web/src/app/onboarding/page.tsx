"use client";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles, UserRound } from "lucide-react";
import { COLLEGES, DEPARTMENTS, DEPARTMENT_SOURCE, getDepartment } from "@/lib/data/departments";
import { JOBS, jobById, skillById } from "@/lib/data/catalog";
import { suggestJobs } from "@/lib/engine";
import { useStore } from "@/lib/store";
import type { Profile, SkillState } from "@/lib/types";

const STEPS = ["소속", "목표", "현재 역량", "준비 시간"];

// 시연용 페르소나 (기획서 4.8 스토리보드)
const PERSONAS: { label: string; desc: string; p: Partial<Profile> }[] = [
  {
    label: "민지",
    desc: "인공지능학과 3학년 · AI 엔지니어",
    p: { departmentId: "ai", grade: 3, status: "재학", jobId: "ai-engineer", skills: { "SK-PY-01": "verified", "SK-DA": "self" } },
  },
  {
    label: "서연",
    desc: "프랑스어문화학과 2학년 · 문화 창업",
    p: { departmentId: "french", grade: 2, status: "재학", jobId: "founder", interests: ["content-planner"], skills: { "SK-IDEA": "self" } },
  },
  {
    label: "도윤",
    desc: "영어영문학부 3학년 · 해외영업",
    p: { departmentId: "english", grade: 3, status: "재학", jobId: "overseas-sales", interests: ["marketer"], skills: { "SK-TOEIC": "verified" } },
  },
];

const newId = () => "U-" + Math.random().toString(36).slice(2, 8).toUpperCase();

export default function Onboarding() {
  const { setProfile } = useStore();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [college, setCollege] = useState("");
  const [f, setF] = useState<Profile>({
    pseudoId: "",
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
  });

  const dept = getDepartment(f.departmentId);
  const maxGrade = dept && ["medicine", "pharmacy"].includes(dept.field) ? 6 : 4;
  const jobs = useMemo(() => (f.departmentId ? suggestJobs(f.departmentId) : JOBS), [f.departmentId]);
  const recommendedIds = new Set(dept ? JOBS.filter((j) => j.fields.includes(dept.field)).map((j) => j.id) : []);
  const job = jobById(f.jobId);

  const canNext = [!!f.departmentId, !!f.jobId, true, true][step];

  const finish = (p: Profile) => {
    setLoading(true);
    // 서버 연결 시: POST /api/profile → Gemini가 경로 설명 생성(노드는 직무 그래프 내 ID만 허용)
    setTimeout(() => {
      setProfile({ ...p, pseudoId: newId(), createdAt: new Date().toISOString() });
      router.push("/tree");
    }, 1200);
  };

  const startPersona = (pp: Partial<Profile>) =>
    finish({ ...f, interests: [], ...pp, campus: getDepartment(pp.departmentId!)!.campus } as Profile);

  if (loading)
    return (
      <div className="card mx-auto mt-10 max-w-md p-10 text-center">
        <Loader2 className="mx-auto animate-spin text-accent" size={32} />
        <p className="mt-4 font-medium">AI가 경로 초안을 만들고 있어요</p>
        <p className="mt-1 text-sm text-slate-500">목표 직무의 역량 그래프에서 노드를 고르고, 지금 열린 공고를 연결하는 중…</p>
      </div>
    );

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="card flex flex-wrap items-center gap-2 p-4 text-sm">
        <UserRound size={16} className="text-slate-500" />
        <span className="text-slate-600">시연용 빠른 시작:</span>
        {PERSONAS.map((x) => (
          <button key={x.label} className="btn-ghost !py-1" onClick={() => startPersona(x.p)} title={x.desc}>
            {x.label} <span className="text-xs text-slate-400">{x.desc}</span>
          </button>
        ))}
      </div>

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
            <h1 className="text-xl font-bold">어느 학과에서 출발하나요?</h1>
            <p className="text-sm text-slate-500">전공은 출발점일 뿐, 진로의 한계가 아니에요. 이름·학번·연락처는 받지 않아요.</p>
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
                    setF({ ...f, departmentId: e.target.value, campus: d?.campus ?? "성심", jobId: "" });
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
                학적
                <select className="input mt-1" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value as Profile["status"] })}>
                  <option>재학</option>
                  <option>휴학</option>
                  <option>졸업예정</option>
                </select>
              </label>
            </div>
            <p className="text-xs text-slate-400">
              학과 목록 출처:{" "}
              <a href={DEPARTMENT_SOURCE.url} target="_blank" rel="noreferrer" className="underline">
                {DEPARTMENT_SOURCE.label}
              </a>{" "}
              ({DEPARTMENT_SOURCE.checkedAt} 확인)
            </p>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <h1 className="text-xl font-bold">어떤 일을 해 보고 싶나요?</h1>
            <p className="text-sm text-slate-500">
              <span className="chip bg-accent/15 text-accent">전공 연계</span> 표시는 {dept?.name} 학생에게 먼저 보여 주는 직무예요. 다른 직무도
              자유롭게 고를 수 있어요.
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {jobs.map((j) => (
                <button
                  key={j.id}
                  onClick={() => setF({ ...f, jobId: j.id, interests: f.interests.filter((x) => x !== j.id) })}
                  className={`rounded-lg border p-3 text-left text-sm transition ${f.jobId === j.id ? "border-navy bg-navy/5 ring-2 ring-navy/20" : "border-slate-200 hover:border-slate-400"}`}
                >
                  <div className="flex items-center gap-2 font-medium">
                    {j.name}
                    {recommendedIds.has(j.id) && <span className="chip bg-accent/15 text-accent">전공 연계</span>}
                  </div>
                  <div className="text-xs text-slate-500">{j.summary}</div>
                </button>
              ))}
            </div>
            {f.jobId && (
              <div>
                <p className="mb-2 text-sm font-medium">함께 관심 있는 분야 (선택)</p>
                <div className="flex flex-wrap gap-1.5">
                  {JOBS.filter((j) => j.id !== f.jobId).map((j) => {
                    const on = f.interests.includes(j.id);
                    return (
                      <button
                        key={j.id}
                        onClick={() => setF({ ...f, interests: on ? f.interests.filter((x) => x !== j.id) : [...f.interests, j.id] })}
                        className={`chip border ${on ? "border-navy bg-navy text-white" : "border-slate-300 bg-white text-slate-600"}`}
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

        {step === 2 && job && (
          <div className="space-y-4">
            <h1 className="text-xl font-bold">{job.name} 경로에서 이미 해 둔 것이 있나요?</h1>
            <p className="text-sm text-slate-500">
              여기서 체크한 항목은 &lsquo;자기 보고&rsquo;로 표시돼요. 어학 점수·자격증은 내 정보에서 증빙을 확인하면 &lsquo;검증됨&rsquo;으로
              바뀌어요.
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {job.nodes.map((n) => {
                const sk = skillById(n.skill)!;
                const on = (f.skills[n.skill] ?? "none") !== "none";
                return (
                  <label key={n.skill} className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm ${on ? "border-navy bg-navy/5" : "border-slate-200"}`}>
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => {
                        const next: Record<string, SkillState> = { ...f.skills };
                        if (on) delete next[n.skill];
                        else next[n.skill] = "self";
                        setF({ ...f, skills: next });
                      }}
                    />
                    <span>
                      {sk.name}
                      <span className="ml-1 text-xs text-slate-400">
                        {sk.kind}
                        {n.required ? " · 필수" : " · 선택"}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
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
              다음
            </button>
          ) : (
            <button className="btn bg-accent text-white" onClick={() => finish(f)}>
              <Sparkles size={16} /> AI 경로 만들기
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
