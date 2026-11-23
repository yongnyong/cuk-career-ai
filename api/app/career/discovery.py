"""Discover named terms in explicit requirement clauses without a term allowlist."""
import re


TOOL = re.compile(
    r'(?<![A-Za-z0-9+#./-])(?P<term>[A-Za-z][A-Za-z0-9+#.-]*(?: +[A-Za-z][A-Za-z0-9+#.-]*){0,2})'
    r'\s*(?:를|을)?\s*(?:(?:활용|사용|운용)\s*(?:가능|능숙|경험|역량|능력|숙련)|능숙|숙련)')
CREDENTIAL = re.compile(
    r'(?<![가-힣A-Za-z0-9])(?P<term>(?:[가-힣A-Za-z0-9]{2,24}(?:기사|기능사|관리사|분석사|지도사|기술사)'
    r'(?:\s*[1-9]\s*급)?|[A-Z][A-Z0-9-]{1,15}(?=\s*자격증)))'
    r'\s*(?:자격증?|면허증?)?\s*(?:을|를)?\s*(?:소지|보유|취득|필수|우대)')
ARTIFACT = re.compile(
    r'(?<![가-힣A-Za-z0-9])(?P<term>[가-힣A-Za-z0-9]{2,18}\s*(?:설계서|계획서|보고서|시연\s*영상|설계도|테스트\s*명세서))'
    r'(?=\s*(?:를|을|파일|원본|제출|첨부|필수|$|[,.(]))')
GENERIC = re.compile(r'^(?:it|ai|oa|sw|s/w|ms|tool|tools|pc|software|프로젝트|관련|각종|기타|해당|업무|개인|본인)$', re.I)
PERSONAL = re.compile(r'경력|병역|건강|신체|범죄|학업계획|자기소개|개인정보|신용|주민등록')


def named_terms(clause, documents=False):
    if '/' in clause or re.search(r'택일|중\s*택|중\s*한\s*가지', clause):
        return
    patterns = [] if documents else [('credential', CREDENTIAL), ('tool', TOOL)]
    if documents or re.search(r'제출|첨부', clause):
        patterns.append(('artifact', ARTIFACT))
    for kind, pattern in patterns:
        for match in pattern.finditer(clause):
            term = match['term'].strip()
            if (2 <= len(term) <= 48 and not GENERIC.fullmatch(term)
                    and not (kind == 'artifact' and (PERSONAL.search(term) or GENERIC.fullmatch(term.split()[0])))):
                yield kind, term
