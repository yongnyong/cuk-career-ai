import json
from pathlib import Path

from app.career.major_conditions import extract_major_conditions

CATALOG = json.loads((Path(__file__).parents[1] / 'app/career/web_catalog.json').read_text(encoding='utf-8'))


def test_explicit_major_basis_and_related_scope_preserve_source():
    text = '지원자격\n컴퓨터공학 전공 필수\n우대사항\n회계학 및 관련 학과 우대\n기업 정보\n간호학과 협약'
    rows = extract_major_conditions(text, CATALOG)
    assert [(r['basis'], r['departmentIds'], r['related']) for r in rows] == [
        ('required', ['cs'], False), ('preferred', ['accounting'], True)]
    assert all(r['quote'] in text and r['scope'] == 'role' for r in rows)
    assert extract_major_conditions(text, CATALOG, multi_role=True)[0]['scope'] == 'posting'


def test_unrestricted_unmapped_and_field_conditions_do_not_imply_an_exact_major():
    rows = extract_major_conditions('지원자격\n전공 무관\n이공계 전공 필수\n항공우주학과 전공자\n우대사항\n상경계 전공 우대', CATALOG)
    assert rows[0]['unrestricted']
    assert 'ict' in rows[1]['fields']
    assert rows[2]['departmentIds'] == []
    assert 'economics' in rows[3]['departmentIds']
    assert 'law' not in rows[3]['departmentIds']
    assert not extract_major_conditions('복리후생\n컴퓨터공학 전공자 교육 지원', CATALOG)
    assert not extract_major_conditions('지원자격\n이수학과 석차비율 구간별 배점\n전공필기 경영학, 경제학, 회계학', CATALOG)
    generic = extract_major_conditions('우대사항\n통계분석·리서치 능숙자, 관련 학과 전공자', CATALOG)
    assert generic[0]['departmentIds'] == []
