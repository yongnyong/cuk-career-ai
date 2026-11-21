"""Extract a startup node catalog from stored submission instructions, forms and rubrics.

python -m app.startup_nodes
python -m app.startup_nodes --posting cuk-277825
python -m app.startup_nodes --export startup-nodes.json
"""
import argparse
import json
import re
from pathlib import Path

from .startup_db import DEFAULT_DB, connect, digest, initialize


VERSION = "1"
# Canonical labels only become nodes when supported by the stored sources.
DOCUMENTS = {
    "사업계획서": ("business-plan", "사업계획서 작성", "artifact", "사업계획서 초안과 공고별 양식 점검", "SK-BIZPLAN"),
    "발표자료": ("pitch-deck", "발표자료·피치덱 제작", "artifact", "발표자료 파일과 해당 공고의 제출 규격 점검", "SK-IR"),
    "시제품": ("prototype", "시제품·MVP 제작", "artifact", "확인 가능한 시제품 또는 실행·시연 링크", "SK-MVP"),
    "팀소개서": ("team-introduction", "팀·기업 소개서 작성", "artifact", "팀 또는 기업 소개 자료", None),
    "포트폴리오": ("portfolio", "사업 포트폴리오 정리", "artifact", "실제 수행한 프로젝트와 성과를 정리한 자료", "SK-PORT"),
    "참가신청서": ("application", "공고별 참가신청서 작성", "application", "해당 공고의 지정 양식 또는 온라인 신청 내용", None),
}
TOPICS = [
    ("item", "창업 아이템 소개 작성", r"창업아이템소개|아이템요약", "아이템명, 핵심가치와 제품·서비스 소개문"),
    ("problem", "고객 문제·개발 필요성 정리", r"문제인식|개발배경|개발필요성|해결의시급성", "해결할 문제와 해결 필요성을 설명한 문서"),
    ("target-customer", "목표 고객 정의", r"목표고객|대상고객|타깃고객|타겟고객", "대상 고객과 해당 고객의 문제를 정리한 문서"),
    ("market", "시장·경쟁 현황 조사", r"시장분석|시장규모|시장성|시장현황|경쟁현황", "출처가 포함된 시장·경쟁 현황 조사 자료"),
    ("customer-validation", "고객·시장 검증계획 작성", r"고객시장검증|고객검증|시장검증계획", "검증할 가설, 대상, 방법과 관찰 항목을 정리한 계획"),
    ("differentiation", "제품·서비스 차별성 정리", r"차별성|차별화|경쟁력확보|경쟁우위", "경쟁 대안과 제품·서비스 차별점을 비교한 자료"),
    ("feasibility", "제품 구현·개발계획 작성", r"실현가능성|개발방법|개선방법|개발계획|제작방법", "제품·서비스의 개발 방법과 실행 가능성을 설명한 계획"),
    ("business-model", "수익모델·비즈니스 모델 정리", r"수익모델|비즈니스모델", "고객, 제공가치와 수익 발생 방식을 정리한 문서"),
    ("market-entry", "시장 진입전략 수립", r"시장진입|시장진출|판매전략|마케팅전략", "초기 고객 확보와 판매·유통 경로를 정리한 전략"),
    ("funding", "자금조달 계획 작성", r"자금조달|투자유치계획", "필요 자금과 조달 방법을 정리한 계획"),
    ("team-capability", "팀 역할·보유역량 정리", r"조직구성|팀역량|대표자및팀|팀\(기업\)구성|기술역량과노하우", "기존 팀원의 역할과 과제 수행 역량을 정리한 자료"),
    ("execution", "사업화 실행계획 작성", r"사업화전략|선정이후활동계획|사업화실행", "사업화를 위한 활동과 실행 방법을 정리한 계획"),
    ("schedule", "개발·사업 추진일정 작성", r"추진일정|개발일정|사업추진계획", "단계별 활동과 일정이 담긴 추진표"),
    ("budget", "사업비 사용계획 작성", r"자금집행계획|사업비활용계획|사업비사용계획|창업자금운용", "지원금·자기부담금의 사용 항목과 배분표"),
    ("cost-breakdown", "비목별 예산 산출", r"비목별사업비|예산산출|산출내역", "비용 항목별 단가·수량과 산출 근거표"),
    ("regional-value", "지역자원·지원동기 정리", r"지역이해도|지역특화콘텐츠기획력|지역자원", "해당 지역자원의 활용 방안과 지원 동기를 설명한 문서"),
    ("item-images", "아이템 이미지·비교자료 준비", r"아이템이미지|유사아이템사진", "아이템을 설명하는 이미지와 비교 자료"),
    ("social-impact", "사회·환경 기여효과 정리", r"사회적가치|사회적기여|탄소중립|사회경제적", "해당 사업이 요구하는 사회·환경 기여효과 설명 자료"),
]
COMPILED_TOPICS = [(key, title, re.compile(pattern), completion) for key, title, pattern, completion in TOPICS]
FORM_HEADING = re.compile(r"^\s*\d+[.)]\s*([^\n]{2,80})$")
FORM_END = re.compile(r"\[제\d+호\s*서식\].*(동의|서약|가점)")
EVALUATION_HEADING = re.compile(r"평가(?:항목|지표)|심사(?:기준|지표)|선정기준")
BUSINESS_FIELD = re.compile(r"사업|아이템|제품|서비스|시장|고객|수익|판매|마케팅|브랜드|기술|지식재산|특허|실증|성과|역량|재무|예산|자금|문제|해결|지역|가치|조직|일정")
ADMIN_FIELD = re.compile(r"성명|생년|연락처|전화|주소|인적\s*사항|지역\s*신청|동의|서약|가점|서식")


def document_node(document_type):
    definition = DOCUMENTS.get(document_type)
    if definition:
        key, title, kind, completion, skill = definition
    else:
        key, title, kind = digest(document_type)[:16], document_type + " 준비", "certificate"
        completion, skill = "해당 공고의 적용 대상과 발급·제출 기준을 확인한 서류", None
    return {"id": "SU-DOC-" + key, "title": title, "kind": kind,
            "completion": completion, "related_skill_id": skill, "extractor_version": VERSION}


def evidence(node_id, source, basis, quote, line, end_line=None, requirement=None):
    requirement = requirement or {}
    page = None
    for match in re.finditer(r"\[PDF page (\d+)\]", "\n".join(source["content"].splitlines()[:line])):
        page = int(match[1])
    return {
        "id": digest(f"{node_id}|{source['id']}|{basis}|{line}|{requirement.get('id', '')}"),
        "node_id": node_id, "posting_id": source["posting_id"], "source_id": source["id"],
        "requirement_id": requirement.get("id"), "basis": basis,
        "necessity": requirement.get("necessity", "unspecified"),
        "stage": requirement.get("stage", "unknown"),
        "condition_text": requirement.get("condition_text", ""),
        "deadline_date": requirement.get("deadline_date"), "quote": quote,
        "start_line": line, "end_line": end_line or line, "source_page": page,
        "review_status": requirement.get("review_status", "unreviewed"),
    }


def topic_sections(source):
    """Yield only form headings or short, explicitly announced rubric sections."""
    lines = source["content"].splitlines()
    evaluation_until = -1
    for i, line in enumerate(lines):
        compact = re.sub(r"\s", "", line)
        if source["kind"] == "template":
            if FORM_END.search(line):
                break
            if FORM_HEADING.match(line):
                yield i + 1, line, "form_section"
            continue
        if re.match(r"^\s*第?제\d+조", compact):
            evaluation_until = -1
        elif len(compact) < 100 and EVALUATION_HEADING.search(compact):
            evaluation_until = i + 40
        elif re.match(r"^\s*(?:□|[ⅠⅡⅢⅣⅤⅥⅦ]+)\s*", line) and not re.search(r"평가|심사", line):
            evaluation_until = -1
        if i <= evaluation_until:
            yield i + 1, line, "evaluation"


def build_catalog(db):
    sources = {row["id"]: dict(row) for row in db.execute("SELECT * FROM sources WHERE current=1 ORDER BY id")}
    nodes, references, edges = {}, {}, set()
    roots_by_posting = {}
    for raw in db.execute("SELECT * FROM submission_requirements ORDER BY id"):
        requirement = dict(raw)
        source = sources.get(requirement["source_id"])
        if source is None or requirement["review_status"] == "rejected":
            continue
        node = document_node(requirement["document_type"])
        nodes[node["id"]] = node
        reference = evidence(node["id"], source, "submission", requirement["evidence_quote"],
                             requirement["evidence_line"], requirement=requirement)
        references[reference["id"]] = reference
        if requirement["necessity"] != "needs_review":
            roots_by_posting.setdefault(requirement["posting_id"], {})[requirement["document_type"]] = node["id"]
    for source in sources.values():
        if source["kind"] not in ("pdf", "template", "html"):
            continue
        roots = roots_by_posting.get(source["posting_id"], {})
        parents = [roots[key] for key in ("사업계획서", "발표자료") if key in roots]
        if source["kind"] == "template":
            template_name = db.execute("SELECT name FROM attachments WHERE posting_id=? AND url=?", (source["posting_id"], source["url"])).fetchone()
            name = template_name[0] if template_name else ""
            parent_type = "사업계획서" if "사업계획서" in name else "참가신청서"
            parents = [roots[parent_type]] if parent_type in roots else []
        elif not parents and "참가신청서" in roots:
            parents = [roots["참가신청서"]]
        seen = set()
        lines = source["content"].splitlines()
        for line_number, line, basis in topic_sections(source):
            compact = re.sub(r"\s|[·ㆍx×]", "", line)
            matches = [(key, title, completion, False) for key, title, pattern, completion in COMPILED_TOPICS
                       if pattern.search(compact)]
            # An unfamiliar business field can extend the pool without adding a
            # dictionary entry. It remains a review candidate until interpreted.
            if basis == "form_section" and not matches and BUSINESS_FIELD.search(compact) and not ADMIN_FIELD.search(compact):
                label = FORM_HEADING.match(line)[1].strip()
                key = "field-" + digest(re.sub(r"\s", "", label))[:16]
                matches.append((key, label + " 작성", f"해당 공고 양식의 {label} 항목 작성본", True))
            for key, title, completion, candidate in matches:
                if key in seen:
                    continue
                seen.add(key)
                node_id = "SU-PREP-" + key
                nodes[node_id] = {"id": node_id, "title": title, "kind": "preparation",
                                  "completion": completion, "related_skill_id": None, "extractor_version": VERSION}
                end_line = min(line_number + 2, len(lines))
                quote = "\n".join(lines[line_number - 1:end_line])
                reference = evidence(node_id, source, basis, quote, line_number, end_line)
                if candidate:
                    reference["necessity"] = "needs_review"
                    reference["condition_text"] = "신규 양식 항목의 의미와 완료 기준 검토 필요"
                references[reference["id"]] = reference
                relation = "form_section" if basis == "form_section" else "evaluation_preparation"
                edges.update((parent, node_id, reference["id"], relation) for parent in parents)
    return nodes, references, edges


def rebuild_nodes(db):
    """Replace the derived graph in a single transaction after successfully extracting it."""
    with db:
        db.execute("BEGIN IMMEDIATE")
        nodes, references, edges = build_catalog(db)
        db.execute("DELETE FROM startup_node_edges")
        db.execute("DELETE FROM startup_node_evidence")
        db.execute("DELETE FROM startup_nodes")
        for table, rows in (("startup_nodes", nodes.values()), ("startup_node_evidence", references.values())):
            for row in rows:
                keys = list(row)
                db.execute(f"INSERT INTO {table}({','.join(keys)}) VALUES({','.join('?' for _ in keys)})", list(row.values()))
        db.executemany("INSERT INTO startup_node_edges(parent_id,child_id,evidence_id,relation) VALUES(?,?,?,?)", sorted(edges))


def load_graph(db, posting_ids=(), include_review=False):
    """Keep obligation, stage and deadline on each notice reference, never on a shared node."""
    rows = db.execute(
        "SELECT e.*,p.title AS posting_title,p.source_url,p.application_status,s.url AS evidence_url "
        "FROM startup_node_evidence e JOIN sources s ON s.id=e.source_id AND s.current=1 "
        "JOIN postings p ON p.id=e.posting_id ORDER BY e.node_id,e.posting_id,e.id"
    )
    references = [dict(row) for row in rows
                  if (not posting_ids or row["posting_id"] in posting_ids)
                  and (include_review or row["necessity"] != "needs_review")]
    by_node = {}
    for reference in references:
        by_node.setdefault(reference["node_id"], []).append(reference)
    nodes = []
    for row in db.execute("SELECT * FROM startup_nodes ORDER BY kind,id"):
        refs = by_node.get(row["id"])
        if not refs:
            continue
        nodes.append({**dict(row), "posting_count": len({r["posting_id"] for r in refs}),
                      "references": refs})
    valid_ids, evidence_ids = {node["id"] for node in nodes}, {r["id"] for r in references}
    edges = [dict(row) for row in db.execute("SELECT * FROM startup_node_edges ORDER BY parent_id,child_id,evidence_id")
             if row["parent_id"] in valid_ids and row["child_id"] in valid_ids and row["evidence_id"] in evidence_ids]
    return {"extractor_version": VERSION, "nodes": nodes, "edges": edges,
            "summary": {"nodes": len(nodes), "preparation_nodes": sum(n["kind"] == "preparation" for n in nodes),
                        "evidence_records": len(references), "edges": len(edges),
                        "postings": len({r["posting_id"] for r in references})}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--posting", action="append", default=[])
    parser.add_argument("--include-review", action="store_true")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error("Collect startup notices before extracting nodes")
    if args.db.resolve() in {DEFAULT_DB.with_name("career.db"), DEFAULT_DB.with_name("dev.db")}:
        parser.error("Use the dedicated startup database")
    initialize(args.db)
    with connect(args.db) as db:
        rebuild_nodes(db)
        graph = load_graph(db, args.posting, args.include_review)
    if args.export:
        args.export.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**graph["summary"], "catalog": [{"id": n["id"], "title": n["title"], "kind": n["kind"],
                                                   "postings": n["posting_count"]} for n in graph["nodes"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
