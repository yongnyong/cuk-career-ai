from app.career.posting_skills import extract_skill_evidence


def test_required_preferred_and_exact_source_quotes():
    text = '자격요건\nPython 활용 가능자\nSQL 사용 경험\n우대사항\nSQLD 보유자\n접수기간 11월'
    evidence = extract_skill_evidence(text)
    assert {(e['skill'], e['basis']) for e in evidence} == {
        ('SK-PY-01', 'required'), ('SK-SQL', 'required'), ('SK-SQLD', 'preferred')}
    assert all(e['quote'] in text for e in evidence)


def test_generic_proficiency_negation_and_alternatives_do_not_create_certificates():
    text = ('우대조건\n컴퓨터활용능력 우수자, 영어가능자, 엑셀 고급능력\n'
            '인턴 경험이 없어도 괜찮습니다\nTOEIC 850 이상 또는 OPIc IH 이상\n'
            '토익 850점 이상 or 토익스피킹 150점 이상\n세무사 1차 합격')
    assert extract_skill_evidence(text) == []


def test_numeric_threshold_and_multi_role_scope():
    text = '자격요건\nTOEIC 800점 이상\n우대사항\nOPIc IH 이상'
    rows = extract_skill_evidence(text, multi_role=True)
    assert {(row['skill'], row['minimum'], row['basis'], row['scope']) for row in rows} == {
        ('SK-TOEIC', '800', 'required', 'posting'), ('SK-OPIC', 'IH', 'preferred', 'posting')}


def test_jobkorea_boilerplate_and_company_benefits_do_not_become_evidence():
    text = ('우대조건 프리젠테이션 능력우수자 이 기업과 나의 적합도 체크 '
            'Python SQLD 기업 정보 복리후생 정보처리기사')
    assert [row['skill'] for row in extract_skill_evidence(text)] == ['SK-PPT']


def test_saved_pr_posting_writing_requirement_and_reviewed_quote_scope():
    text = '자격요건\n• 자료 작성 및 글쓰기에 능숙한 분\n• 영어 가능자 우대\n복지제도 영어 교육비 지원'
    reviewed = [{'status': '우대', 'item': '영어 가능자',
                 'original_text': '자료 작성 및 글쓰기에 능숙한 분 • 영어 가능자 우대'}]
    rows = extract_skill_evidence(text, reviewed)
    assert len(rows) == 1
    assert rows[0]['skill'] == 'SK-WRITE' and rows[0]['basis'] == 'required'


def test_required_portfolio_and_optional_documents():
    text = '필수 제출 서류 이력서, 포트폴리오\n전형절차 면접'
    assert [row['skill'] for row in extract_skill_evidence(text)] == ['SK-PORT']
    assert extract_skill_evidence('제출서류 선택 포트폴리오\n근무 조건 주5일') == []
