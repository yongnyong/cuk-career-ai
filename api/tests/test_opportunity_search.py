from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import os
import tempfile
import io
import json

# Configure isolated stores before importing modules that create the default engines.
for key, name in (("DATABASE_URL", "accounts.db"), ("CAREER_DATABASE_URL", "career.db")):
    os.environ.setdefault(key, "sqlite:///" + os.path.join(tempfile.mkdtemp(prefix="rag-test-"), name).replace("\\", "/"))

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.career_db import CareerBase, SearchSection
from app.career.opportunity_search import OpportunitySearch, posting_sections
from app.career.opportunity_rag import explain


def posting(pid, title, body, kind="employment", version=1):
    return dict(id=pid, title=title, type="창업지원" if kind == "startup" else "채용",
        source=dict(url=f"https://example.edu/{pid}"), applyUrl=f"https://example.edu/{pid}",
        org="테스트 기관", isVirtual=False, required=[], preferred=[], jobs=[], documents=[],
        sections=[dict(id="duties", title="업무", text=body)],
        versions=[dict(version=version, checkedAt="2026-11-24", deadline="2026-12-31T23:59:00+09:00")])


@pytest.fixture
def index(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "career.db"))
    CareerBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    rows = [
        posting("evaluation", "응답 품질 검수 담당", "LLM 답변을 비교하고 품질 기준에 따라 평가합니다. SQL 활용 우대."),
        posting("sales", "온라인 상품 영업", "온라인 상품 판매와 고객 응대를 담당합니다."),
        posting("prototype", "AI 시제품 제작비 지원", "학원 상담 요약 AI의 시제품 제작비와 개발비를 지원합니다.", "startup"),
        posting("channel", "창업기업 판로 상담", "학원 상담 요약 AI의 판로 상담과 구매처 연결을 지원합니다.", "startup"),
    ]
    search = OpportunitySearch(sessions, lambda: deepcopy(rows))
    try:
        yield search, rows, sessions
    finally:
        engine.dispose()


def test_keyword_retrieval_searches_full_domain_and_retains_exact_sources(index):
    search, rows, _ = index
    hit = search.search("LLM 답변 비교 평가 SQL", "employment")
    assert hit["hits"][0]["postingId"] == "evaluation"
    assert all(item["postingId"] not in {"prototype", "channel"} for item in hit["hits"])
    for source in hit["hits"][0]["evidence"]:
        raw = next(row for row in rows if row["id"] == source["postingId"])
        assert source["version"] == raw["versions"][-1]["version"]
        assert any(source["quote"] in text for text in [raw["title"], *[s["text"] for s in raw["sections"]]])
    assert search.search("완전히무관한외계행성zzzz", "employment")["hits"] == []


def test_service_classification_notes_are_never_indexed_as_original_evidence(index):
    search, rows, _ = index
    rows[0]["sections"].extend([
        dict(id="review", title="확인 범위·주의사항", text="서비스가 분류한 마케팅 업무"),
        dict(id="mapping", title="직무 연결", text="서비스가 분류한 마케팅 업무"),
        dict(id="placeholder", title="지원 조건", text="지원 조건은 원문 링크에서 확인해 주세요."),
    ])
    sections, _ = search.refresh()
    assert not any("서비스가 분류한" in section.quote for section in sections)
    assert not any("지원 조건은 원문" in section.quote for section in sections)


def test_startup_goal_changes_ranking_with_same_idea_and_customer(index):
    search, _, _ = index
    assert search.search("학원 상담 요약 AI 시제품 제작비", "startup")["hits"][0]["postingId"] == "prototype"
    assert search.search("학원 상담 요약 AI 판로 상담 구매처", "startup")["hits"][0]["postingId"] == "channel"
    assert [hit["postingId"] for hit in search.search("학원 상담 요약 AI 판로 상담", "startup",
        focus="판로 상담")["hits"]] == ["channel"]
    search.source = lambda: [row for row in index[1] if row["id"] != "channel"]
    assert search.search("학원 상담 요약 AI 판로 상담", "startup", focus="판로 상담")["hits"] == []


def test_reindex_is_idempotent_and_removes_deleted_and_superseded_chunks(index):
    search, rows, sessions = index
    first, _ = search.refresh()
    assert [section.id for section in search.refresh()[0]] == [section.id for section in first]
    rows[0]["versions"][-1]["version"] = 2
    rows[0]["sections"][0]["text"] = "새로운 업무 원문"
    rows.pop(1)
    sections, _ = search.refresh()
    assert all(section.version == 2 for section in sections if section.posting_id == "evaluation")
    assert not any(section.posting_id == "sales" for section in sections)
    with sessions() as db:
        stored = db.scalars(select(SearchSection)).all()
    assert {row.id for row in stored} == {section.id for section in sections}


class Embeddings:
    model = "fixture-embeddings-v1"
    dimensions = 2
    calls = 0

    def embed(self, texts, **kwargs):
        self.calls += 1
        return [[1., 0.] if "LLM" in text else [0., 1.] for text in texts]

    def query(self, text):
        assert "student@example.com" not in text
        return [1., 0.]


def test_semantic_rank_is_combined_and_cached_document_vectors_are_reused(index):
    search, _, _ = index
    embeddings = Embeddings()
    search.embeddings = embeddings
    search.index_embeddings()
    count = embeddings.calls
    assert search.index_embeddings() == 0
    assert embeddings.calls == count
    result = search.search("모델의 출력물을 심사한 경험 student@example.com", "employment")
    assert result["mode"] == "hybrid"
    assert result["hits"][0]["postingId"] == "evaluation"
    assert embeddings.calls == count


def test_invalid_embedding_configuration_never_uses_old_vectors(index):
    search, _, _ = index
    search.embeddings = Embeddings()
    search.index_embeddings()
    search.embeddings.model = "fixture-embeddings-v2"
    assert search.search("SQL", "employment")["mode"] == "keyword"


def test_embedding_outage_retains_keyword_evidence(index):
    from app.career.embeddings import EmbeddingUnavailable
    search, _, _ = index
    search.embeddings = Embeddings()
    search.index_embeddings()
    def unavailable(query):
        raise EmbeddingUnavailable("offline")
    search.embeddings.query = unavailable
    response = search.search("SQL", "employment")
    assert response["mode"] == "keyword_fallback"
    assert response["hits"][0]["postingId"] == "evaluation"


@pytest.mark.parametrize("model", ["gemini-embedding-001", "gemini-embedding-2"])
def test_embedding_http_contract_dimension_normalization_and_query_cache(monkeypatch, model):
    from app.career import embeddings
    requests = []
    def open_request(request, timeout):
        requests.append(json.loads(request.data))
        return io.BytesIO(json.dumps({"embeddings": [{"values": [1.] * 128}]}).encode())
    monkeypatch.setattr(embeddings, "urlopen", open_request)
    client = embeddings.GeminiEmbeddings("synthetic-key", model, dimensions=128)
    first = client.query("LLM evaluation")
    assert client.query("LLM evaluation") == first and len(requests) == 1
    assert len(first) == 128 and sum(v * v for v in first) == pytest.approx(1.)
    sent = requests[0]["requests"][0]
    assert sent["outputDimensionality"] == 128
    if model.endswith("001"):
        assert sent["taskType"] == "RETRIEVAL_QUERY"
    else:
        assert "taskType" not in sent
        assert sent["content"]["parts"][0]["text"].startswith("task: search result")


def test_rag_model_cannot_invent_quotes_conditions_or_other_posting_evidence(index):
    search, _, _ = index
    def generate(instruction, data, schema):
        assert "SQL 활용 우대" in str(data)
        return dict(items=[dict(postingId="evaluation", relevantEvidenceIds=["forged"],
            checkEvidenceIds=["foreign-posting"], unsupported="SQLD 필수")])
    result = explain(search, SimpleNamespace(generate=generate), "SQL 분석", ["evaluation"])
    assert result["items"]
    assert "SQLD 필수" not in str(result)
    assert all("SQL 활용 우대" in source["quote"] for source in result["items"][0]["related"])
    assert result["items"][0]["checks"] == []


def test_corrected_posting_during_generation_cannot_return_old_evidence(index):
    search, rows, _ = index
    def generate(instruction, data, schema):
        row = rows[0]
        row["versions"][-1]["version"] += 1
        row["sections"][0]["text"] = "변경된 업무"
        return dict(items=[dict(postingId="evaluation",
            relevantEvidenceIds=[data["evidence"][0]["evidenceId"]], checkEvidenceIds=[])])
    result = explain(search, SimpleNamespace(generate=generate), "SQL", ["evaluation"])
    assert result["items"] == []


def test_duplicate_reposts_do_not_multiply_results(index):
    search, rows, _ = index
    clone = deepcopy(rows[0])
    clone["id"] = "duplicate"
    clone["source"]["url"] += "?utm_source=repost"
    rows.append(clone)
    assert len(search.search("SQL", "employment")["hits"]) == 1


def test_request_pagination_covers_all_candidates_before_eligibility_filter(index):
    search, rows, _ = index
    for number in range(14):
        rows.append(posting(f"sql-{number}", "SQL 업무", "SQL 활용 우대"))
    pages = []
    offset = 0
    while True:
        page = search.search("SQL", "employment", offset=offset, limit=3)
        pages.extend(page["hits"])
        if page["nextOffset"] is None:
            break
        offset = page["nextOffset"]
    assert len(pages) == len({hit["postingId"] for hit in pages}) == 15


def test_empty_shared_selection_stays_empty_and_order_is_preserved():
    from app.assistant.context import select_opportunities
    from app.assistant.contracts import Screen
    from app.assistant.service_data import FOCUS, ServiceCareerData
    rows = [posting("first", "첫 공고", "SQL"), posting("second", "둘째 공고", "SQL")]
    data = object.__new__(ServiceCareerData)
    data.public_postings = lambda: rows
    for focus, expected in [((), []), (("second", "first"), ["second", "first"])]:
        token = FOCUS.set(focus)
        try:
            selected, _ = select_opportunities(data, Screen(), "취업 공고 추천", [], None,
                datetime(2026, 11, 24, tzinfo=timezone.utc))
            assert [item.id for item in selected] == expected
        finally:
            FOCUS.reset(token)


def test_date_only_closing_date_matches_web_end_of_korean_day():
    from app.assistant.service_data import to_opportunity
    row = posting("closing", "접수 마감일 공고", "SQL")
    row["deadlineStatus"] = "date_only"
    row["versions"][-1]["deadline"] = "2026-11-24"
    item = to_opportunity(row)
    assert item.deadline.isoformat() == "2026-11-24T23:59:59.999999+09:00"

