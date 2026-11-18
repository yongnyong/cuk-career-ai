"""Extract explicit skill clauses from saved posting text with exact citations."""
import re

HEADINGS = re.compile(
    r'(?P<preferred>우대\s*(?:조건|사항|역량(?:\s*및\s*경험)?|요건)|이런\s*분이면\s*더욱\s*좋습니다)'
    r'|(?P<required>자격\s*요건|지원\s*자격|필수\s*(?:요건|역량(?:\s*및\s*경험)?|조건)|필요\s*역량|이런\s*분을\s*찾)'
    r'|(?P<documents>제출해야\s*할\s*서류|필수\s*제출\s*서류|제출서류)'
    r'|(?P<stop>로그인|이\s*기업과\s*나의|접수기간|기업\s*정보|복리후생|복지제도|채용\s*프로세스|전형절차|근무\s*조건|혜택\s*및\s*복지)'
)
# Competencies and certificates have separate aliases. Office proficiency does
# not establish a Computer Specialist certificate or a language test result.
SKILL_PATTERNS = {
    'SK-PY-01': r'(?<![A-Za-z])Python(?![A-Za-z])|파이썬',
    'SK-SQL': r'(?<![A-Za-z])SQL(?![A-Za-z])',
    'SK-SQLD': r'(?<![A-Za-z])SQLD(?![A-Za-z])',
    'SK-ADSP': r'(?<![A-Za-z])ADsP(?![A-Za-z])',
    'SK-INFO-PE': r'정보처리기사',
    'SK-COMP': r'컴퓨터활용능력\s*[12]\s*급|컴활\s*[12]\s*급',
    'SK-TOEIC': r'(?<![A-Za-z])TOEIC(?!\s*Speaking|[A-Za-z])|토익(?!\s*스피킹)',
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
NEGATED = re.compile(r'없어도|무관|불필요|제한\s*없|필요\s*없')
ALTERNATIVE = re.compile(r'또는|혹은|\bor\b|중\s*(?:하나|1개|택)|대체|환산', re.I)


def _clauses(text, basis, scope):
    # Preserve original wording and offsets, including PDF line breaks.
    for fragment in re.split(r'\n|[•●;。]|(?<=[다요])\.\s*', text):
        clause = fragment.strip()
        if not 4 <= len(clause) <= 500 or NEGATED.search(clause):
            continue
        if ALTERNATIVE.search(clause) or re.search(r'1차\s*합격|취득\s*예정', clause):
            continue
        if basis == 'documents':
            if '포트폴리오' in clause and not re.search(r'선택|자유\s*제출|해당자', clause):
                yield {'skill': 'SK-PORT', 'basis': 'required', 'quote': clause, 'scope': scope}
            continue
        local_basis = 'preferred' if '우대' in clause else basis
        for skill, pattern in SKILL_PATTERNS.items():
            hit = re.search(pattern, clause, re.I)
            if hit is None:
                continue
            if skill in ('ACC-C-CPA', 'ACC-C-CTA') and not re.search(r'자격|보유|소지|합격', clause):
                continue
            minimum = None
            tail = clause[hit.end():]
            if skill == 'SK-TOEIC':
                score = re.match(r'\s*(\d{3})\s*점?\s*이상', tail)
                if score and 10 <= int(score[1]) <= 990:
                    minimum = score[1]
            if skill == 'SK-OPIC':
                grade = re.match(r'\s*(IM[123]|IH|AL)\s*(?:이상)?', tail, re.I)
                if grade:
                    minimum = grade[1].upper()
            if skill == 'SK-JLPT':
                grade = re.match(r'\s*(N[1-5])', tail, re.I)
                if grade:
                    minimum = grade[1].upper()
            yield {'skill': skill, 'basis': local_basis, 'quote': clause, 'scope': scope,
                   **({'minimum': minimum} if minimum else {})}


def extract_skill_evidence(text, reviewed=(), *, multi_role=False):
    results = []
    scope = 'posting' if multi_role else 'role'
    headings = list(HEADINGS.finditer(text))
    for index, heading in enumerate(headings):
        if heading.lastgroup == 'stop':
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.end():min(end, heading.end() + 1800)]
        results.extend(_clauses(block, heading.lastgroup, scope))
    for item in reviewed:
        basis = {'우대': 'preferred', 'preferred': 'preferred',
                 'required': 'required', '지원자격 기재': 'required'}.get(item['status'])
        if basis:
            named_skills = {skill for skill, pattern in SKILL_PATTERNS.items()
                            if re.search(pattern, item['item'], re.I)}
            results.extend(entry for entry in _clauses(item['original_text'], basis, scope)
                           if entry['skill'] in named_skills)
    unique = {}
    for entry in results:
        # A skill keeps its required and preferred clauses independently.
        unique.setdefault((entry['skill'], entry['basis'], entry['quote']), entry)
    return list(unique.values())
