"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowUpRight, BellPlus, BellOff, CheckSquare, History, Square } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { ChatPanel } from "@/components/ChatPanel";
import { AiNotice, DDay, Empty, SourceLine, TypeTag, VerdictBadge, VerdictIcon, VirtualTag, Warn } from "@/components/ui";
import { useStore } from "@/lib/store";
import { evaluate, fmt, latest } from "@/lib/engine";
import { skillById } from "@/lib/data/catalog";
import { questProgress } from "@/lib/quest";

function Body() {
  const { id } = useParams<{ id: string }>();
  const s = useStore();
  const p = s.profile!;
  const now = s.nowDate;
  const o = s.opportunities.find((x) => x.id === id);
  if (!o) return <Empty>공고를 찾을 수 없어요.</Empty>;
  const v = latest(o);
  const { results, overall } = evaluate(o, p);
  const followed = s.followed.includes(o.id);
  const qp = questProgress(o, s.quests[o.id]);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
      <div className="space-y-4">
        <div className="card p-5">
          <div className="flex flex-wrap items-center gap-1.5">
            <TypeTag type={o.type} />
            {o.isVirtual && <VirtualTag />}
            {v.version > 1 && <span className="chip bg-danger text-white">마감 정정됨</span>}
            {!o.reviewed && <span className="chip bg-amber-100 text-amber-700">검수 대기</span>}
            <span className="ml-auto">
              <DDay opp={o} now={now} />
            </span>
          </div>
          <h1 className="mt-2 text-xl font-bold">{o.title}</h1>
          <p className="text-sm text-slate-500">
            {o.org}
            {o.period && ` · 활동 ${o.period}`} · 마감 {fmt(v.deadline)}
          </p>
          <SourceLine opp={o} />
          <AiNotice className="mt-1" />
          {!o.reviewed && (
            <div className="mt-3">
              <Warn>AI 구조화 신뢰도 {o.confidence}로 검수 전이에요. 아래 내용보다 원문을 먼저 확인하세요.</Warn>
            </div>
          )}
        </div>

        {o.facts && o.facts.length > 0 && (
          <div className="card p-5">
            <h2 className="font-bold">핵심 정보</h2>
            <dl className="mt-2 divide-y divide-line text-sm">
              {o.facts.map((f) => (
                <div key={f.label} className="grid gap-1 py-2 sm:grid-cols-[9rem_1fr]">
                  <dt className="font-semibold text-slate-500">{f.label}</dt>
                  <dd className={/지원금|혜택/.test(f.label) ? "font-bold text-accent" : ""}>
                    {/^https?:\/\//.test(f.value) ? (
                      <a href={f.value} target="_blank" rel="noreferrer" className="break-all underline">
                        {f.value}
                      </a>
                    ) : (
                      f.value
                    )}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-2 text-xs text-slate-500">공고문에 적힌 내용만 옮겼어요. 금액과 조건은 원문에서 다시 확인하세요.</p>
          </div>
        )}

        <div className="card p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-bold">필수 조건</h2>
            <VerdictBadge v={overall} />
          </div>
          <ul className="mt-3 space-y-2">
            {results.length === 0 && <li className="text-sm text-slate-500">명시된 필수 조건이 없어요.</li>}
            {results.map((r, i) => (
              <li
                key={i}
                className={`flex items-start gap-2 rounded-lg px-3 py-2 text-sm ${
                  r.verdict === "pass" ? "bg-emerald-50" : r.verdict === "fail" ? "bg-red-50" : "bg-amber-50"
                }`}
              >
                <VerdictIcon v={r.verdict} />
                <div className="flex-1">
                  <b>{r.condition.label}</b> <span className="text-slate-600">— {r.reason}</span>
                </div>
                <a href={`#sec-${r.condition.src}`} className="chip bg-panel text-slate-500">
                  원문 {r.condition.src}
                </a>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-500">학과·학년만으로 선발 가능성을 판단하지 않아요. 날짜·명시 조건은 규칙 엔진이 판정해요.</p>
          {o.conditionsBy === "ai" && (
            <p className="mt-1 text-xs text-slate-500">
              조건 문장은 AI가 읽어 정리했고, 공고 원문에 실제로 있는 구절만 남겼어요. 판정은 AI가 아니라 규칙이 해요.
            </p>
          )}

          {o.preferred.length > 0 && (
            <>
              <h3 className="mt-4 text-sm font-bold">우대 사항 · 내 스킬트리와 연결</h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {o.preferred.map((sk) => {
                  const st = p.skills[sk] ?? "none";
                  return (
                    <span
                      key={sk}
                      className={`chip border ${st === "none" ? "border-slate-300 text-slate-500" : "border-edge bg-navy/5 text-ink"}`}
                    >
                      {skillById(sk)?.name} {st === "verified" ? "✓ 검증" : st === "self" ? "✓ 자기 보고" : "(준비 전)"}
                    </span>
                  );
                })}
              </div>
            </>
          )}
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-bold">지원 퀘스트</h2>
            {followed ? (
              <button className="btn-ghost !py-1 text-xs" onClick={() => s.unfollow(o.id)}>
                <BellOff size={14} /> 알림 끄기
              </button>
            ) : (
              <button className="btn-primary !py-1 text-xs" onClick={() => s.follow(o.id)}>
                <BellPlus size={14} /> 지원 퀘스트 시작 · 마감 알림 받기
              </button>
            )}
          </div>
          {followed ? (
            <>
              <p className="mt-1 text-xs text-slate-500">
                {qp.done}/{qp.total} 완료 · D-7·3·1 알림 예약됨
              </p>
              <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
                {qp.items.map((it) => {
                  const done = !!s.quests[o.id]?.[it];
                  return (
                    <li key={it}>
                      <button
                        onClick={() => s.toggleQuest(o.id, it)}
                        className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${done ? "bg-emerald-50 text-ok" : "bg-paper"}`}
                      >
                        {done ? <CheckSquare size={16} /> : <Square size={16} />} {it}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </>
          ) : (
            <p className="mt-2 text-sm text-slate-500">
              제출 서류: {o.documents.join(", ") || "없음"} — 퀘스트를 시작하면 체크리스트와 마감 알림이 생겨요.
            </p>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <a
              href={o.applyUrl}
              target="_blank"
              rel="noreferrer"
              onClick={() => followed && !s.quests[o.id]?.["공식 신청처 이동"] && s.toggleQuest(o.id, "공식 신청처 이동")}
              className="btn bg-navy text-white"
            >
              공식 신청처로 이동 <ArrowUpRight size={16} />
            </a>
            <span className="text-xs text-slate-500">이동 버튼은 신청 완료로 기록하지 않아요{o.isVirtual && " · 가상 공고라 실제 신청처가 아니에요"}</span>
          </div>
        </div>

        {o.versions.length > 1 && (
          <div className="card p-5">
            <h2 className="flex items-center gap-1.5 font-bold">
              <History size={16} /> 변경 이력
            </h2>
            <ul className="mt-2 space-y-2 text-sm">
              {[...o.versions].reverse().map((ver) => (
                <li key={ver.version} className="rounded-lg bg-paper px-3 py-2">
                  <b>버전 {ver.version}</b> <span className="text-xs text-slate-500">확인 {fmt(ver.checkedAt)}</span>
                  {ver.changes?.map((c) => (
                    <div key={c.field} className="mt-1">
                      {c.field}: <span className="text-slate-400 line-through">{c.before}</span> →{" "}
                      <span className="font-bold text-danger">{c.after}</span>
                    </div>
                  ))}
                  {!ver.changes && <div className="text-xs text-slate-500">최초 등록</div>}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="card p-5">
          <h2 className="font-bold">원문 (의미 단위)</h2>
          <p className="text-xs text-slate-500">챗봇과 판정은 아래 문단만 근거로 사용해요.</p>
          <dl className="mt-3 space-y-2 text-sm">
            {o.sections.map((sec) => (
              <div key={sec.id} id={`sec-${sec.id}`} className="scroll-mt-20 rounded-lg border border-slate-100 px-3 py-2 target:ring-2 target:ring-accent">
                <dt className="text-xs font-bold text-slate-500">
                  {sec.id} {sec.title}
                </dt>
                <dd>{sec.text}</dd>
              </div>
            ))}
          </dl>
        </div>

        <Link href="/opportunities" className="text-sm underline">
          ← 기회 목록
        </Link>
      </div>

      <ChatPanel opp={o} />
    </div>
  );
}

export function Detail() {
  return (
    <RequireProfile>
      <Body />
    </RequireProfile>
  );
}
