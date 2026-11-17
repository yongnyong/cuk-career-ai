"use client";
import { useMemo, useState } from "react";
import { Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import { useStore } from "@/lib/store";
import { jobsFor, type TreeNode } from "@/lib/engine";
import { SKILLS, isBaseJob, sanitizeJob, skillById } from "@/lib/data/catalog";
import { DEPARTMENTS } from "@/lib/data/departments";
import type { Job, Skill, SkillKind } from "@/lib/types";
import { Legend, NodeBox } from "./quest-ui";

const KINDS: SkillKind[] = ["교육", "경험", "프로젝트", "자격증", "어학", "역량"];
const newId = (prefix: string) => `${prefix}-${Date.now().toString(36)}`;

// 학생이 처음 보는 모습 그대로(아무것도 완료하지 않은 상태) 그린다
function Preview({ job, nameOf }: { job: Job; nameOf: (id: string) => Skill | undefined }) {
  const rows = useMemo(() => {
    const depth = new Map<string, number>();
    const depthOf = (id: string): number => {
      if (depth.has(id)) return depth.get(id)!;
      const n = job.nodes.find((x) => x.skill === id);
      const d = n?.prereq?.length ? Math.max(...n.prereq.map(depthOf)) + 1 : 0;
      depth.set(id, d);
      return d;
    };
    const out: TreeNode[][] = [];
    for (const n of job.nodes) {
      const sk = nameOf(n.skill);
      (out[depthOf(n.skill)] ??= []).push({
        skill: n.skill,
        name: sk?.name ?? n.skill,
        kind: sk?.kind ?? "",
        required: n.required,
        prereq: n.prereq ?? [],
        depth: depthOf(n.skill),
        state: "none",
        locked: (n.prereq ?? []).length > 0,
        opportunities: [],
      });
    }
    return out;
  }, [job, nameOf]);
  const now = useMemo(() => new Date(0), []);
  if (!job.nodes.length) return <p className="p-4 text-sm text-slate-500">노드가 없어요. 아래에서 노드를 추가하세요.</p>;
  return (
    <div className="space-y-3 overflow-x-auto bg-paper p-4">
      {rows.map((row, i) => (
        <div key={i} className="flex justify-center gap-3">
          {row?.map((n) => <NodeBox key={n.skill} node={n} now={now} />)}
        </div>
      ))}
    </div>
  );
}

export function TrackEditor() {
  const { isAdmin, catalog, catalogVersion, saveCatalog } = useStore();
  const [dept, setDept] = useState("psychology");
  const [draft, setDraft] = useState<Job | null>(null);
  const [skills, setSkills] = useState<Record<string, Skill>>({}); // 이번 편집에서 고치거나 새로 만든 스킬
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const jobs = useMemo(() => jobsFor(dept), [dept, catalogVersion]);
  const nameOf = useMemo(() => (id: string) => skills[id] ?? skillById(id), [skills]);

  const open = (job: Job) => {
    setDraft(structuredClone(job));
    setSkills({});
    setMsg("");
  };
  const patchNode = (id: string, patch: Partial<Job["nodes"][number]>) =>
    setDraft((d) => d && { ...d, nodes: d.nodes.map((n) => (n.skill === id ? { ...n, ...patch } : n)) });
  const patchSkill = (id: string, patch: Partial<Skill>) => setSkills((s) => ({ ...s, [id]: { ...nameOf(id)!, ...patch } }));
  const addNode = (id: string) => setDraft((d) => d && { ...d, nodes: [...d.nodes, { skill: id, required: false, prereq: [] }] });

  const save = async () => {
    if (!draft) return;
    if (!draft.name.trim()) return setMsg("테크 이름을 입력해 주세요.");
    if (Object.values(skills).some((s) => !s.name.trim())) return setMsg("이름이 빈 노드가 있어요.");
    setBusy(true);
    const allSkills = { ...catalog.skills, ...skills };
    const known = new Set([...SKILLS.map((s) => s.id), ...Object.keys(allSkills)]);
    const err = await saveCatalog({ skills: allSkills, jobs: { ...catalog.jobs, [draft.id]: sanitizeJob(draft, known) } });
    setBusy(false);
    setMsg(err ?? "저장했어요. 학생 화면에 바로 반영돼요.");
    if (!err) setSkills({});
  };
  const reset = async () => {
    if (!draft) return;
    const rest = Object.fromEntries(Object.entries(catalog.jobs).filter(([id]) => id !== draft.id));
    setBusy(true);
    const err = await saveCatalog({ skills: catalog.skills, jobs: rest });
    setBusy(false);
    setMsg(err ?? (isBaseJob(draft.id) ? "처음 상태로 되돌렸어요." : "이 테크를 삭제했어요."));
    if (!err) setDraft(null);
  };

  const others = SKILLS.filter((s) => draft && !draft.nodes.some((n) => n.skill === s.id));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <select className="input sm:w-64" value={dept} onChange={(e) => (setDept(e.target.value), setDraft(null))} aria-label="학과 선택">
          {DEPARTMENTS.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        {isAdmin && (
          <button
            className="btn-ghost"
            onClick={() => open({ id: newId("adm"), name: "새 테크", summary: "", fields: [], departments: [dept], nodes: [] })}
          >
            <Plus size={14} /> 이 학과에 새 테크
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {jobs.map((j) => (
          <button
            key={j.id}
            onClick={() => open(j)}
            className={`chip border px-2.5 py-1 ${draft?.id === j.id ? "border-edge bg-navy text-white" : "border-slate-300 bg-panel text-slate-600"}`}
          >
            {j.name}
            {j.departments && " ★"}
            {catalog.jobs[j.id] && " (수정됨)"}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-500">★ 학과 테크 · 테크를 누르면 학생이 보는 스킬트리와 편집 칸이 열려요.</p>

      {draft && (
        <div className="space-y-4">
          <div className="window overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-edge bg-navy px-4 py-2 text-sm text-white">
              <span className="font-bold">{draft.name || "(이름 없음)"} — 학생 화면 미리보기</span>
              <span className="text-white/70">{draft.summary}</span>
            </div>
            <Preview job={draft} nameOf={nameOf} />
            <div className="border-t border-edge px-4 py-2">
              <Legend />
            </div>
          </div>

          <fieldset disabled={!isAdmin || busy} className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-[1fr_2fr]">
              <input className="input" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} aria-label="테크 이름" placeholder="테크 이름" />
              <input className="input" value={draft.summary} onChange={(e) => setDraft({ ...draft, summary: e.target.value })} aria-label="한 줄 설명" placeholder="한 줄 설명" />
            </div>

            <ul className="divide-y divide-line rounded-md border border-line">
              {draft.nodes.map((n) => {
                const sk = nameOf(n.skill);
                return (
                  <li key={n.skill} className="space-y-2 p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <input className="input min-w-40 flex-1" value={sk?.name ?? ""} onChange={(e) => patchSkill(n.skill, { name: e.target.value })} aria-label="노드 이름" />
                      <select className="input w-28" value={sk?.kind ?? "역량"} onChange={(e) => patchSkill(n.skill, { kind: e.target.value as SkillKind })} aria-label="종류">
                        {KINDS.map((k) => (
                          <option key={k}>{k}</option>
                        ))}
                      </select>
                      <label className="flex items-center gap-1 text-xs">
                        <input type="checkbox" checked={n.required} onChange={(e) => patchNode(n.skill, { required: e.target.checked })} /> 필수
                      </label>
                      <button
                        className="btn-ghost !px-2 !py-1 text-danger"
                        aria-label={`${sk?.name} 노드 빼기`}
                        onClick={() =>
                          setDraft({
                            ...draft,
                            nodes: draft.nodes.filter((x) => x.skill !== n.skill).map((x) => ({ ...x, prereq: (x.prereq ?? []).filter((q) => q !== n.skill) })),
                          })
                        }
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                    <div className="flex flex-wrap items-center gap-1 text-xs text-slate-500">
                      먼저 해야 하는 노드:
                      {draft.nodes
                        .filter((x) => x.skill !== n.skill)
                        .map((x) => {
                          const on = (n.prereq ?? []).includes(x.skill);
                          return (
                            <button
                              key={x.skill}
                              type="button"
                              onClick={() => patchNode(n.skill, { prereq: on ? n.prereq!.filter((q) => q !== x.skill) : [...(n.prereq ?? []), x.skill] })}
                              className={`chip border ${on ? "border-edge bg-navy text-white" : "border-slate-300 text-slate-500"}`}
                            >
                              {nameOf(x.skill)?.name}
                            </button>
                          );
                        })}
                      {draft.nodes.length < 2 && "없음"}
                    </div>
                  </li>
                );
              })}
            </ul>

            {isAdmin && (
              <div className="flex flex-wrap items-center gap-2">
                <select className="input sm:w-72" value="" onChange={(e) => e.target.value && addNode(e.target.value)} aria-label="기존 노드 추가">
                  <option value="">+ 기존 노드에서 골라 추가</option>
                  {others.map((s) => (
                    <option key={s.id} value={s.id}>
                      [{s.kind}] {s.name}
                    </option>
                  ))}
                </select>
                <button
                  className="btn-ghost"
                  onClick={() => {
                    const id = newId("ADM");
                    setSkills((s) => ({ ...s, [id]: { id, name: "새 노드", kind: "교육", verifiable: false } }));
                    addNode(id);
                  }}
                >
                  <Plus size={14} /> 새 노드 만들기
                </button>
              </div>
            )}

            {isAdmin ? (
              <div className="flex flex-wrap items-center gap-2">
                <button className="btn-primary" onClick={save}>
                  <Save size={16} /> 저장
                </button>
                {(catalog.jobs[draft.id] || !isBaseJob(draft.id)) && (
                  <button className="btn-ghost" onClick={reset}>
                    <RotateCcw size={14} /> {isBaseJob(draft.id) ? "처음 상태로 되돌리기" : "이 테크 삭제"}
                  </button>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-500">수정은 관리자 계정으로 로그인하면 할 수 있어요.</p>
            )}
          </fieldset>
          {msg && (
            <p className="text-sm font-semibold" role="status">
              {msg}
            </p>
          )}
          <p className="text-xs text-slate-500">
            노드 이름을 고치면 그 노드를 쓰는 다른 테크에도 같이 바뀌어요. 서로를 먼저 요구하는 순환 관계는 저장할 때 자동으로 풀려요.
          </p>
        </div>
      )}
    </div>
  );
}
