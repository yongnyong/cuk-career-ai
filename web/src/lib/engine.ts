// 규칙 엔진·추천·스킬트리·알림·근거 챗봇.
// 원칙: 날짜·자격 판정은 AI가 아닌 코드가 한다. 근거가 없으면 답하지 않는다.
// 서버(api/) 연결 전까지 브라우저에서 같은 로직으로 동작하며, 서버 구현도 이 규칙을 따른다.
import { JOBS, SKILLS, formatScore, jobById, meetsTarget, skillById } from "./data/catalog";
import { getDepartment } from "./data/departments";
import type {
  ChatAnswer,
  Condition,
  ConditionResult,
  Notice,
  Opportunity,
  OppType,
  Profile,
  Verdict,
} from "./types";

// ───────── 날짜
export const latest = (o: Opportunity) => o.versions[o.versions.length - 1];
export const deadlineOf = (o: Opportunity) => new Date(latest(o).deadline);
export function dday(o: Opportunity, now: Date) {
  const ms = deadlineOf(o).getTime() - now.getTime();
  return Math.ceil(ms / 86_400_000);
}
export const isOpen = (o: Opportunity, now: Date) => deadlineOf(o).getTime() > now.getTime();
export function fmt(isoStr: string, withTime = true) {
  const d = new Date(isoStr);
  const p = (n: number) => String(n).padStart(2, "0");
  const k = new Date(d.getTime() + 9 * 3600_000); // KST 표시
  const s = `${k.getUTCFullYear()}.${p(k.getUTCMonth() + 1)}.${p(k.getUTCDate())}`;
  return withTime ? `${s} ${p(k.getUTCHours())}:${p(k.getUTCMinutes())}` : s;
}

// ───────── 규칙 엔진 (3값: 충족 / 미충족 / 확인 필요)
export function evaluateCondition(c: Condition, p: Profile): ConditionResult {
  const dept = getDepartment(p.departmentId);
  const r = (verdict: Verdict, reason: string): ConditionResult => ({ condition: c, verdict, reason });
  switch (c.key) {
    case "status":
      return c.status!.includes(p.status)
        ? r("pass", `현재 학적 ${p.status}`)
        : r("fail", `공고는 ${c.status!.join("·")}생 대상, 현재 ${p.status}`);
    case "grade":
      return c.grades!.includes(p.grade)
        ? r("pass", `현재 ${p.grade}학년`)
        : r("fail", `공고는 ${c.grades!.join("·")}학년 대상, 현재 ${p.grade}학년`);
    case "major":
      if (!dept) return r("check", "소속 학과 정보 없음");
      if (dept.field === "open") return r("check", "광역·자유전공은 담당 부서 확인 필요");
      return c.majors!.includes(dept.field)
        ? r("pass", `${dept.name} — 지정 계열에 포함`)
        : r("fail", `${dept.name} — 지정 계열에 포함되지 않음`);
    case "skill": {
      const st = p.skills[c.skill!] ?? "none";
      if (c.min) {
        // 점수·등급 기준이 있는 조건: 스킬트리에 적어 둔 내 점수와 비교한다
        const ok = meetsTarget(c.skill!, p.scores?.[c.skill!], c.min);
        const need = formatScore(c.skill!, c.min);
        if (ok === null) return r("check", `${need} 이상 필요 — 스킬트리에 내 점수를 적으면 판정해요`);
        return ok ? r("pass", `내 기록 ${formatScore(c.skill!, p.scores![c.skill!])} — 기준 ${need} 이상`) : r("fail", `기준은 ${need} 이상, 내 기록은 ${formatScore(c.skill!, p.scores![c.skill!])}`);
      }
      if (st === "verified") return r("pass", "증빙 확인된 자격");
      if (st === "self") return r("check", "자기 보고 완료 — 증빙은 신청처에서 확인");
      return r("fail", "아직 준비하지 않은 역량");
    }
    case "startup": {
      const stage = p.startup?.stage;
      if (!stage) return r("check", "내 정보에 창업 단계를 적으면 판정해요");
      if (stage === "none") return r("check", "창업 계획이 없다고 적어 두셨어요. 창업을 시작하면 다시 확인하세요");
      if (stage === "pre")
        return c.stages!.includes("예비창업자") ? r("pass", "예비창업자도 신청할 수 있어요") : r("fail", "이미 창업한 기업 대상이에요(예비창업자 제외)");
      const limit = Math.max(0, ...c.stages!.map((x) => Number(x.match(/^(\d+)년미만$/)?.[1] ?? 0)));
      if (!limit) return r("fail", "예비창업자 대상이에요(이미 창업한 기업 제외)");
      return Number(stage) <= limit ? r("pass", `창업 ${stage}년 미만 — 공고는 ${limit}년 미만까지`) : r("fail", `공고는 창업 ${limit}년 미만까지, 내 기업은 그보다 오래됐어요`);
    }
    case "age": {
      const year = p.startup?.birthYear;
      if (!year) return r("check", "내 정보에 출생 연도를 적으면 판정해요");
      const age = new Date().getFullYear() - year; // 생일 전후로 한 살 차이가 날 수 있다
      const band = age < 20 ? "u20" : age < 40 ? "20-39" : "40+";
      if (age === 19 || age === 20 || age === 39 || age === 40) return r("check", `만 ${age - 1}~${age}세 — 연령 경계라서 원문에서 기준일을 확인하세요`);
      return c.ages!.includes(band) ? r("pass", `만 ${age}세 안팎 — 대상 연령에 포함`) : r("fail", `만 ${age}세 안팎 — 대상 연령이 아니에요`);
    }
    case "region": {
      const region = p.startup?.region;
      if (!region) return r("check", "내 정보에 거주 지역을 적으면 판정해요");
      return c.regions!.includes(region) ? r("check", `${region} 거주 — 시·군 단위 조건은 원문에서 확인하세요`) : r("fail", `공고는 ${c.regions!.join("·")} 대상, 내 지역은 ${region}`);
    }
    case "degree":
      // 학부생 기준: 졸업 요건은 학적·학년으로 판정하고, 애매하면 확인 필요로 남긴다
      if (c.degree === "none" || c.degree === "high") return r("pass", "학력 제한이 없거나 고졸 이상이라 지원할 수 있어요");
      if (c.degree === "master") return r("fail", "석사 이상 대상이라 학부생은 지원할 수 없어요");
      if (c.degree === "bachelor") {
        if (p.status === "졸업예정") return r("pass", "졸업예정자로 지원할 수 있어요");
        if (p.grade >= 4) return r("check", "졸업(예정)자 대상 — 4학년은 졸업예정 인정 시점을 원문에서 확인");
        return r("fail", `졸업(예정)자 대상 공고예요. 현재 ${p.grade}학년`);
      }
      if (c.degree === "associate") return r("check", "전문대 졸업 이상 — 4년제 재학생 지원 가능 여부를 원문에서 확인");
      return r("check", "공고에 최소 학력이 분명하지 않아요. 원문에서 확인");
    default:
      return r("check", "자동으로 판정하지 않는 조건이에요. 원문에서 직접 확인");
  }
}

export function evaluate(o: Opportunity, p: Profile) {
  const results = o.required.map((c) => evaluateCondition(c, p));
  const overall: Verdict = results.some((x) => x.verdict === "fail")
    ? "fail"
    : results.some((x) => x.verdict === "check")
      ? "check"
      : "pass";
  return { results, overall };
}

export const VERDICT_LABEL: Record<Verdict, string> = {
  pass: "명시 조건 충족",
  check: "확인 필요",
  fail: "조건 미충족",
};

// ───────── 추천 (규칙 필터 → 가중 점수 → 유형 다양화)
export interface Recommendation {
  opp: Opportunity;
  score: number;
  reasons: string[];
  verdict: Verdict;
}

export function recommend(opps: Opportunity[], p: Profile, now: Date): Recommendation[] {
  const job = jobById(p.jobId);
  const dept = getDepartment(p.departmentId);
  const scored: Recommendation[] = [];
  for (const o of opps) {
    if (!isOpen(o, now)) continue;
    const { overall } = evaluate(o, p);
    if (overall === "fail") continue;
    let score = 0;
    const reasons: string[] = [];
    if (o.jobs.length === 0) {
      score += 30;
      reasons.push("모든 학생 대상 공지");
    } else if (o.jobs.includes(p.jobId) || (job?.base && o.jobs.includes(job.base))) {
      score += 50;
      reasons.push(`목표 직무(${job?.name}) 연결`);
    } else if (dept && o.jobs.some((j) => jobById(j)?.fields.includes(dept.field))) {
      score += 15;
      reasons.push("전공 계열 관련 기회");
    } else if (p.interests.some((i) => o.jobs.includes(i))) {
      score += 20;
      reasons.push("관심 분야");
    } else continue;
    const held = o.preferred.filter((s) => (p.skills[s] ?? "none") !== "none");
    if (held.length) {
      score += held.length * 10;
      reasons.push(`우대 역량 ${held.map((s) => skillById(s)?.name).join(", ")} 보유`);
    }
    const d = dday(o, now);
    if (d <= 7) {
      score += 10;
      reasons.push(`마감 임박 D-${d}`);
    }
    if (overall === "check") reasons.push("일부 조건 확인 필요");
    scored.push({ opp: o, score, reasons, verdict: overall });
  }
  scored.sort((a, b) => b.score - a.score);
  // 유형 다양화(MMR 단순화): 같은 유형이 연속 3개를 넘지 않게
  const out: Recommendation[] = [];
  const rest = [...scored];
  while (rest.length) {
    const lastTypes = out.slice(-2).map((x) => x.opp.type);
    const idx = rest.findIndex((x) => !(lastTypes.length === 2 && lastTypes.every((t) => t === x.opp.type)));
    out.push(...rest.splice(idx === -1 ? 0 : idx, 1));
  }
  return out;
}

// ───────── 스킬트리
export interface TreeNode {
  skill: string;
  name: string;
  kind: string;
  required: boolean;
  prereq: string[];
  depth: number;
  state: "none" | "self" | "verified";
  locked: boolean;
  opportunities: Opportunity[]; // 이 노드에서 열리는 실제 기회
  target?: string; // 학과 권장 점수·등급
  score?: string; // 내 점수·등급
}

export function buildTree(p: Profile, opps: Opportunity[], now: Date): TreeNode[] {
  const job = jobById(p.jobId);
  if (!job) return [];
  const depth: Record<string, number> = {};
  const depthOf = (id: string): number => {
    if (depth[id] !== undefined) return depth[id];
    const n = job.nodes.find((x) => x.skill === id);
    depth[id] = n?.prereq?.length ? Math.max(...n.prereq.map(depthOf)) + 1 : 0;
    return depth[id];
  };
  return job.nodes.map((n) => {
    const sk = skillById(n.skill)!;
    const state = p.skills[n.skill] ?? "none";
    const locked = (n.prereq ?? []).some((q) => (p.skills[q] ?? "none") === "none");
    const linked = opps.filter(
      (o) =>
        isOpen(o, now) &&
        (o.preferred.includes(n.skill) || o.required.some((c) => c.skill === n.skill)) &&
        evaluate(o, p).overall !== "fail",
    );
    return {
      skill: n.skill,
      name: sk.name,
      kind: sk.kind,
      required: n.required,
      prereq: n.prereq ?? [],
      depth: depthOf(n.skill),
      state,
      locked,
      opportunities: linked,
      target: n.target,
      score: p.scores?.[n.skill],
    };
  });
}

export function progress(p: Profile) {
  const job = jobById(p.jobId);
  const nodes = job?.nodes ?? [];
  let exp = 0;
  for (const n of nodes) {
    const st = p.skills[n.skill] ?? "none";
    exp += st === "verified" ? 100 : st === "self" ? 60 : 0;
  }
  const max = nodes.length * 100 || 1;
  return { exp, max, pct: Math.round((exp / max) * 100), level: 1 + Math.floor(exp / 40) };
}

// 오늘의 퀘스트: 가장 가까운 기회 하나 + 다음 노드 하나
export function nextNode(p: Profile) {
  const job = jobById(p.jobId);
  return job?.nodes.find(
    (n) => (p.skills[n.skill] ?? "none") === "none" && (n.prereq ?? []).every((q) => (p.skills[q] ?? "none") !== "none"),
  );
}

// 경로 초안 생성 — 서버 연결 시 Gemini가 경로 설명을 쓰고, 노드는 직무 그래프에서만 고른다(존재하는 노드 ID만 허용)
// 학과에서 고를 수 있는 직무: 공통 직무 + 그 학과의 전용 테크(다른 학과 전용 테크는 제외)
export const jobsFor = (departmentId: string) => JOBS.filter((j) => !j.departments || j.departments.includes(departmentId));

export function suggestJobs(departmentId: string) {
  const dept = getDepartment(departmentId);
  const all = jobsFor(departmentId);
  if (!dept || dept.field === "open") return all;
  const rank = (j: (typeof all)[number]) => (j.departments ? 0 : j.fields.includes(dept.field) ? 1 : 2);
  return [...all].sort((a, b) => rank(a) - rank(b));
}

// ───────── 알림 (멱등키로 중복 방지, 정정 시 이전 알림 무효화)
const DAY = 86_400_000;
export function syncNotices(
  notices: Notice[],
  opps: Opportunity[],
  followed: string[],
  now: Date,
  quests: Record<string, Record<string, boolean>> = {},
): Notice[] {
  const byKey = new Map(notices.map((n) => [n.idempotencyKey, { ...n }]));
  const cancel = (id: string, keep: (n: Notice) => boolean = () => false) => {
    for (const n of byKey.values()) if (n.oppId === id && n.status === "scheduled" && !keep(n)) n.status = "cancelled";
  };
  for (const id of followed) {
    const o = opps.find((x) => x.id === id);
    // 공고가 목록에서 사라지면(삭제·수집 제외) 남은 예약을 취소한다
    if (!o) {
      cancel(id);
      continue;
    }
    // 공식 신청처로 이동(지원 완료)했으면 남은 마감 알림은 보내지 않는다. 정정 알림은 그대로 둔다
    const applied = !!quests[id]?.["공식 신청처 이동"];
    if (applied) cancel(id, (n) => n.kind === "정정");
    const v = latest(o);
    // 이전 버전 예약 알림 무효화
    for (const n of byKey.values()) {
      if (n.oppId === id && n.version < v.version && n.status === "scheduled") n.status = "cancelled";
    }
    // 정정 알림
    if (v.version > 1) {
      const key = `${id}:${v.version}:정정`;
      if (!byKey.has(key)) {
        const ch = v.changes?.map((c) => `${c.field} ${c.before} → ${c.after}`).join(", ");
        byKey.set(key, {
          id: key,
          oppId: id,
          version: v.version,
          kind: "정정",
          fireAt: v.checkedAt,
          message: `[정정] ${o.title} — ${ch ?? "내용 변경"}. 이전 알림은 무효입니다.`,
          status: "scheduled",
          idempotencyKey: key,
        });
      }
    }
    if (applied) continue;
    for (const k of [7, 3, 1] as const) {
      const key = `${id}:${v.version}:D-${k}`;
      const dl = new Date(v.deadline);
      const fire = new Date(dl.getTime() - k * DAY);
      const prev = byKey.get(key);
      if (prev) {
        // 팔로우를 해제했다가 다시 팔로우하면 같은 버전의 취소된 예약을 되살린다
        if (prev.status === "cancelled" && fire.getTime() >= now.getTime()) prev.status = "scheduled";
        continue;
      }
      if (fire.getTime() < now.getTime()) continue; // 이미 지난 시점의 알림은 만들지 않음
      byKey.set(key, {
        id: key,
        oppId: id,
        version: v.version,
        kind: `D-${k}`,
        fireAt: fire.toISOString(),
        message: `[D-${k}] ${o.title} 마감 ${fmt(v.deadline)}`,
        status: "scheduled",
        idempotencyKey: key,
      });
    }
  }
  // 발송: 가상 시계 기준 도래한 예약 알림
  for (const n of byKey.values()) {
    if (n.status === "scheduled" && new Date(n.fireAt).getTime() <= now.getTime()) n.status = "sent";
  }
  return [...byKey.values()].sort((a, b) => a.fireAt.localeCompare(b.fireAt));
}

// ───────── 근거 기반 챗봇 (RAG 대체 구현: 선택 공고 최신 버전만 검색)
const bigrams = (s: string) => {
  const t = s.replace(/\s+/g, "").toLowerCase();
  const out = new Set<string>();
  for (let i = 0; i < t.length - 1; i++) out.add(t.slice(i, i + 2));
  return out;
};

export function answer(q: string, o: Opportunity, p: Profile | null): ChatAnswer {
  const v = latest(o);
  const cite = (sectionId: string) => ({ sectionId, version: v.version });
  const sec = (id: string) => o.sections.find((s) => s.id === id)!;
  const hold = (text: string): ChatAnswer => ({ text, citations: [], held: true });

  if (/합격|붙을|가능성|뽑힐/.test(q))
    return hold("합격 가능성은 예측하지 않아요. 공고에 명시된 조건 충족 여부만 확인해 드릴 수 있어요.");

  if (/마감|기한|언제까지|바뀌|정정|연장/.test(q)) {
    if (v.version > 1) {
      const prev = o.versions[o.versions.length - 2];
      return {
        text: `네, 버전 ${v.version}에서 마감이 ${fmt(prev.deadline)} → ${fmt(v.deadline)}로 정정됐어요. 이전 알림은 취소하고 새 일정으로 다시 알려드려요.`,
        citations: [cite("§5")],
        held: false,
      };
    }
    return { text: `원문 기준 접수 마감은 ${fmt(v.deadline)}이에요.`, citations: [cite("§5")], held: false };
  }

  if (/토익|toeic|오픽|opic|점수|어학|학점|성적/i.test(q)) {
    const hit = o.sections.find((s) => /TOEIC|OPIc|JLPT|HSK|어학|성적|학점/.test(s.text));
    if (!hit)
      return hold(
        "확인 필요 · 공고 원문에 어학·성적 조건이 없어요. 담당 부서(공고 문의처)에 확인해 주세요. 합격 가능성은 예측하지 않아요.",
      );
    return { text: `원문 ${hit.id}에 이렇게 적혀 있어요: "${hit.text}"`, citations: [cite(hit.id)], held: false };
  }

  if (/서류|제출|분량|자기소개서|이력서|매/.test(q)) {
    const s4 = sec("§4");
    return { text: `원문 ${s4.id}: ${s4.text}`, citations: [cite("§4")], held: false };
  }

  if (/자격|학년|대상|지원\s?가능|지원할\s?수/.test(q)) {
    const s2 = sec("§2");
    let t = `원문 ${s2.id}: ${s2.text}`;
    if (p) {
      const { results } = evaluate(o, p);
      if (results.length)
        t += ` 내 프로필 기준 판정: ${results.map((r) => `${r.condition.label} ${VERDICT_LABEL[r.verdict]}`).join(", ")}.`;
    }
    return { text: t, citations: [cite("§2")], held: false };
  }

  // 일반 질문: 문단 bigram 유사도 검색, 임계값 미만이면 답변 보류
  const qb = bigrams(q);
  let best: { id: string; score: number } | null = null;
  for (const s of o.sections) {
    const sb = bigrams(s.title + s.text);
    let hit = 0;
    for (const b of qb) if (sb.has(b)) hit++;
    const score = qb.size ? hit / qb.size : 0;
    if (!best || score > best.score) best = { id: s.id, score };
  }
  if (!best || best.score < 0.25)
    return hold("확인 필요 · 이 공고 원문에서 질문과 관련된 근거를 찾지 못했어요. 담당 부서에 문의해 주세요.");
  const s = sec(best.id);
  return { text: `원문 ${s.id}(${s.title}): ${s.text}`, citations: [cite(s.id)], held: false };
}

// 서버측 인용 검증: 모델이 낸 근거 ID가 실제 문서·버전에 존재하는지 대조
export function verifyCitations(a: ChatAnswer, o: Opportunity): ChatAnswer {
  const ok = a.citations.every((c) => o.sections.some((s) => s.id === c.sectionId) && c.version <= latest(o).version);
  return ok ? a : { text: "근거 대조에 실패해 답변을 보류했어요. 원문을 확인해 주세요.", citations: [], held: true };
}

// ───────── 공고 구조화 (서버 연결 전 대체 파서 — 서버에선 Gemini Flash + JSON 스키마)
const KEYWORD_SKILL: [RegExp, string][] = [
  [/opic/i, "SK-OPIC"],
  [/toeic|토익/i, "SK-TOEIC"],
  [/jlpt/i, "SK-JLPT"],
  [/hsk/i, "SK-HSK"],
  [/delf/i, "SK-DELF"],
  [/sns/i, "SK-SNS"],
  [/python|파이썬/i, "SK-PY-01"],
  [/sql/i, "SK-SQL"],
  [/마케팅/, "SK-MKT"],
  [/콘텐츠/, "SK-CONTENT"],
  [/gmp/i, "SK-GMP"],
  [/회계/, "SK-ACC"],
  [/사업계획/, "SK-BIZPLAN"],
  [/봉사/, "SK-VOL"],
  [/포트폴리오/, "SK-PORT"],
  [/청소년상담사/, "PSY-C-YOUTH"],
  [/집단상담/, "PSY-GROUP"],
  [/상담면접|상담 면접/, "PSY-INTERVIEW"],
  [/임상심리사/, "PSY-C-CLIN"],
  [/직업상담사/, "PSY-C-JOB"],
  [/사회복지사/, "SK-SW-CERT"],
  [/사회적경제|소셜벤처/, "SW-SOCIAL"],
];

export interface Parsed {
  type: OppType;
  title: string;
  status?: ("재학" | "휴학" | "졸업예정")[];
  grades?: number[];
  preferred: string[];
  documents: string[];
  deadline?: string;
  jobs: string[];
  confidence: number;
  unparsed: string[];
}

export function parsePosting(raw: string): Parsed {
  const lines = raw.split(/\n/).map((l) => l.trim()).filter(Boolean);
  const head = lines[0] ?? "";
  const tm = head.match(/^\[(현장실습|창업지원|장학|학사|비교과)\]\s*(.+)$/);
  const type = (tm?.[1] as OppType) ?? "현장실습";
  const title = (tm?.[2] ?? head).replace(/\(가상\)/, "").trim();
  const get = (re: RegExp) => lines.find((l) => re.test(l))?.replace(re, "").replace(/^[:：\s]+/, "");
  const unparsed: string[] = [];
  let found = 0;

  const target = get(/^(지원\s?대상|지원\s?자격)/);
  let status: Parsed["status"];
  let grades: number[] | undefined;
  if (target) {
    found++;
    const st = (["재학", "휴학", "졸업예정"] as const).filter((x) => target.includes(x));
    if (st.length) status = [...st];
    const g = target.match(/(\d)\s*[~\-]\s*(\d)\s*학년/);
    if (g) grades = Array.from({ length: +g[2] - +g[1] + 1 }, (_, i) => +g[1] + i);
  } else unparsed.push("지원 대상");

  const pref = get(/^우대\s?사항/);
  const preferred = pref ? KEYWORD_SKILL.filter(([re]) => re.test(pref)).map(([, id]) => id) : [];
  if (pref) found++;
  else unparsed.push("우대 사항");

  const docs = get(/^제출\s?서류/);
  const documents = docs ? docs.split(/[,，、]/).map((x) => x.trim()).filter(Boolean) : [];
  if (docs) found++;
  else unparsed.push("제출 서류");

  const period = get(/^(접수\s?기간|마감)/);
  let deadline: string | undefined;
  const dm = period?.match(/(\d{4})\.(\d{1,2})\.(\d{1,2}).*?(\d{1,2}):(\d{2})/);
  if (dm) {
    found++;
    const p = (n: string) => n.padStart(2, "0");
    deadline = `${dm[1]}-${p(dm[2])}-${p(dm[3])}T${p(dm[4])}:${dm[5]}:00+09:00`;
  } else unparsed.push("마감일");

  const jobs = JOBS.filter((j) => j.nodes.some((n) => preferred.includes(n.skill))).map((j) => j.id);
  return { type, title, status, grades, preferred, documents, deadline, jobs, confidence: +(found / 4).toFixed(2), unparsed };
}

export { SKILLS };

// ───────── 보유 역량 진단 (가입 직후: 학과·학년 기준 체크 항목과 직무 일치도)
const COMMON_SKILLS = ["SK-TOEIC", "SK-OPIC", "SK-COMP", "SK-PORT", "SK-RESUME"];
const KIND_ORDER = ["어학", "자격증", "프로젝트", "교육", "경험", "역량"] as const;

export const GRADE_STAGE: Record<number, { stage: string; tip: string; focus: string[] }> = {
  1: { stage: "탐색", tip: "관심 활동 몇 개로 진로 후보를 찾는 시기예요. 아직 없는 게 당연해요.", focus: ["교육", "경험"] },
  2: { stage: "역량 쌓기", tip: "목표 직무의 필수·우대 역량을 하나씩 채우는 시기예요.", focus: ["어학", "교육", "프로젝트"] },
  3: { stage: "현장실습", tip: "조건이 맞는 실습을 찾고 서류를 준비하는 시기예요.", focus: ["프로젝트", "자격증", "역량"] },
  4: { stage: "취업·창업", tip: "마감과 정정을 놓치지 않는 게 중요한 시기예요.", focus: ["역량", "자격증", "어학"] },
};
export const gradeStage = (grade: number) => GRADE_STAGE[Math.min(grade, 4)];

export function diagnosisItems(departmentId: string, grade: number) {
  const dept = getDepartment(departmentId);
  const all = jobsFor(departmentId);
  const related = dept && dept.field !== "open" ? all.filter((j) => j.departments || j.fields.includes(dept.field)) : all;
  const ids = new Set<string>(COMMON_SKILLS);
  for (const j of related) for (const n of j.nodes) ids.add(n.skill);
  const focus = gradeStage(grade).focus;
  return KIND_ORDER.map((kind) => ({
    kind,
    focus: focus.includes(kind),
    skills: SKILLS.filter((s) => s.kind === kind && ids.has(s.id)),
  }))
    .filter((g) => g.skills.length)
    .sort((a, b) => Number(b.focus) - Number(a.focus));
}

export function matchJobs(skills: Record<string, string>, departmentId: string) {
  const dept = getDepartment(departmentId);
  return jobsFor(departmentId)
    .map((j) => {
      const have = j.nodes.filter((n) => (skills[n.skill] ?? "none") !== "none").length;
      return { job: j, have, total: j.nodes.length, own: !!j.departments, major: !!dept && j.fields.includes(dept.field) };
    })
    .sort((a, b) => Number(b.own) - Number(a.own) || b.have / b.total - a.have / a.total || Number(b.major) - Number(a.major));
}
