"""Extract major conditions only from recruitment requirement sections."""
import re

from .posting_skills import _blocks, FACT_BOUNDARY

# These are name equivalents. Adjacency between disciplines is never a required match.
ALIASES = {
    'cs': r'컴퓨터(?:공학|정보공학|과학)|전산(?:학|공학)|소프트웨어(?:학|공학)',
    'ai': r'인공지능(?:학|공학)?',
    'data-science': r'데이터사이언스|데이터과학',
    'ice': r'전자(?:공학|정보)|정보통신(?:공학)?',
    'business': r'경영(?:학|학과)?',
    'accounting': r'회계(?:학|학과)?|세무(?:학|회계)',
    'psychology': r'심리(?:학|학과)?',
    'social-welfare': r'사회복지(?:학|학과)?',
    'media-tech': r'미디어기술콘텐츠|영상(?:학|제작)|방송영상',
    'chemistry': r'화학(?:과)?(?!공학)',
    'math': r'수학(?:과)?',
    'physics': r'물리(?:학|학과)?',
    'nursing': r'간호(?:학|학과)?',
    'pharmacy': r'약학(?:과)?',
    'food-nutrition': r'식품영양(?:학|학과)?',
    'biotech': r'생명공학',
    'biomed-science': r'의생명과학',
    'medicine': r'의학(?:과)?',
    'law': r'법학(?:과)?',
    'economics': r'경제(?:학|학과)?',
}
FIELDS = {
    '이공계': ['science', 'engineering', 'bio', 'ict'],
    '인문계': ['humanities', 'language'],
    '자연계': ['science'],
    '공학계': ['engineering', 'ict'],
}


def extract_major_conditions(text, catalog, *, multi_role=False):
    rows = []
    known = {d['id'] for d in catalog['departments']}
    for block, section_basis, documents in _blocks(text):
        if documents:
            continue
        for clause in FACT_BOUNDARY.split(block):
            quote = clause.strip()
            if not 2 <= len(quote) <= 400 or not re.search(
                    r'전공(?!필기|시험|시험과목)|(?:관련|유관)\s*학과|학과\s*(?:졸업|출신)|계열|이공계|상경계', quote):
                continue
            if re.search(r'전공\s*(?:필기|시험)|석차|스킬\s*[,：:]?', quote):
                continue
            if re.search(r'제외|불가|아니|않|해당자|복수전공|부전공', quote):
                continue
            unrestricted = bool(re.search(r'전공\s*(?:무관|불문|제한\s*없)|학과\s*(?:무관|불문)', quote))
            basis = 'preferred' if '우대' in quote else 'required' if '필수' in quote else section_basis or 'unspecified'
            ids = {key for key, pattern in ALIASES.items() if key in known and re.search(
                r'(?<![가-힣])(?:' + pattern + r')(?:과)?(?![가-힣])', quote, re.I)}
            ids.update(d['id'] for d in catalog['departments'] if d['name'] in quote)
            if '상경계' in quote:
                ids.update({'business', 'accounting', 'global-business', 'economics', 'intl'} & known)
            fields = {f for term, values in FIELDS.items() if term in quote for f in values}
            # Store unmapped conditions for manual review, preserving the original phrase.
            row = {'basis': basis, 'departmentIds': sorted(ids), 'fields': sorted(fields),
                   'related': bool(re.search(r'관련|유관|등\s*전공|또는|혹은', quote)),
                   'unrestricted': unrestricted, 'quote': quote,
                   'scope': 'posting' if multi_role else 'role'}
            if row not in rows:
                rows.append(row)
    return rows
