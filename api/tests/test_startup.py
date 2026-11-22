"""Regressions that would produce incorrect student submission instructions."""
import json
import sqlite3

import pytest

from app.startup_collect import attachments_from_html, build_posting, source_record
from app.startup_db import connect, initialize, save_posting
from app.startup_extract import application_period, application_status, extract_requirements


URL = "https://business.catholic.ac.kr/business/community/notice.do?mode=view&articleNo=277825"
NOW = "2026-11-21T01:00:00+00:00"


def extract(text, kind="html"):
    source = source_record("cuk-277825", URL, kind, text, NOW)
    return source, extract_requirements(source, 2026, [])


def test_pitch_required_and_mvp_optional_have_submission_deadline():
    source, rows = extract(
        "- 2026. 11. 23.(월) ~ 11. 27.(금): Pitch Deck 제출 (MVP 선택 제출)\n"
        "4. 제출 자료 (~11.27. 금)\n"
        "- Pitch Deck(발표자료): 필수 제출\n"
        "- MVP(시제품): 선택 제출\n"
    )
    by_type = {row["document_type"]: row for row in rows}
    assert by_type["발표자료"]["necessity"] == "required"
    assert "필수 제출" in by_type["발표자료"]["evidence_quote"]
    assert by_type["시제품"]["necessity"] == "optional"
    assert by_type["발표자료"]["deadline_date"] == "2026-11-27"
    for row in rows:
        assert source["content"].splitlines()[row["evidence_line"] - 1] == row["evidence_quote"]


def test_finalist_deliverable_is_conditional():
    _, rows = extract(
        "- 신청 방법 : 참가 신청서 및 사업계획서 작성 후 이메일로 제출 (~11.18 23:59)\n"
        "- 본선 발표 자료 제출 : 12.4 (금)"
    )
    by_type = {row["document_type"]: row for row in rows}
    assert by_type["사업계획서"]["stage"] == "application"
    assert by_type["발표자료"]["stage"] == "finalist"
    assert by_type["발표자료"]["necessity"] == "conditional"
    assert by_type["발표자료"]["deadline_date"] == "2026-12-04"


def test_filename_does_not_prove_obligation_or_make_manual_a_deliverable():
    _, rows = extract("사업계획서 작성 안내.pdf\n사업계획서 양식.hwp\n사업자등록증 제출목록 안내.hwp", "attachment_index")
    assert len(rows) == 1
    assert rows[0]["necessity"] == "needs_review"
    assert rows[0]["stage"] == "unknown"


def test_eligibility_and_support_mentions_do_not_become_deliverables():
    _, rows = extract("사업자등록증을 보유하지 않은 예비창업자\n시제품 제작비 및 사업계획서 교육 지원\n서류: 사업자등록증 제출 불필요")
    assert rows == []


def test_penalty_paragraph_is_not_a_requirement_and_posters_are_not_mvp():
    _, rows = extract("③ 사업계획서 등을 타인이 대신 작성하여 제출하는 경우 처벌\n- 선정기업은 사업계획서에 명시된 목표 달성을 위하여 이행하여야 함\n신청서 사업계획서 등 제출서류 기반")
    assert rows == []
    _, rows = extract("시제품 제작지원 사업 신청서.hwp\n2026년 시제품제작터 웹포스터.pdf", "attachment_index")
    assert not any(row["document_type"] == "시제품" for row in rows)


def test_pdf_table_certificates_are_scoped_to_applicant_type():
    _, rows = extract("제출서류\n필수\n예비\n창업자\n① 사실증명서 사업자등록사실여부\n개인 및\n법인사업자\n① 사업자등록증\n② 법인등기부등본 (해당 시)")
    assert all(row["necessity"] == "conditional" for row in rows)
    assert next(row for row in rows if row["document_type"] == "사업자등록증")["condition_text"] == "개인및법인사업자"


def test_distinct_fact_certificates_are_preserved():
    _, rows = extract("제출서류\n예비\n창업자\n사실증명서 (사업자등록사실여부)\n개인 및\n법인사업자\n사실증명서 (총사업자등록내역)")
    assert {row["document_type"] for row in rows} == {"사업자등록사실여부증명", "총사업자등록내역증명"}


def test_conditional_certificate_and_application_channel():
    _, rows = extract("제출서류\n- 사업자등록증 (해당 시)\n- 참가신청서 작성 후 구글폼으로 제출")
    assert {r["document_type"] for r in rows} == {"사업자등록증", "참가신청서"}
    assert next(r for r in rows if r["document_type"] == "사업자등록증")["necessity"] == "conditional"


def test_conflicting_closing_dates_and_budget_are_unresolved():
    assert application_period("모집 기간 : 11.9 ~ 11.18\n신청 방법 : 신청서 제출 (~11.20까지)", 2026)[2] is None
    assert application_period("신청기간\n예산 소진시까지", 2026)[2] is None
    assert application_status(None, None, "예산 소진시까지", "2026-11-21") == "needs_review"
    assert application_status("2026-11-01", "2026-12-01", "조기마감 사유\n조기종료 자동처리", "2026-11-21") == "closed"


def test_multiline_government_period_and_same_day_precision():
    raw, start, end, note = application_period("신청기간\n2026.03.06 ~\n2026.03.26\n사업개요", 2026)
    assert (start, end, note) == ("2026-03-06", "2026-03-26", None)
    assert application_status(start, end, raw, end) == "needs_review"


def test_download_token_is_not_persisted_with_stable_attachment_identity():
    page = '''<li><div class="file_name">사업계획서 양식.hwp</div>
        <a href="/cmm/fms/fileDown.do?atchFileId=FILE_123&amp;fileSn=1&amp;downloadToken=temporary">다운로드</a></li>'''
    item = attachments_from_html(page, "https://www.bizinfo.go.kr/")[0]
    assert "downloadToken" not in item["url"]
    assert "fileSn=1" in item["url"]
    assert "downloadToken" in item["_fetch_url"]


def test_reingestion_is_atomic_and_idempotent(tmp_path):
    path = tmp_path / "startup.db"
    initialize(path)
    source, requirements = extract("참가신청서 작성 후 제출")
    posting, _ = build_posting(URL, "2026 창업경진대회", "2026-11-16", [source], [], NOW)
    with connect(path) as db:
        save_posting(db, posting, [source], [], requirements)
        save_posting(db, posting, [source], [], requirements)
        assert db.execute("SELECT count(*) FROM postings").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM submission_requirements").fetchone()[0] == 1
        broken = {**requirements[0], "source_id": "missing"}
        with pytest.raises(sqlite3.IntegrityError):
            save_posting(db, posting, [source], [], [broken])
        assert db.execute("SELECT source_id FROM submission_requirements").fetchone()[0] == source["id"]
        assert json.loads(posting["review_notes"])
