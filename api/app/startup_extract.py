"""Conservative, evidence-backed startup submission extraction. No model credentials needed."""
import re
from datetime import date

from .startup_db import digest


VERSION = "1"
DOCUMENTS = {
    "사업계획서": r"사업\s*계획서",
    "발표자료": r"[Pp]itch\s*[Dd]eck|피치\s*덱|발표\s*자료|[Ii][Rr]\s*자료|투자\s*제안서",
    "시제품": r"\bMVP\b|시제품|프로토타입",
    "참가신청서": r"(?:참가|참여|입주|지원|사업|도전|온라인|창업동아리|멘토링)\s*신청서|참가\s*지원서|신청\s*통합\s*서식",
    "개인정보동의서": r"개인\s*정보[\w\s·ㆍ,・/()]{0,30}동의서",
    "사업자등록증": r"사업자\s*등록증(?:명원)?|사업자\s*등록\s*증명",
    "법인등기부등본": r"법인\s*등기부\s*(?:등본)?",
    "사실증명": r"사실\s*증명(?:원)?(?:\s*\([^)]{0,50}\))?",
    "재학증명서": r"재학\s*증명서|휴학\s*증명서",
    "주민등록초본": r"주민\s*등록\s*(?:초본|등본)",
    "납세증명서": r"(?:국세|지방세|완납|납세)\s*(?:완납\s*)?증명서",
    "견적서": r"(?:비교\s*)?견적서",
    "통장사본": r"통장\s*사본",
    "서약서": r"(?:참가|참여|청렴|보안|윤리)?\s*서약서",
    "팀소개서": r"팀\s*소개서|기업\s*소개서",
    "포트폴리오": r"포트폴리오",
    "가점증빙": r"가점\s*증빙(?:\s*서류)?|우대\s*증빙(?:\s*서류)?|가점\s*확인\s*신청서",
}
PATTERNS = {name: re.compile(pattern) for name, pattern in DOCUMENTS.items()}
SUBMIT = re.compile(r"제출|첨부|구비|접수\s*서류|작성\s*후|업로드|각\s*1\s*부|필수\s*서류")
DOC_HEADING = re.compile(r"^(?:[\d.\s□○■◦-]+)?(?:[가나다라][.)]\s*)?(?:제출\s*(?:서류|자료)|구비\s*서류|신청\s*서류|접수\s*서류)")
HEADING = re.compile(r"^(?:\d+[.)]|[□■]|[가나다라][.)])\s*")
NO_SUBMIT = re.compile(r"제출\s*(?:불필요|하지\s*않|생략)|미제출\s*가능|제외|대필|대신\s*작성|허위|위배|위반|처벌|사업계획서\s*상|기\s*제출|사업계획서에\s*명시|제출서류\s*기반")
DATE = re.compile(r"(?:(20\d{2})\s*[.년/-]\s*)?(\d{1,2})\s*[.월/-]\s*(\d{1,2})(?:\s*[.일])?")


def dates(text, year):
    found = []
    for match in DATE.finditer(text):
        try:
            value = date(int(match[1] or year), int(match[2]), int(match[3])).isoformat()
        except ValueError:
            continue
        found.append(value)
    return found


def application_period(text, year):
    """Keep open-ended, contradictory or missing dates unresolved."""
    lines = text.splitlines()
    hits = []
    for i, line in enumerate(lines):
        if re.search(r"(?:모집|접수|신청)\s*기간", line):
            value = line
            for following in lines[i + 1:i + 4]:
                if len(dates(value, year)) >= 2 or re.search(r"사업개요|조기마감|신청\s*방법|결과\s*발표", following):
                    break
                value += " " + following
            hits.append(value)
    raw = "\n".join(dict.fromkeys(hits))
    parsed = [dates(line, year) for line in hits]
    periods = [values for values in parsed if len(values) >= 2]
    # Closing dates also appear inside application instructions and may be amended there.
    end_candidates = {values[-1] for values in periods}
    for line in lines:
        if "발표" not in line and re.search(r"신청\s*방법|신청\s*마감|접수\s*마감", line):
            values = dates(line, year)
            if values:
                end_candidates.add(values[-1])
    if len(end_candidates) > 1:
        return raw, None, None, "본문의 접수 마감 표현이 달라 원문 확인 필요"
    if periods:
        return raw, periods[0][0], periods[0][-1], None
    return raw, None, None, "접수 기간 확인 필요" if not raw else None


def application_status(start, end, text, today):
    if re.search(r"조기종료|모집\s*종료|접수\s*종료", text):
        return "closed"
    if end and end < today:
        return "closed"
    if start and start > today:
        return "upcoming"
    # Same-day closing time, remaining budget, and early closure require a live check.
    if end and end > today and start:
        return "within_announced_period"
    return "needs_review"


def category(title):
    for pattern, name in (
        (r"해커톤", "교육·멘토링"),
        (r"경진|공모전|챌린지|Challenge", "경진대회·공모전"),
        (r"창업동아리", "창업동아리"),
        (r"입주|보육센터", "공간·보육"),
        (r"시제품|제작터|제조창업", "시제품·제작"),
        (r"멘토링|창업유망팀|해커톤|스쿨|예비창업\s*프로그램", "교육·멘토링"),
    ):
        if re.search(pattern, title, re.I):
            return name
    return "사업화·활동비"


def extract_requirements(source, year, attachments):
    """A filename is a candidate only. Mandatory status requires a submission instruction."""
    lines = source["content"].splitlines()
    if source["kind"] == "template":
        return []
    out = {}
    priorities = {}
    section = ""
    section_line = -1
    applicant_scope = ""
    for i, line in enumerate(lines):
        if DOC_HEADING.search(line):
            section = line
            section_line = i
        elif (HEADING.search(line) or re.search(r"유의\s*사항|주의\s*사항|문의\s*처|선정기업의\s*의무", line)) and not re.match(r"^\s*\d+[.)]\s*\S*(신청서|계획서|증명서)", line):
            section = ""
            applicant_scope = ""
        if i - section_line > 25:
            section = ""
            applicant_scope = ""
        scope = re.sub(r"\s", "", "".join(lines[max(0, i - 1):i + 1]))
        if section and scope in ("예비창업자", "개인및법인사업자"):
            applicant_scope = scope
        if NO_SUBMIT.search(line):
            continue
        is_attachment = source["kind"] in ("attachment_index", "template")
        for doc_type, pattern in PATTERNS.items():
            match = pattern.search(line)
            if not match:
                continue
            if is_attachment and (doc_type == "시제품" or re.search(r"포스터|매뉴얼|소개자료|공고문", line)):
                continue
            if not is_attachment and not (SUBMIT.search(line) or section):
                continue
            # Within an attachment index, manuals and eligibility guides aren't deliverables.
            if is_attachment and re.search(r"매뉴얼|작성\s*안내|공고문|소개자료|질의응답|제출\s*목록|목록\s*안내", line):
                continue
            stage = "unknown" if is_attachment else "application"
            context = f"{section}\n{line}" if section else line
            if re.search(r"본선|발표\s*(?:평가|심사)|2차|진출", context):
                stage = "finalist"
            if re.search(r"협약|선정\s*후|최종\s*(?:선정|선발)|선발\s*직후", context):
                stage = "agreement"
            following = [other.start() for other_type, other_pattern in PATTERNS.items() if other_type != doc_type
                         for other in other_pattern.finditer(line) if other.start() >= match.end()]
            nearby = line[match.start():min(following) if following else len(line)]
            necessity = "needs_review" if is_attachment else "required"
            condition = ""
            if re.search(r"선택|자율|희망\s*시", nearby):
                necessity = "optional"
            elif re.search(r"해당\s*시|해당자|보유\s*시|보유자|경우|창업기업의", context) or doc_type == "가점증빙":
                necessity, condition = "conditional", line
            elif stage in ("finalist", "agreement"):
                necessity, condition = "conditional", "본선·발표평가 대상 시" if stage == "finalist" else "선정·협약 단계 진입 시"
            if applicant_scope and doc_type in ("사업자등록증", "법인등기부등본", "사실증명") and not is_attachment:
                necessity, condition = "conditional", applicant_scope
            if doc_type in ("사업자등록증", "법인등기부등본", "사실증명", "납세증명서") and not condition and not is_attachment:
                necessity = "needs_review"
                condition = "증빙서류의 적용 대상 확인 필요"
            # A schedule line mentioning optional MVP must not make the preceding Pitch Deck optional.
            if re.search(r"필수", nearby) and necessity != "needs_review":
                necessity = "conditional" if stage in ("finalist", "agreement") or condition else "required"
            if is_attachment:
                necessity, stage, condition = "needs_review", "unknown", "첨부 양식의 적용 대상·제출 의무 확인 필요"
            deadline_line = line if dates(line, year) else section
            deadline_values = dates(deadline_line, year)
            template = next((a["url"] for a in attachments
                             if pattern.search(a["name"]) and a["role"] == "template"), None)
            normalized_type = doc_type
            if doc_type == "사실증명":
                qualifier = re.search(r"사업자등록사실여부|총사업자등록내역", re.sub(r"\s", "", line))
                if qualifier:
                    normalized_type = qualifier[0] + "증명"
            row = {
                "id": digest(f"{source['id']}|{normalized_type}|{stage}"),
                "posting_id": source["posting_id"], "source_id": source["id"],
                "document_type": normalized_type, "original_name": match.group().strip(),
                "necessity": necessity, "stage": stage, "condition_text": condition,
                "deadline_text": deadline_line if deadline_values else None,
                "deadline_date": deadline_values[-1] if deadline_values else None,
                "deadline_precision": "day" if deadline_values else None,
                "evidence_quote": line, "evidence_line": i + 1,
                "template_url": template,
                "extraction_method": "filename_candidate" if is_attachment else "submission_rule",
            }
            key = (normalized_type, stage)
            # Prefer explicit obligation over a mention in a schedule or a list of attachments.
            priority = (bool(re.search(r"필수|선택|해당\s*시", nearby)), bool(deadline_values))
            if priority > priorities.get(key, (-1, -1)):
                out[key] = row
                priorities[key] = priority
    return list(out.values())
