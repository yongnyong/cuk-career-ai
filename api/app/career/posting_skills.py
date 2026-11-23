"""Extract explicit skill clauses from saved posting text with exact citations."""
import json
import re
from pathlib import Path
from .discovery import named_terms

HEADINGS = re.compile(
    r'(?P<preferred>우대\s*(?:조건|사항|역량(?:\s*및\s*경험)?|요건)|이런\s*분이면\s*더욱\s*좋습니다)'
    r'|(?P<required>자격\s*요건|지원\s*자격|필수\s*(?:요건|역량(?:\s*및\s*경험)?|조건)|필요\s*역량|이런\s*분을\s*찾)'
    r'|(?P<documents>제출해야\s*할\s*서류|(?:필수|선택)\s*제출\s*서류|제출\s*서류)'
    r'|(?P<stop>로그인|이\s*기업과\s*나의|접수기간|기업\s*정보|복리후생|복지제도|채용\s*프로세스|전형\s*절차|근무\s*조건|혜택\s*및\s*복지'
    r'|주요\s*업무|담당\s*업무|\s스킬\s*[,：:])'
)
# Competencies and certificates have separate aliases. Office proficiency does
# not establish a Computer Specialist certificate or a language test result.
WEB_CATALOG = json.loads(Path(__file__).with_name('web_catalog.json').read_text(encoding='utf-8'))
CERTIFICATE_PATTERNS = WEB_CATALOG['credentialPatterns']
SKILL_PATTERNS = {
    **CERTIFICATE_PATTERNS,
    'SK-PY-01': r'(?<![A-Za-z])Python(?![A-Za-z])|파이썬',
    'SK-SQL': r'(?<![A-Za-z])SQL(?![A-Za-z])',
    'SK-SQLD': r'(?<![A-Za-z])SQLD(?![A-Za-z])',
    'SK-ADSP': r'(?<![A-Za-z])ADsP(?![A-Za-z])',
    'SK-INFO-PE': r'정보처리기사',
    'SK-COMP': r'컴퓨터활용능력\s*[12]\s*급|컴활\s*[12]\s*급',
    'SK-TOEIC': r'(?<![A-Za-z])TOEIC(?![\s-]*Speaking|[A-Za-z])|토익(?![\s-]*스피킹)',
    'SK-TOEIC-SPEAKING': r'(?<![A-Za-z])TOEIC[\s-]*Speaking(?![A-Za-z])|토익[\s-]*스피킹',
    'SK-OPIC': r'(?<![A-Za-z])OPIc(?![A-Za-z])|오픽',
    'SK-JLPT': r'(?<![A-Za-z])JLPT(?![A-Za-z])',
    'SK-HSK': r'(?<![A-Za-z])HSK(?![A-Za-z])',
    'SK-PPT': r'프[리레]젠테이션\s*(?:능력|역량)|기획서\s*작성|제안서\s*작성',
    'SK-WRITE': r'글쓰기|카피라이팅|카피\s*작성',
    'SK-VIDEO': r'영상\s*편집|프리미어\s*프로|Premiere\s*Pro',
    'SK-SNS': r'SNS\s*(?:채널\s*)?운영|소셜\s*미디어\s*운영',
    'SK-DESIGN-TOOL': r'(?<![A-Za-z])(?:Auto\s*CAD|CAD|SketchUp|Rhino)(?![A-Za-z])',
    'SK-ACC': r'전산회계\s*1\s*급',
    'ACC-C-CPA': r'공인회계사(?!\s*1차)',
    'ACC-C-CTA': r'세무사(?!\s*1차)',
    'SK-TRADE': r'국제무역사',
    'SK-BLS': r'(?<![A-Za-z])BLS(?![A-Za-z])\s*(?:자격|provider|이수|수료)',
    'SK-INTERIOR': r'실내건축기사',
    'SK-DIET': r'영양사\s*(?:면허|자격)',
}
NEGATED = re.compile(r'없어도|무관|불필요|제한\s*없|필요\s*없|필요하지\s*않|필수.{0,6}(?:아닌|아니|아님|아닙|않)')
ALTERNATIVE = re.compile(r'또는|혹은|\bor\b|중\s*(?:하나|1개|택)|대체|환산', re.I)

# The observation key describes the employer's wording only. The student-facing
# recommendation (e.g. practicing SQL or preparing SQLD) is selected later.
CAPABILITIES = {
    'business_document': r'문서\s*작성\s*(?:능력|역량|우수|능숙)|보고서\s*작성\s*(?:능력|역량|우수|능숙)',
    'spreadsheet': r'엑셀|(?<![A-Za-z])Excel(?![A-Za-z])',
    'sql': SKILL_PATTERNS['SK-SQL'],
    'presentation': r'프[리레]젠테이션\s*(?:능력|역량|자료\s*(?:개발|제작))|발표\s*(?:능력|역량)|(?:기획서|제안서)\s*작성',
    'writing': SKILL_PATTERNS['SK-WRITE'],
    'cad': r'(?<![A-Za-z])(?:Auto\s*CAD|CAD)(?![A-Za-z])',
    'analysis': r'(?:데이터|통계)\s*분석\s*(?:력|능력|역량|경험|능숙)|통계분석[·ㆍ]리서치\s*능숙',
    'premiere_editing': r'프리미어\s*프로|\bPremiere\s*Pro\b',
    'after_effects': r'애프터\s*이펙트|에프터\s*이펙트|\bAfter\s+Effects\b',
    'power_bi': r'(?<![a-z])Power\s*BI(?![a-z])',
    **WEB_CATALOG['postingProjectPatterns'],
}
ARTIFACTS = {
    'proposal': r'(?:기획서|제안서)',
    'writing_sample': r'글쓰기\s*샘플|작문\s*(?:샘플|예시)|기고문|본인(?:이)?\s*작성(?:한)?\s*(?:기사|원고)|카피\s*샘플',
    'drawing': r'(?:설계\s*)?도면',
    'portfolio': r'포트폴리오|작품집',
}
CREDENTIALS = {
    **{'credential:' + skill: pattern for skill, pattern in CERTIFICATE_PATTERNS.items()},
    'credential:SK-FINANCE-MANAGER': r'재경관리사',
    'credential:SK-NURSING-LICENSE': r'간호사\s*면허',
    'credential:SK-CHILDCARE-2': r'보육교사\s*2\s*급',
    'credential:SK-KOREAN-TEACHER-2': r'한국어교원\s*2\s*급',
    'credential:SK-TOEIC-SPEAKING': SKILL_PATTERNS['SK-TOEIC-SPEAKING'],
    'credential:SK-HYGIENIST': r'위생사',
    'credential:SK-FOOD-ENGINEER': r'식품기사',
    'credential:SK-FOOD-INDUSTRIAL': r'식품산업기사',
    'sql_certificate': SKILL_PATTERNS['SK-SQLD'],
    **{'credential:' + skill: SKILL_PATTERNS[skill] for skill in (
        'SK-ADSP', 'SK-INFO-PE', 'SK-ACC', 'ACC-C-CPA', 'ACC-C-CTA', 'SK-TRADE',
        'SK-BLS', 'SK-INTERIOR', 'SK-DIET',
    )},
    'credential:ENV-C-AIR': r'대기환경기사', 'credential:ENV-C-WATER': r'수질환경기사',
    'credential:ENV-C-SAFE': r'산업안전기사', 'credential:ICE-C-ELECTRIC': r'전기기사',
    'credential:SK-ELEC-PE': r'전자기사', 'credential:SW-C-1': r'사회복지사\s*1\s*급',
    'credential:SK-SW-CERT': r'사회복지사\s*2\s*급',
}
REGISTERED_TERMS = tuple(re.compile(pattern, re.I) for pattern in {
    *SKILL_PATTERNS.values(), *CAPABILITIES.values(), *CREDENTIALS.values(), *ARTIFACTS.values()})
REGISTERED_NAMES = {re.sub(r'\s+', '', skill['name']).casefold() for skill in WEB_CATALOG['skills']}
SQL_PROJECT = re.compile(
    r'(?<![A-Za-z])SQL(?![A-Za-z])[^,;·\n]{0,40}(?:프로젝트|분석(?:한|해\s*본)?\s*(?:경험|보고서)|포트폴리오)'
    r'|(?:프로젝트|분석\s*경험)[^,;·\n]{0,32}(?<![A-Za-z])SQL(?![A-Za-z])', re.I)
FACT_NEGATION = re.compile(
    r'아니(?:어|여|라)|아님|필수.{0,6}않|(?:보유|제출|소지).{0,4}않|없어도|없이도?|미보유|미제출|불가|불필요|제외|해당자|선택|권장하지|자유\s*제출|취득\s*예정|1차\s*합격')
FACT_BOUNDARY = re.compile(r'[\n\r•●;。]|\s+[·]\s+|\s+-\s+(?=[A-Za-z])|(?<=[다요])\.\s+|\s+(?=[a-z]\.\s*(?:필수|선택)\s*[:：])')
EXPLICIT_BASIS = {'우대': 'preferred', '필수': 'required'}
REVIEW_BASIS = {'우대': 'preferred', 'preferred': 'preferred',
                'required': 'required', '지원자격 기재': 'required'}


def _match_keys(patterns, text):
    return {key for key, pattern in patterns.items() if re.search(pattern, text, re.I)}


def has_multiple_roles(title, text):
    if re.search(r'각\s*(?:부문|분야)|(?:부문|분야|직무)별|직무.{0,60}직무', title):
        return True
    # Explicit role names on both sides avoid interpreting 신입/경력 as multiple roles.
    role = r'(?:개발|영업|재무|구매|디자인|마케팅|기획|연구|생산|보안|물류)'
    if re.search(role + r'\s*[/·ㆍ]\s*' + role, title) or re.search(r'직무별\s*상[이세]', text):
        return True
    listing = re.search(r'모집분야\s+([^\n]{1,55},[^\n]{1,55}?)\s*모집인원', text)
    if not listing:
        return False
    # A listing can repeat the same occupation for junior and experienced applicants.
    occupations = [re.sub(r'\s+(?:신입|경력)(?:직)?$', '', value.strip())
                   for value in listing[1].split(',')]
    return len(set(occupations)) > 1


def _observation_keys(clause, documents):
    submission = documents or bool(re.search(r'제출|첨부|지참', clause))
    if submission:
        for key in sorted(_match_keys(ARTIFACTS, clause)):
            yield key
    if documents:
        return
    credentials = _match_keys(CREDENTIALS, clause)
    if len(credentials) > 1 and '/' in clause:
        credentials.clear()
    keys = _match_keys(CAPABILITIES, clause) | credentials
    if SQL_PROJECT.search(clause):
        keys.discard('sql')
        keys.add('sql_project')
    if not re.search(r'자격|보유|소지|합격', clause):
        keys.difference_update(('credential:ACC-C-CPA', 'credential:ACC-C-CTA'))
    for key in sorted(keys):
        yield key


def _blocks(text):
    headings = list(HEADINGS.finditer(text))
    prefix = text[:headings[0].start()] if headings else text
    # Outside labeled sections, require the clause to explicitly say 필수/우대.
    yield prefix, None, False
    for index, heading in enumerate(headings):
        if heading.lastgroup == 'stop':
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.end():min(end, heading.end() + 1800)]
        if heading.lastgroup == 'documents':
            if '선택' not in heading[0]:
                required = '필수' in heading[0] or '제출해야' in heading[0]
                yield block, 'required' if required else None, True
        else:
            yield block, heading.lastgroup, False


def _source_clauses(text, reviewed):
    blocks = [(block, basis, documents, None) for block, basis, documents in _blocks(text)]
    for row in reviewed:
        item = dict(row)
        basis = REVIEW_BASIS.get(item['status'])
        if basis and item.get('text_type') == 'extracted':
            blocks.append((item['original_text'], basis, False, item['item']))
    for block, basis, documents, item_name in blocks:
        clauses = [part.strip() for part in FACT_BOUNDARY.split(block) if part.strip()]
        optional = False
        for index, clause in enumerate(clauses):
            if re.match(r'^(?:[a-z]\.[ ]*)?(?:선택|자유\s*제출)', clause):
                optional = True
            elif re.match(r'^(?:[a-z]\.[ ]*)?필수', clause):
                optional = False
            # An open-ended choice list cannot establish individual requirements.
            if re.search(r'(?:다음|아래)(?:\s*자격증?)?\s*중\s*(?:하나|택|1)', clause):
                break
            if (optional or not 2 <= len(clause) <= 400 or FACT_NEGATION.search(clause)
                    or NEGATED.search(clause) or ALTERNATIVE.search(clause)):
                continue
            before = clauses[index - 1] if index else ''
            after = clauses[index + 1] if index + 1 < len(clauses) else ''
            if re.search(r'(?:또는|혹은|\bor)\s*$', before, re.I) or re.match(r'(?:또는|혹은|or\b)', after, re.I):
                continue
            markers = {kind for word, kind in EXPLICIT_BASIS.items() if word in clause}
            if re.search(r'\b(?:mandatory|is\s+(?:a\s+)?must|is\s+required)\b', clause, re.I):
                markers.add('required')
            if re.search(r'\bis\s+preferred\b', clause, re.I):
                markers.add('preferred')
            if len(markers) > 1:
                continue
            observed_basis = next(iter(markers), basis)
            if observed_basis:
                yield clause, observed_basis, documents, item_name


def extract_preparation_evidence(text, reviewed=(), *, multi_role=False):
    scope = 'posting' if multi_role else 'role'
    results = {}
    for clause, basis, documents, item_name in _source_clauses(text, reviewed):
        allowed = set(_observation_keys(item_name, documents)) if item_name else None
        for key in _observation_keys(clause, documents):
            if allowed is None or key in allowed:
                results.setdefault((key, basis, clause), {
                    'key': key, 'basis': basis, 'quote': clause, 'scope': scope})
    return list(results.values())


def attach_preparation_evidence(data, text, reviewed=(), *, multi_role=False):
    """Attach quoted observations to the public posting and reuse identical source sections."""
    observations = extract_preparation_evidence(text, reviewed, multi_role=multi_role)
    discovery = []
    seen = set()
    if not multi_role:
        for clause, basis, documents, _ in _source_clauses(text, ()):
            for kind, term in named_terms(clause, documents):
                key = (kind, term.casefold(), clause, basis)
                if (key in seen or re.sub(r'\s+', '', term).casefold() in REGISTERED_NAMES
                        or any(pattern.fullmatch(term) for pattern in REGISTERED_TERMS)):
                    continue
                seen.add(key)
                discovery.append(dict(kind=kind, term=term, basis=basis, quote=clause, scope='role'))
    sections = data.setdefault('sections', [])
    sources = {section['text']: section['id'] for section in sections}
    section_ids = {section['id'] for section in sections}
    index = 0
    for row in observations + discovery:
        quote = row['quote']
        if quote not in sources:
            index += 1
            while f'준비{index}' in section_ids:
                index += 1
            source_id = f'준비{index}'
            sources[quote] = source_id
            sections.append({'id': source_id, 'title': '준비 근거', 'text': quote})
        row['src'] = sources[quote]
    data['preparationEvidence'] = observations
    if discovery:
        data['discoveryEvidence'] = discovery
    else:
        data.pop('discoveryEvidence', None)
    return data


def extract_skill_evidence(text, reviewed=(), *, multi_role=False):
    unique = {}
    scope = 'posting' if multi_role else 'role'
    for clause, basis, documents, item_name in _source_clauses(text, reviewed):
        if documents:
            if '포트폴리오' in clause and item_name is None:
                unique.setdefault(('SK-PORT', basis, clause), {
                    'skill': 'SK-PORT', 'basis': basis, 'quote': clause, 'scope': scope})
            continue
        if '/' in clause and len(_match_keys(SKILL_PATTERNS, clause)) > 1:
            continue
        for skill, pattern in SKILL_PATTERNS.items():
            hit = re.search(pattern, clause, re.I)
            if hit is None or (item_name and not re.search(pattern, item_name, re.I)):
                continue
            if skill in ('ACC-C-CPA', 'ACC-C-CTA') and not re.search(r'자격|보유|소지|합격', clause):
                continue
            minimum = None
            tail = clause[hit.end():]
            if skill == 'CERT-TAX':
                grade = re.match(r'\s*([12])\s*급', tail)
                if grade and (grade[1] == '1' or re.match(r'\s*이상', tail[grade.end():])):
                    minimum = grade[1] + '급'
            if skill == 'SK-TOEIC':
                score = re.match(r'\s*(\d{3})\s*점?\s*이상', tail)
                if score and 10 <= int(score[1]) <= 990:
                    minimum = score[1]
            if skill == 'SK-OPIC':
                grade = re.match(r'\s*(IM[123]|IH|AL)\s*(?:이상)?', tail, re.I)
                if grade:
                    minimum = grade[1].upper()
            if skill == 'SK-TOEIC-SPEAKING':
                grade = re.match(r'\s*(NL|NM|NH|IL|IM[123]|IH|AL|AM|AH|\d{2,3})\s*점?\s*이상', tail, re.I)
                if grade:
                    minimum = grade[1].upper()
            if skill == 'SK-JLPT':
                grade = re.match(r'\s*(N[1-5])', tail, re.I)
                if grade:
                    minimum = grade[1].upper()
            unique.setdefault((skill, basis, clause), {
                'skill': skill, 'basis': basis, 'quote': clause, 'scope': scope,
                **({'minimum': minimum} if minimum else {})})
    return list(unique.values())
