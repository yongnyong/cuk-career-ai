"""Protect the graph from turning conditional documents and rubrics into global prerequisites."""
import json
import sqlite3

import pytest

from app.startup_collect import build_posting, source_record
from app.startup_db import connect, initialize, save_posting
from app.startup_extract import extract_requirements
from app.startup_nodes import load_graph, rebuild_nodes


NOW = "2026-11-21T00:00:00+00:00"


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "startup.db"
    initialize(path)
    with connect(path) as connection:
        yield connection


def store(db, number, body, template=None):
    url = f"https://www.catholic.ac.kr/ko/campuslife/notice.do?mode=view&articleNo={number}"
    source = source_record(f"cuk-{number}", url, "html", body, NOW)
    sources = [source]
    attachments = []
    if template:
        sources.append(source_record(f"cuk-{number}", url + "&attachNo=1", "template", template, NOW))
        attachments.append({"posting_id": f"cuk-{number}", "url": url + "&attachNo=1", "name": "참가신청서 양식.pdf",
                            "role": "template", "extraction_status": "extracted"})
    posting, requirements = build_posting(url, "2026 창업 지원사업", "2026-11-01", sources, attachments, NOW)
    save_posting(db, posting, sources, attachments, requirements)
    return source


def node(graph, node_id):
    return next(n for n in graph["nodes"] if n["id"] == node_id)


def test_shared_node_retains_distinct_deadline_obligation_and_stage(db):
    store(db, 1, "제출자료\n11.27 발표자료 필수 제출")
    store(db, 2, "12.4 본선 발표자료 제출")
    store(db, 3, "11.20 발표자료 선택 제출")
    rebuild_nodes(db)
    graph = load_graph(db)
    pitch = node(graph, "SU-DOC-pitch-deck")
    assert pitch["posting_count"] == 3
    assert "required" not in pitch
    assert {(r["necessity"], r["stage"], r["deadline_date"]) for r in pitch["references"]} == {
        ("required", "application", "2026-11-27"),
        ("conditional", "finalist", "2026-12-04"),
        ("optional", "application", "2026-11-20"),
    }


def test_only_actual_form_fields_become_child_nodes_and_keep_source(db):
    source = store(db, 1, "참가신청서 작성 후 제출", template=(
        "[PDF page 1]\n1. 인적 사항\n2. 창업 아이템 소개\n소개를 작성하세요\n"
        "3. 조직구성\n4. 자금 집행 계획안\n[제2호 서식] 개인정보 동의서\n5. 시장분석"
    ))
    rebuild_nodes(db)
    graph = load_graph(db)
    titles = {n["title"] for n in graph["nodes"]}
    assert "창업 아이템 소개 작성" in titles
    assert "팀 역할·보유역량 정리" in titles
    assert "시장·경쟁 현황 조사" not in titles
    assert not any("인적" in title for title in titles)
    assert all(edge["parent_id"] == "SU-DOC-application" for edge in graph["edges"])
    assert {edge["relation"] for edge in graph["edges"]} == {"form_section"}
    form = node(graph, "SU-PREP-item")["references"][0]
    assert form["necessity"] == "unspecified"
    assert form["source_page"] == 1
    assert form["source_id"] != source["id"]


def test_evaluation_preparation_does_not_become_required_submission(db):
    store(db, 1, "사업계획서 제출\n평가항목 세부 내용\n문제인식과 수익모델\n시장진입 전략\n□ 지원내용\n멘토링 주제: 투자유치계획")
    rebuild_nodes(db)
    graph = load_graph(db)
    problem = node(graph, "SU-PREP-problem")
    assert problem["references"][0]["basis"] == "evaluation"
    assert problem["references"][0]["necessity"] == "unspecified"
    assert "SU-PREP-funding" not in {n["id"] for n in graph["nodes"]}
    assert {e["relation"] for e in graph["edges"]} == {"evaluation_preparation"}


def test_unfamiliar_business_form_field_extends_review_pool(db):
    store(db, 1, "참가신청서 제출", template="1. 지식재산권 확보 전략\n작성 내용을 기재\n2. 인적사항")
    rebuild_nodes(db)
    assert len(load_graph(db)["nodes"]) == 1
    graph = load_graph(db, include_review=True)
    candidate = next(n for n in graph["nodes"] if n["id"].startswith("SU-PREP-field-"))
    assert candidate["title"] == "지식재산권 확보 전략 작성"
    assert candidate["references"][0]["necessity"] == "needs_review"


def test_filename_only_candidates_are_hidden_and_certificates_stay_documents(db):
    store(db, 1, "개인정보동의서 각 1부 제출")
    source = source_record("cuk-1", "https://example.org/", "attachment_index", "납세증명서 양식.hwp", NOW)
    requirements = extract_requirements(source, 2026, [])
    db.execute("INSERT INTO sources(id,posting_id,url,kind,content,content_hash,fetched_at) VALUES(:id,:posting_id,:url,:kind,:content,:content_hash,:fetched_at)", source)
    for r in requirements:
        keys = list(r)
        db.execute(f"INSERT INTO submission_requirements({','.join(keys)}) VALUES({','.join('?' for _ in keys)})", list(r.values()))
    db.commit()
    rebuild_nodes(db)
    graph = load_graph(db)
    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["kind"] == "certificate"
    assert len(load_graph(db, include_review=True)["nodes"]) == 2


def test_posting_filter_never_leaks_other_program_requirements(db):
    store(db, 1, "11.27 MVP 선택 제출")
    store(db, 2, "사업계획서 제출\n评价\n평가항목\n시장진입 전략")
    rebuild_nodes(db)
    graph = load_graph(db, ["cuk-1"])
    assert [n["id"] for n in graph["nodes"]] == ["SU-DOC-prototype"]
    assert graph["edges"] == []


def test_idempotent_graph_and_removed_evidence_are_refreshed(db):
    store(db, 1, "사업계획서 제출\n평가항목\n시장진입 전략")
    rebuild_nodes(db)
    first = json.dumps(load_graph(db), sort_keys=True)
    rebuild_nodes(db)
    assert json.dumps(load_graph(db), sort_keys=True) == first
    store(db, 1, "발표자료 필수 제출")
    rebuild_nodes(db)
    assert {n["id"] for n in load_graph(db)["nodes"]} == {"SU-DOC-pitch-deck"}
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_failed_graph_replacement_restores_previous_catalog(db):
    store(db, 1, "사업계획서 제출")
    rebuild_nodes(db)
    before = load_graph(db)
    db.execute("CREATE TRIGGER fail_node BEFORE INSERT ON startup_nodes BEGIN SELECT RAISE(ABORT,'test'); END")
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        rebuild_nodes(db)
    assert load_graph(db) == before
