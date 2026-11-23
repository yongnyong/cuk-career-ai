import type { Opportunity, Profile, Skill, TreeSignal } from "./types";

type Observation = NonNullable<Opportunity["discoveryEvidence"]>[number];
type Kind = Observation["kind"];
const normalize = (value: string) => value.normalize("NFKC").trim().replace(/\s+/g, " ").toLowerCase();
const validTerm = /^[a-z0-9가-힣][a-z0-9가-힣 .+#-]{1,47}$/;

function describe(kind: Kind, term: string) {
  if (kind === "credential") return { name: term, action: term + " 취득",
    completion: "발급기관의 자격증 또는 취득 확인서에서 자격명과 취득 결과를 확인하세요." };
  if (kind === "artifact") return { name: term + " 완성", action: term + " 완성",
    completion: term + "의 최종본을 저장하고 공고에 명시된 제출 형식과 대조하세요." };
  return { name: term + " 실무 예제 제작", action: term + " 실무 예제 제작",
    completion: term + "로 목표 직무의 업무 한 가지를 수행하세요. 입력 자료, 다시 열어 편집할 수 있는 원본 파일, 최종 결과물을 함께 저장하세요." };
}

function citedWork(kind: Kind, term: string, hits: Hit[]) {
  // Choose a deliverable from capabilities cited together by independent employers.
  const officeWork = hits.filter(({ observation: { quote } }) =>
    /\bWord\b|워드|문서\s*작성/i.test(quote) && /PowerPoint|파워포인트|프레젠테이션/i.test(quote));
  if (kind === "tool" && officeWork.length >= 2) return { action: term + " 기획 문서·발표자료 제작",
    completion: "목표 직무에서 제안하고 싶은 개선안 하나를 고르세요. 목적·대상·실행 계획을 담은 편집 가능한 기획 문서와 같은 제안을 설명하는 발표 파일을 완성하세요." };
  return describe(kind, term);
}

export function discoveredSkillById(id: string, sourceTerm?: string): Skill | undefined {
  const match = /^AUTO-(tool|credential|artifact)-(.+)$/.exec(id);
  if (!match || !validTerm.test(match[2]) || normalize(match[2]) !== match[2]) return;
  const kind = match[1] as Kind;
  const term = sourceTerm && normalize(sourceTerm) === match[2] ? sourceTerm : match[2];
  return { id, name: describe(kind, term).name, kind: kind === "credential" ? "자격증" : "프로젝트",
    verifiable: kind === "credential" };
}

export function savedDiscoveryOutcome(id: string) {
  const match = /^AUTO-(tool|artifact)-(.+)$/.exec(id);
  if (!match || !validTerm.test(match[2])) return;
  const work = describe(match[1] as Kind, match[2]);
  return { title: work.name, completion: work.completion, label: "완료한 작업물" };
}

function sourceKey(raw: string) {
  try {
    const url = new URL(raw);
    if (!["https:", "http:"].includes(url.protocol)) return;
    for (const key of [...url.searchParams.keys()]) {
      if (/^(utm_|ref$|from$|oem_code$|tracking)/i.test(key)) url.searchParams.delete(key);
    }
    url.searchParams.sort();
    if (url.pathname === "/" && !url.search) return;
    return url.host.toLowerCase() + url.pathname.replace(/\/$/, "") + url.search;
  } catch { return; }
}

interface Hit {
  employer: string; url: string; jobs: string[]; observation: Observation; reference: TreeSignal["reference"];
}

function independent(hits: Hit[]) {
  const employers = new Set<string>();
  const urls = new Set<string>();
  return hits.filter(hit => {
    if (employers.has(hit.employer) || urls.has(hit.url)) return false;
    employers.add(hit.employer);
    urls.add(hit.url);
    return true;
  });
}

export function discoveredSignals(postings: Iterable<Opportunity>, profile: Profile,
  historical: (o: Opportunity) => boolean, jobFamily: (id: string) => string): TreeSignal[] {
  const groups = new Map<string, Hit[]>();
  for (const o of postings) {
    if (!o.discoveryEvidence?.length || !o.reviewed || o.isVirtual || !["채용", "현장실습"].includes(o.type)) continue;
    const mapping = o.employmentMatch;
    const jobs = (mapping ? mapping.namedJobs.length ? mapping.namedJobs : mapping.reviewedJobs : o.jobs).filter(id => id !== "etc");
    const url = sourceKey(o.source.url);
    const employer = normalize(o.org).replace(/\(주\)|주식회사|\s/g, "");
    if (!jobs.length || !url || !employer || /비공개|미공개|미상|미기재|채용대행/.test(employer)) continue;
    for (const entry of o.discoveryEvidence) {
      const term = normalize(entry.term);
      if (entry.scope !== "role" || !validTerm.test(term) || !normalize(entry.quote).includes(term) ||
        !o.sections.some(s => s.id === entry.src && s.text.includes(entry.quote))) continue;
      const id = "AUTO-" + entry.kind + "-" + term;
      const hits = groups.get(id) ?? [];
      hits.push({ employer, url, jobs, observation: entry, reference: { id: o.id, title: o.title, url: o.source.url,
        organization: o.org, version: o.versions[o.versions.length - 1].version, historical: historical(o),
        quote: entry.quote, sectionId: entry.src, scope: "role" } });
      groups.set(id, hits);
    }
  }
  const signals: TreeSignal[] = [];
  for (const [skillId, hits] of groups) {
    hits.sort((a, b) => Number(a.reference.historical) - Number(b.reference.historical) ||
      Number(b.observation.basis === "required") - Number(a.observation.basis === "required") ||
      a.reference.id.localeCompare(b.reference.id));
    const localHits = hits.filter(hit => hit.jobs.includes(profile.jobId));
    const local = independent(localHits);
    if (local.length < 2) continue;
    // A common skill needs a second job family supported independently of this one.
    const family = jobFamily(profile.jobId);
    const localEmployers = new Set(localHits.map(h => h.employer));
    const localUrls = new Set(localHits.map(h => h.url));
    const other = hits.filter(h => !localEmployers.has(h.employer) && !localUrls.has(h.url) &&
      h.jobs.every(job => jobFamily(job) !== family));
    const common = [...new Set(other.flatMap(h => h.jobs))].some(job => independent(other.filter(h => h.jobs.includes(job))).length >= 2);
    const { term, kind } = local[0].observation;
    const { action, completion } = citedWork(kind, term, local);
    for (const hit of local) signals.push({ skillId, basis: hit.observation.basis,
      status: profile.skills[skillId] && profile.skills[skillId] !== "none" ? "matched" : "gap",
      preparation: { kind: kind === "tool" ? "suggested" : "direct", action, completion,
        discovery: { term, domain: common ? "common" : "specialist" } }, reference: hit.reference });
  }
  return signals;
}
