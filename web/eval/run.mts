// 자동 검증: M2① 자격 판정 합성 조합, M6 알림 시나리오. 실행: npx tsx eval/run.mts [결과 파일]
// 기대값은 docs/EVALUATION.md의 표를 그대로 옮겼다. 기대값을 시스템 출력에 맞춰 고치지 않는다.
import { writeFileSync } from "node:fs";
import { evaluate, evaluateCondition, syncNotices } from "../src/lib/engine";
import type { Condition, Notice, Opportunity, Profile, Verdict } from "../src/lib/types";

// ───────── M2① 자격 판정
const base: Profile = {
  pseudoId: "eval", admissionYear: 2024, campus: "성심", departmentId: "ai", grade: 3, status: "재학",
  jobId: "ai-research", interests: [], weeklyHours: 5, targetTerm: "", skills: {}, createdAt: "",
};
const P = (x: Partial<Profile>): Profile => ({ ...base, ...x });
const C = (x: Partial<Condition> & { key: Condition["key"] }): Condition => ({ label: x.key, src: "§1", ...x }) as Condition;
const year = new Date().getFullYear();

const eligibility: { name: string; cond: Condition; profile: Profile; expect: Verdict }[] = [
  { name: "학적 재학 대상 × 재학", cond: C({ key: "status", status: ["재학"] }), profile: P({ status: "재학" }), expect: "pass" },
  { name: "학적 재학 대상 × 휴학", cond: C({ key: "status", status: ["재학"] }), profile: P({ status: "휴학" }), expect: "fail" },
  { name: "학적 재학 대상 × 졸업예정", cond: C({ key: "status", status: ["재학"] }), profile: P({ status: "졸업예정" }), expect: "fail" },
  { name: "학년 3·4 × 2학년", cond: C({ key: "grade", grades: [3, 4] }), profile: P({ grade: 2 }), expect: "fail" },
  { name: "학년 3·4 × 3학년", cond: C({ key: "grade", grades: [3, 4] }), profile: P({ grade: 3 }), expect: "pass" },
  { name: "학년 3·4 × 4학년", cond: C({ key: "grade", grades: [3, 4] }), profile: P({ grade: 4 }), expect: "pass" },
  { name: "전공 ICT × 인공지능학과", cond: C({ key: "major", majors: ["ict"] }), profile: P({ departmentId: "ai" }), expect: "pass" },
  { name: "전공 ICT × 심리학과", cond: C({ key: "major", majors: ["ict"] }), profile: P({ departmentId: "psychology" }), expect: "fail" },
  { name: "전공 ICT × 자유전공", cond: C({ key: "major", majors: ["ict"] }), profile: P({ departmentId: "free-major" }), expect: "check" },
  { name: "학력 4년제 졸업(예정) × 재학 2학년", cond: C({ key: "degree", degree: "bachelor" }), profile: P({ grade: 2 }), expect: "fail" },
  { name: "학력 4년제 졸업(예정) × 재학 4학년", cond: C({ key: "degree", degree: "bachelor" }), profile: P({ grade: 4 }), expect: "check" },
  { name: "학력 4년제 졸업(예정) × 졸업예정", cond: C({ key: "degree", degree: "bachelor" }), profile: P({ grade: 4, status: "졸업예정" }), expect: "pass" },
  { name: "학력 무관 × 1학년", cond: C({ key: "degree", degree: "none" }), profile: P({ grade: 1 }), expect: "pass" },
  { name: "학력 고졸 이상 × 2학년", cond: C({ key: "degree", degree: "high" }), profile: P({ grade: 2 }), expect: "pass" },
  { name: "학력 석사 이상 × 4학년", cond: C({ key: "degree", degree: "master" }), profile: P({ grade: 4 }), expect: "fail" },
  { name: "학력 전문대 졸업 이상 × 3학년", cond: C({ key: "degree", degree: "associate" }), profile: P({ grade: 3 }), expect: "check" },
  { name: "토익 700 × 미입력", cond: C({ key: "skill", skill: "SK-TOEIC", min: "700" }), profile: P({}), expect: "check" },
  { name: "토익 700 × 650점", cond: C({ key: "skill", skill: "SK-TOEIC", min: "700" }), profile: P({ skills: { "SK-TOEIC": "self" }, scores: { "SK-TOEIC": "650" } }), expect: "fail" },
  { name: "토익 700 × 850점", cond: C({ key: "skill", skill: "SK-TOEIC", min: "700" }), profile: P({ skills: { "SK-TOEIC": "self" }, scores: { "SK-TOEIC": "850" } }), expect: "pass" },
  { name: "창업 예비~3년 × 미입력", cond: C({ key: "startup", stages: ["예비창업자", "1년미만", "2년미만", "3년미만"] }), profile: P({}), expect: "check" },
  { name: "창업 예비~3년 × 예비창업자", cond: C({ key: "startup", stages: ["예비창업자", "1년미만", "2년미만", "3년미만"] }), profile: P({ startup: { stage: "pre" } }), expect: "pass" },
  { name: "창업 예비~3년 × 창업 3년 미만", cond: C({ key: "startup", stages: ["예비창업자", "1년미만", "2년미만", "3년미만"] }), profile: P({ startup: { stage: "3" } }), expect: "pass" },
  { name: "창업 예비~3년 × 창업 7년 미만", cond: C({ key: "startup", stages: ["예비창업자", "1년미만", "2년미만", "3년미만"] }), profile: P({ startup: { stage: "7" } }), expect: "fail" },
  { name: "연령 20~39 × 미입력", cond: C({ key: "age", ages: ["20-39"] }), profile: P({}), expect: "check" },
  { name: "연령 20~39 × 23세", cond: C({ key: "age", ages: ["20-39"] }), profile: P({ startup: { birthYear: year - 23 } }), expect: "pass" },
  { name: "연령 20~39 × 45세", cond: C({ key: "age", ages: ["20-39"] }), profile: P({ startup: { birthYear: year - 45 } }), expect: "fail" },
  { name: "연령 20~39 × 경계 20세", cond: C({ key: "age", ages: ["20-39"] }), profile: P({ startup: { birthYear: year - 20 } }), expect: "check" },
  { name: "지역 경기 × 미입력", cond: C({ key: "region", regions: ["경기"] }), profile: P({}), expect: "check" },
  { name: "지역 경기 × 경기 거주", cond: C({ key: "region", regions: ["경기"] }), profile: P({ startup: { region: "경기" } }), expect: "check" },
  { name: "지역 경기 × 서울 거주", cond: C({ key: "region", regions: ["경기"] }), profile: P({ startup: { region: "서울" } }), expect: "fail" },
  { name: "기타 문장(병역필) × 아무 학생", cond: C({ key: "other", label: "병역: 병역필 또는 면제" }), profile: P({}), expect: "check" },
];
const m2 = eligibility.map((t) => {
  const got = evaluateCondition(t.cond, t.profile).verdict;
  const kind = got === t.expect ? "일치" : t.expect === "pass" && got === "fail" ? "거짓 배제" : t.expect === "fail" && got === "pass" ? "거짓 허용" : "판정 차이";
  return { name: t.name, expect: t.expect, got, ok: got === t.expect, kind };
});
// 충돌: 학년은 충족, 학적은 미충족 → 공고 전체 미충족
{
  const o = { required: [C({ key: "grade", grades: [3, 4] }), C({ key: "status", status: ["재학"] })] } as unknown as Opportunity;
  const got = evaluate(o, P({ grade: 3, status: "휴학" })).overall;
  m2.push({ name: "충돌: 학년 충족 + 학적 미충족 → 전체", expect: "fail", got, ok: got === "fail", kind: got === "fail" ? "일치" : "거짓 허용" });
}

// ───────── M6 알림
const T = (s: string) => new Date(s.length === 16 ? `${s}:00+09:00` : s);
const opp = (id: string, ...vs: [string, string?][]): Opportunity =>
  ({
    id, title: id, required: [], sections: [],
    versions: vs.map(([deadline, checkedAt], i) => ({
      version: i + 1, deadline: `${deadline}:00+09:00`, checkedAt: `${checkedAt ?? "2026-11-20T09:00"}:00+09:00`,
      ...(i > 0 && { changes: [{ field: "마감", before: vs[i - 1][0], after: deadline }] }),
    })),
  }) as unknown as Opportunity;

class Sim {
  notices: Notice[] = [];
  followed: string[] = [];
  quests: Record<string, Record<string, boolean>> = {};
  constructor(public opps: Opportunity[], public now: Date) {}
  sync(now?: Date) {
    if (now) this.now = now;
    this.notices = syncNotices(this.notices, this.opps, this.followed, this.now, this.quests);
    return this;
  }
  follow(id: string) {
    if (!this.followed.includes(id)) this.followed.push(id);
    return this.sync();
  }
  // store.tsx의 unfollow와 같은 동작
  unfollow(id: string) {
    this.followed = this.followed.filter((x) => x !== id);
    this.notices = this.notices.map((n) => (n.oppId === id && n.status === "scheduled" ? { ...n, status: "cancelled" as const } : n));
    return this.sync();
  }
  of(id: string, f: Partial<{ kind: string; status: string; version: number }> = {}) {
    return this.notices.filter((n) => n.oppId === id && (!f.kind || n.kind === f.kind) && (!f.status || n.status === f.status) && (!f.version || n.version === f.version));
  }
}

const scenarios: { name: string; run: () => [boolean, string] }[] = [
  { name: "1 마감 10일 전 팔로우 → D-7·3·1 예약", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a");
    return [s.of("a", { status: "scheduled" }).length === 3 && s.of("a", { status: "sent" }).length === 0, `예약 ${s.of("a", { status: "scheduled" }).map((n) => n.kind)}`];
  } },
  { name: "2 마감 2일 전 팔로우 → D-1만", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-12-08T09:00")).follow("a");
    const k = s.of("a").map((n) => n.kind);
    return [k.length === 1 && k[0] === "D-1", `알림 ${k}`];
  } },
  { name: "3 같은 상태로 두 번 동기화 → 변화 없음(멱등)", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a");
    const before = JSON.stringify(s.notices);
    s.sync().sync();
    return [before === JSON.stringify(s.notices), `${s.notices.length}개`];
  } },
  { name: "4 D-7 시점 도래 → D-7만 발송", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a").sync(T("2026-12-03T18:00"));
    const sent = s.of("a", { status: "sent" }).map((n) => n.kind);
    return [sent.length === 1 && sent[0] === "D-7", `발송 ${sent}`];
  } },
  { name: "5 마감 연장 정정 → 정정 1개, v1 예약 취소", run: () => {
    const o = opp("a", ["2026-12-10T18:00"]);
    const s = new Sim([o], T("2026-11-30T09:00")).follow("a");
    s.opps = [opp("a", ["2026-12-10T18:00"], ["2026-12-12T18:00", "2026-12-01T09:00"])];
    s.sync(T("2026-12-01T09:00"));
    const fix = s.of("a", { kind: "정정" }).length, v1 = s.of("a", { version: 1, status: "scheduled" }).length, v2 = s.of("a", { version: 2, status: "scheduled" }).length;
    return [fix === 1 && v1 === 0 && v2 === 3, `정정 ${fix}, v1 예약 ${v1}, v2 예약 ${v2}`];
  } },
  { name: "6 정정 후 다시 동기화 → 정정 알림 중복 없음", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"], ["2026-12-12T18:00", "2026-12-01T09:00"])], T("2026-12-01T09:00")).follow("a");
    s.sync().sync(T("2026-12-02T09:00"));
    return [s.of("a", { kind: "정정" }).length === 1, `정정 ${s.of("a", { kind: "정정" }).length}`];
  } },
  { name: "7 v2→v3 연속 정정 → 정정 2개, v2 예약 취소", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"], ["2026-12-12T18:00", "2026-12-01T09:00"])], T("2026-12-01T09:00")).follow("a");
    s.opps = [opp("a", ["2026-12-10T18:00"], ["2026-12-12T18:00", "2026-12-01T09:00"], ["2026-12-14T18:00", "2026-12-02T09:00"])];
    s.sync(T("2026-12-02T09:00"));
    const fix = s.of("a", { kind: "정정" }).length, v2 = s.of("a", { version: 2, status: "scheduled" }).length;
    return [fix === 2 && v2 === 0, `정정 ${fix}, v2 예약 ${v2}`];
  } },
  { name: "8 마감 단축으로 D-3 시점이 이미 지남 → v2 D-3 없음", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a");
    s.opps = [opp("a", ["2026-12-10T18:00"], ["2026-12-08T18:00", "2026-12-06T09:00"])];
    s.sync(T("2026-12-06T09:00"));
    return [s.of("a", { version: 2, kind: "D-3" }).length === 0, `v2 ${s.of("a", { version: 2 }).map((n) => n.kind)}`];
  } },
  { name: "9 마감 23:59(KST) → D-1은 전날 23:59", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T23:59"])], T("2026-11-30T09:00")).follow("a");
    const d1 = s.of("a", { kind: "D-1" })[0];
    return [!!d1 && new Date(d1.fireAt).getTime() === T("2026-12-09T23:59").getTime(), d1?.fireAt ?? "없음"];
  } },
  { name: "10 팔로우 해제 → 남은 예약 취소", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a").unfollow("a").sync(T("2026-12-09T20:00"));
    return [s.of("a", { status: "scheduled" }).length === 0 && s.of("a", { status: "sent" }).length === 0, `예약 ${s.of("a", { status: "scheduled" }).length}, 발송 ${s.of("a", { status: "sent" }).length}`];
  } },
  { name: "11 해제 후 다시 팔로우 → 새 예약", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a").unfollow("a").follow("a");
    return [s.of("a", { status: "scheduled" }).length === 3, `예약 ${s.of("a", { status: "scheduled" }).length}`];
  } },
  { name: "12 발송된 알림이 있는 상태에서 정정 → 발송분 유지, 예약만 취소", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a").sync(T("2026-12-03T18:00"));
    s.opps = [opp("a", ["2026-12-10T18:00"], ["2026-12-12T18:00", "2026-12-04T09:00"])];
    s.sync(T("2026-12-04T09:00"));
    const sent = s.of("a", { version: 1, status: "sent" }).length, v1s = s.of("a", { version: 1, status: "scheduled" }).length;
    return [sent === 1 && v1s === 0, `v1 발송 ${sent}, v1 예약 ${v1s}`];
  } },
  { name: "13 마감 지난 공고 팔로우 → 알림 없음", run: () => {
    const s = new Sim([opp("a", ["2026-11-25T18:00"])], T("2026-11-30T09:00")).follow("a");
    return [s.of("a").length === 0, `${s.of("a").length}개`];
  } },
  { name: "14 지원 완료(공식 신청처 이동) 후 → 남은 D-day 알림 중단", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a");
    s.quests = { a: { "공식 신청처 이동": true } };
    s.sync(T("2026-12-09T20:00"));
    return [s.of("a", { status: "sent" }).length === 0, `완료 후 발송 ${s.of("a", { status: "sent" }).map((n) => n.kind)}`];
  } },
  { name: "15 공고 2개 동시 팔로우 → 공고별 독립", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"]), opp("b", ["2026-12-20T18:00"])], T("2026-11-30T09:00")).follow("a").follow("b");
    const keys = new Set(s.notices.map((n) => n.idempotencyKey));
    return [s.of("a").length === 3 && s.of("b").length === 3 && keys.size === 6, `a ${s.of("a").length}, b ${s.of("b").length}`];
  } },
  { name: "16 가상 시계를 되돌림 → 발송분이 다시 예약되지 않음", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a").sync(T("2026-12-03T18:00")).sync(T("2026-11-30T09:00"));
    return [s.of("a", { kind: "D-7" })[0]?.status === "sent", s.of("a", { kind: "D-7" })[0]?.status ?? "없음"];
  } },
  { name: "17 저장 후 다른 기기에서 복원 → 중복 없음", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a");
    s.notices = JSON.parse(JSON.stringify(s.notices));
    s.sync();
    return [s.notices.length === 3, `${s.notices.length}개`];
  } },
  { name: "18 공고가 목록에서 사라짐 → 예약 취소", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a");
    s.opps = [];
    s.sync(T("2026-12-09T20:00"));
    return [s.of("a", { status: "sent" }).length === 0 && s.of("a", { status: "scheduled" }).length === 0, `예약 ${s.of("a", { status: "scheduled" }).length}, 발송 ${s.of("a", { status: "sent" }).length}`];
  } },
  { name: "19 마감 외 항목만 정정 → 정정 1개, D-day 예약 유지", run: () => {
    const o2 = opp("a", ["2026-12-10T18:00"], ["2026-12-10T18:00", "2026-11-30T10:00"]);
    (o2.versions[1] as { changes?: unknown }).changes = [{ field: "제출 서류", before: "이력서", after: "이력서, 포트폴리오" }];
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a");
    s.opps = [o2];
    s.sync(T("2026-11-30T10:00"));
    return [s.of("a", { kind: "정정" }).length === 1 && s.of("a", { status: "scheduled" }).filter((n) => n.kind !== "정정").length === 3, `정정 ${s.of("a", { kind: "정정" }).length}, D-day 예약 ${s.of("a", { status: "scheduled" }).filter((n) => n.kind !== "정정").length}`];
  } },
  { name: "20 같은 공고의 D-day 알림이 하루에 2개 이상 발송되지 않음", run: () => {
    const s = new Sim([opp("a", ["2026-12-10T18:00"])], T("2026-11-30T09:00")).follow("a");
    for (let d = 30; d <= 41; d++) {
      const day = new Date(T("2026-11-30T09:00").getTime() + (d - 30) * 86_400_000);
      if (d === 35) s.opps = [opp("a", ["2026-12-10T18:00"], ["2026-12-11T18:00", day.toISOString().slice(0, 16)])];
      s.sync(day).sync(new Date(day.getTime() + 9 * 3_600_000));
    }
    const perDay: Record<string, number> = {};
    for (const n of s.of("a", { status: "sent" }).filter((n) => n.kind.startsWith("D-"))) {
      const k = new Date(new Date(n.fireAt).getTime() + 9 * 3_600_000).toISOString().slice(0, 10);
      perDay[k] = (perDay[k] ?? 0) + 1;
    }
    return [Object.values(perDay).every((x) => x <= 1), JSON.stringify(perDay)];
  } },
];
const m6 = scenarios.map((t) => {
  try {
    const [ok, detail] = t.run();
    return { name: t.name, ok, detail };
  } catch (e) {
    return { name: t.name, ok: false, detail: `오류: ${(e as Error).message}` };
  }
});

const out = {
  m2: { total: m2.length, match: m2.filter((x) => x.ok).length, falseExclude: m2.filter((x) => x.kind === "거짓 배제").length, falseInclude: m2.filter((x) => x.kind === "거짓 허용").length, checkShare: m2.filter((x) => x.got === "check").length / m2.length, cases: m2 },
  m6: { total: m6.length, pass: m6.filter((x) => x.ok).length, cases: m6 },
};
for (const c of m2.filter((x) => !x.ok)) console.log("M2 불일치:", c.name, "기대", c.expect, "실제", c.got, `(${c.kind})`);
for (const c of m6) console.log(c.ok ? "  통과" : "  실패", c.name, "—", c.detail);
console.log(`M2 ${out.m2.match}/${out.m2.total} 일치 · 거짓 배제 ${out.m2.falseExclude} · 거짓 허용 ${out.m2.falseInclude} · 확인 필요 비율 ${(out.m2.checkShare * 100).toFixed(0)}%`);
console.log(`M6 ${out.m6.pass}/${out.m6.total} 통과`);
if (process.argv[2]) writeFileSync(process.argv[2], JSON.stringify(out, null, 1));
