from app.career.posting_skills import attach_preparation_evidence, extract_preparation_evidence, extract_skill_evidence
from app.career.posting_skills import has_multiple_roles


def test_specific_certificate_names_and_tax_grade_are_distinct_from_product_proficiency():
    text = '우대조건\n전산세무1급\n포토샵 능숙자\nPower BI 활용\nAWS 데이터 파이프라인 운영'
    assert [(r['skill'], r.get('minimum')) for r in extract_skill_evidence(text)] == [('CERT-TAX', '1급')]
    assert {r['key'] for r in extract_preparation_evidence(text)} == {
        'credential:CERT-TAX', 'PR-IMAGE-RETOUCH', 'power_bi'}
    assert {r['skill'] for r in extract_skill_evidence('자격요건\nACP Photoshop\nSNS광고마케터 1급')} == {
        'CERT-ACP-PS', 'CERT-SNS-ADS'}
    assert not extract_skill_evidence('자격요건\nSNS광고마케터 1급 없어도 가능\n전산세무1급 또는 전산회계1급')
    assert not has_multiple_roles('기장관리업무 신입, 경력직 채용', '모집분야 기장관리업무 신입, 기장관리업무 경력 모집인원 2명')
    assert has_multiple_roles('공개 채용', '모집분야 기장관리업무 신입, 고객상담 경력 모집인원 2명')


def test_project_observations_keep_exact_capability_without_inventing_a_certificate():
    lines = ['커머스 업종 브랜드 자사몰 운영(AMD) 경험이 있으신 분',
             '업무 생산성 Tool(Notion, G-Suite 등)활용이 능숙하신 분']
    rows = extract_preparation_evidence('우대사항\n' + '\n'.join(lines))
    assert {(r['key'], r['quote'], r['basis'], r['scope']) for r in rows} == {
        ('PR-STORE-OPS', lines[0], 'preferred', 'role'),
        ('PR-NOTION', lines[1], 'preferred', 'role'),
        ('PR-SHARED-DOCS', lines[1], 'preferred', 'role')}
    assert not extract_preparation_evidence('복리후생\n포토샵 강의\n자격요건\nNotion 경험 없어도 가능합니다')
    rows = extract_preparation_evidence('우대사항\nEnglish communication skill is mandatory')
    assert [(r['key'], r['basis']) for r in rows] == [('PR-FOREIGN-CALL', 'required')]


def test_speaking_grade_is_attached_only_to_the_named_exam():
    text = '자격요건\nTOEIC Speaking IH 이상\n우대사항\n토익 850점 이상'
    rows = extract_skill_evidence(text)
    assert {(r['skill'], r['minimum']) for r in rows} == {('SK-TOEIC-SPEAKING', 'IH'), ('SK-TOEIC', '850')}
    assert not extract_preparation_evidence('우대사항\n토익 또는 토익스피킹 보유')


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


def test_observed_sql_capability_project_and_explicit_certificate_stay_distinct():
    text = ('우대조건\nSQL 활용 우대\nSQL로 데이터를 분석한 경험\nSQLD 자격 보유자\n'
            '자격요건\n정보처리기사\n주요 업무\nCAD 도면 검토')
    facts = extract_preparation_evidence(text, multi_role=True)
    assert {(r['key'], r['basis']) for r in facts} == {
        ('sql', 'preferred'), ('sql_project', 'preferred'), ('sql_certificate', 'preferred'),
        ('credential:SK-INFO-PE', 'required')}
    assert all(row['quote'] in text and row['scope'] == 'posting' for row in facts)
    assert [r['key'] for r in extract_preparation_evidence('SQL 활용 가능자 우대')] == ['sql']


def test_document_and_spreadsheet_skills_produce_observations_without_inventing_certificates():
    facts = extract_preparation_evidence('우대사항\n문서작성 우수자, 엑셀 고급능력 보유자\n컴퓨터활용능력 우수자')
    assert {row['key'] for row in facts} == {'business_document', 'spreadsheet'}
    assert extract_preparation_evidence('우대사항\nRhino 능숙자') == []


def test_named_deliverables_need_submission_context_and_clear_basis():
    text = ('우대조건\n제안서 작성 능력\n필수 제출 서류\n설계 도면\n기획서\n글쓰기 샘플\n'
            'a. 필수 : 이력서 (지원동기 포함 必), 포트폴리오 b. 선택 : 추가 제출 서류\n'
            '근무 조건 주5일')
    facts = extract_preparation_evidence(text)
    assert {(row['key'], row['basis']) for row in facts} == {
        ('presentation', 'preferred'), ('drawing', 'required'), ('proposal', 'required'),
        ('writing_sample', 'required'), ('portfolio', 'required')}
    assert all(row['quote'] in text for row in facts)
    assert not extract_preparation_evidence('제출서류\n포트폴리오')
    assert not extract_preparation_evidence('필수 제출 서류\n이력서\n선택: 아래 서류\n포트폴리오')
    assert not extract_preparation_evidence('선택 제출 서류\n포트폴리오')
    assert not extract_preparation_evidence('필수 제출 서류\n기획 결과물 또는 포트폴리오')


def test_ambiguous_certificates_and_generic_skill_tags_are_not_requirements():
    text = ('자격요건\nSQLD 필요하지 않음\nSQLD 필수 아님\nSQLD/ADsP\nSQLD 또는\nADsP\n'
            'SQLD\n또는 ADsP\n경력 신입 학력 대졸이상 스킬 , AI, 산업안전기사\n'
            '기업 정보 SQLD 우대')
    assert not extract_preparation_evidence(text)
    assert not extract_preparation_evidence('자격요건\n다음 중 하나\nSQLD\nADsP')


def test_only_verbatim_reviewed_evidence_has_a_source_and_matching_item():
    quote = 'SQL 활용 우대'
    reviewed = [{'status': '우대', 'item': 'SQL', 'text_type': 'extracted', 'original_text': quote},
                {'status': 'required', 'item': 'SQLD', 'text_type': 'summary', 'original_text': 'SQLD 필수'},
                {'status': '우대', 'item': '영어', 'text_type': 'extracted', 'original_text': 'SQLD 보유자 우대'}]
    data = {'sections': [{'id': '역량1', 'text': quote}]}
    assert attach_preparation_evidence(data, '', reviewed) is data
    assert data['preparationEvidence'] == [
        {'key': 'sql', 'basis': 'preferred', 'scope': 'role', 'quote': quote, 'src': '역량1'}]
    attach_preparation_evidence(data, '우대조건\nSQL 활용 우대\n포트폴리오 제출 우대', reviewed)
    sections = {s['id']: s['text'] for s in data['sections']}
    assert len(sections) == 2
    assert all(row['quote'] == sections[row['src']] for row in data['preparationEvidence'])
