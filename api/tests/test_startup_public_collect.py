from pathlib import Path

import pytest

from app.startup_collect import build_posting, source_record
from app.startup_db import connect, initialize, save_posting
from app.startup_public_collect import listing, parse_detail, robots_allowed, KSTARTUP


def test_robots_longest_rule_wildcard_and_agent_selection():
    policy = 'User-agent: *\nAllow: /\nDisallow: /afile*/\nDisallow: /private/\nAllow: /private/public$'
    assert robots_allowed(policy, KSTARTUP)
    assert not robots_allowed(policy, 'https://www.k-startup.go.kr/afileUpload/a.pdf')
    assert robots_allowed(policy, 'https://example.org/private/public')
    assert not robots_allowed(policy, 'https://example.org/private/public-more')
    specific = policy + '\nUser-agent: CUK-Startup-Demo\nDisallow: /'
    assert not robots_allowed(specific, KSTARTUP)
    with pytest.raises(ValueError):
        robots_allowed('<html>error</html>', KSTARTUP)


def test_listing_merges_public_links_without_running_javascript():
    page = '<a href="javascript:go_view(123);"><p class="tit">AI 팀 모집</p></a>'
    page += '<a href="https://www.k-startup.go.kr/?pbancSn=123">자세히 보기</a>'
    assert listing(page) == {'123': 'AI 팀 모집'}


def test_detail_excludes_navigation_keeps_separate_submission_lines(tmp_path):
    page = '''<p class="tit">중소벤처24 통합로그인 사이트</p><div>가입</div>
      <h3>AI 창업기업 모집</h3><div class="information_list">
      <div><p class="tit">신청기간</p><p class="txt">2026.11.20 ~ 2026.12.10</p></div>
      <div><p class="tit">신청대상</p><div class="list_wrap">예비창업자</div></div>
      <div><p class="tit">제출서류</p><div class="list_wrap">사업계획서 필수<br/>사업자등록증(해당자)</div></div>
      </div>'''
    title, body = parse_detail(page)
    assert '통합로그인' not in body
    assert '제출서류: 사업계획서 필수\n제출서류: 사업자등록증(해당자)' in body
    url = KSTARTUP + '?schM=view&pbancSn=123'
    source = source_record('kstartup-123', url, 'html', body, '2026-11-26T09:00:00+09:00')
    posting, requirements = build_posting(url, title, None, [source], [], '2026-11-26T09:00:00+09:00')
    assert posting['id'] == 'kstartup-123'
    assert posting['source_site'] == 'K-Startup(창업진흥원)'
    assert posting['application_end'] == '2026-12-10'
    assert requirements
    assert all(r['evidence_quote'] in source['content'] for r in requirements)
    assert any(r['necessity'] == 'conditional' for r in requirements)
    db_path = tmp_path / 'startup.db'
    initialize(db_path)
    with connect(db_path) as db:
        for _ in range(2):
            save_posting(db, posting, [source], [], requirements)
        assert db.execute('select count(*) from postings').fetchone()[0] == 1
        assert db.execute('select count(*) from submission_requirements').fetchone()[0] == len(requirements)


def test_missing_detail_layout_fails_without_inventing_conditions():
    with pytest.raises(ValueError):
        parse_detail('<h3>모집공고</h3><div>레이아웃 변경</div>')
