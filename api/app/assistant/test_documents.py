"""Generated fixtures exercise output files and the authenticated API contract."""
import io
import json
from types import SimpleNamespace

import pytest
from docx import Document
from fastapi import Cookie, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from .contracts import DraftEdit, DraftRequest
from .document_formats import MAX_UPLOAD_BYTES
from .errors import Conflict, ModelTimeout, NotFound, UnsupportedDocument, UploadTooLarge
from .prompts import CONSULTATION, FIELD_MATCHING
from .router import make_router
from .test_chat import CERT_MESSAGE, ask, make_assistant

JSON_FIELDS = [
    {"id": "name", "label": "이름"},
    {"id": "projects", "label": "프로젝트"},
    {"id": "cert", "label": "자격증"},
    {"id": "awards", "label": "수상"},
    {"id": "intro", "label": "자기소개서"},
]


def json_template():
    return json.dumps({"fields": JSON_FIELDS}, ensure_ascii=False).encode("utf-8")


def make_docx():
    doc = Document()
    title = doc.add_paragraph("프로젝트 ")
    title.add_run("{{proj")
    title.add_run("ect}}")
    doc.add_paragraph("수상 {{award}}")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "학과"
    table.cell(1, 0).text = "학년"
    table.cell(1, 1).text = "원본 기입값"
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def make_pdf():
    data = io.BytesIO()
    pdf = Canvas(data)
    pdf.drawString(30, 740, "Career AI test application")
    pdf.acroForm.textfield(name="grade", x=30, y=680, width=180, height=24)
    pdf.acroForm.textfield(name="skill", x=30, y=635, width=180, height=24)
    pdf.showPage()
    pdf.save()
    return data.getvalue()


@pytest.fixture
def service(tmp_path):
    return make_assistant(tmp_path)


def test_json_analysis_fill_provenance_missing_narrative_and_edit(service):
    ask(service, CERT_MESSAGE)
    source = json_template()
    document = service.documents.upload("alice", "mock-application.json", source)
    assert [field.kind for field in document.fields] == ["personal", "project", "certification", "award", "narrative"]
    draft = service.documents.generate("alice", document.id, DraftRequest(narrative_prompt="프로젝트 지원동기"))
    fields = {item.field.id: item for item in draft.fields}
    assert fields["name"].status == fields["awards"].status == "missing"
    assert fields["projects"].value.startswith("Campus Data Lab")
    assert fields["projects"].sources[0].source == "system"
    assert fields["cert"].sources[0].source == "official"
    assert [item.value for item in fields["cert"].suggestions] == ["SQLD"]
    assert "SQLD" not in fields["cert"].value
    assert fields["intro"].status == "draft" and "Campus Data Lab" in fields["intro"].value
    assert fields["intro"].value.startswith("[AI 초안]")
    assert service.store.get_original("alice", document.id) == source
    changed = service.documents.edit("alice", document.id, DraftEdit(revision=1, values={"intro": "내가 직접 작성한 문장"}))
    assert changed.revision == 2
    with pytest.raises(Conflict):
        service.documents.edit("alice", document.id, DraftEdit(revision=1, values={"intro": "이전 수정"}))
    _, media, raw = service.documents.download("alice", document.id)
    result = json.loads(raw)
    assert media == "application/json" and result["draft"]
    assert len(result["fields"]) == len(JSON_FIELDS)
    assert result["fields"][0]["value"] is None and result["fields"][-1]["value"] == "내가 직접 작성한 문장"


def test_docx_replaces_split_placeholder_and_empty_cell_without_changing_original(service):
    source = make_docx()
    document = service.documents.upload("alice", "form.docx", source)
    assert [field.kind for field in document.fields] == ["project", "award", "department"]
    service.documents.generate("alice", document.id, DraftRequest())
    name, _, output = service.documents.download("alice", document.id)
    filled = Document(io.BytesIO(output))
    assert name.endswith("-draft.docx") and "Campus Data Lab" in filled.paragraphs[0].text
    assert filled.paragraphs[1].text == "수상 "
    assert filled.tables[0].cell(0, 1).text == "인공지능학과"
    assert filled.tables[0].cell(1, 1).text == "원본 기입값"
    assert service.store.get_original("alice", document.id) == source
    assert "{{project}}" in Document(io.BytesIO(source)).paragraphs[0].text


def test_fillable_pdf_updates_canonical_and_widget_while_preserving_original(service):
    source = make_pdf()
    document = service.documents.upload("alice", "test.pdf", source)
    draft = service.documents.generate("alice", document.id, DraftRequest())
    assert draft.fields[0].value == "3"
    assert draft.fields[1].status == "unsupported"
    _, media, output = service.documents.download("alice", document.id)
    row = PdfReader(io.BytesIO(output))
    fields = row.get_fields()
    assert media == "application/pdf"
    assert fields["grade"]["/V"] == "3" and fields["skill"]["/V"] == ""
    widget = row.pages[0]["/Annots"][0].get_object()
    assert widget["/V"] == "3" and widget["/AP"]["/N"].get_object().get_data()
    assert PdfReader(io.BytesIO(source)).get_fields()["grade"]["/V"] == ""
    assert service.store.get_original("alice", document.id) == source


def test_flat_pdf_wrong_formats_and_upload_size(service):
    data = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(data)
    with pytest.raises(UnsupportedDocument, match="AcroForm"):
        service.documents.upload("alice", "flat.pdf", data.getvalue())
    with pytest.raises(UnsupportedDocument):
        service.documents.upload("alice", "fake.docx", b"not a document")
    with pytest.raises(UnsupportedDocument):
        service.documents.upload("alice", "unsup.exe", b"data")
    with pytest.raises(UnsupportedDocument):
        service.documents.upload("alice", "invalid.json", b'{"fields":[{"id":"x","label":"z"},{"id":"x","label":"z"}]}')
    with pytest.raises(UploadTooLarge):
        service.documents.upload("alice", "test.docx", b"x" * (MAX_UPLOAD_BYTES + 1))


def test_unknown_labels_cannot_add_fields_and_failure_keeps_local_mapping(service):
    doc = json.dumps({"fields": [{"id": "misc", "label": "내 포트폴리오 과업"}]}, ensure_ascii=False).encode()
    service.model.field_mapping = [{"id": "misc", "kind": "project"}, {"id": "invented", "kind": "award"}]
    record = service.documents.upload("alice", "mapped.json", doc)
    assert [(field.id, field.kind) for field in record.fields] == [("misc", "project")]
    service.model.failures[FIELD_MATCHING] = ModelTimeout("fixture")
    record = service.documents.upload("alice", "fallback.json", doc)
    assert record.fields[0].kind == "unknown" and record.warnings


def test_narrative_grounding_and_missing_experience(service):
    service.model.fact_ids = ["demo-project", "invented-award"]
    response = service.documents.narrative(service.data.get_profile("alice"), "프로젝트 경험으로 지원동기")
    assert response.mock_data
    result = response.draft
    assert result.status == "draft" and [source.id for source in result.sources] == ["demo-project"]
    missing = service.documents.narrative(service.data.get_profile("bob"), "프로젝트 경험으로 지원동기").draft
    assert missing.status == "missing" and missing.value is None
    answer = ask(service, "내 프로젝트 경험을 바탕으로 지원동기를 작성해 줘.")
    assert "[AI 초안]" in answer.answer and "Campus Data Lab" in answer.answer


def test_chat_document_followup_atomic_and_owned(service):
    record = service.documents.upload("alice", "resume.json", json_template())
    result = ask(service, "이 이력서 양식을 내 정보로 작성해 줘.", page="documents", document_id=record.id)
    assert result.document.revision == 1
    result = ask(service, "프로젝트 경험도 넣어줘.", page="home")
    assert result.document.id == record.id and result.document.revision == 2
    result = ask(service, "어떤 정보가 부족해?", page="profile")
    assert "이름" in result.document.missing and result.document.revision == 2
    with pytest.raises(NotFound):
        ask(service, "문서 초안 보여 줘.", user="bob", document_id=record.id)
    with pytest.raises(NotFound):
        service.documents.download("bob", record.id)


def client_for(service):
    app = FastAPI()

    def current_user(cuk_session: str | None = Cookie(default=None)):
        users = {"alice-session": "alice", "bob-session": "bob"}
        if cuk_session not in users:
            raise HTTPException(401, "로그인이 필요해요.")
        return SimpleNamespace(id=users[cuk_session])

    @app.post("/api/chat")
    def posting_chat():
        return {"text": "공고 원문 답변", "held": True, "citations": []}

    app.include_router(make_router(current_user, service))
    return TestClient(app)


def test_router_auth_ownership_json_contract_and_existing_route(service):
    client = client_for(service)
    prefix = "/api/assistant"
    assert client.get(prefix + "/memory").status_code == 401
    client.cookies.set("cuk_session", "alice-session")
    reply = client.post(prefix + "/chat", json={
        "message": CERT_MESSAGE,
        "conversationId": "session-1",
        "context": {"page": "tree", "jobId": "mock-ai-engineer", "skillId": "mock-data-analysis"},
    })
    assert reply.status_code == 200 and reply.json()["memoryUpdated"]
    assert reply.headers["cache-control"] == "no-store"
    assert client.get(prefix + "/conversations/session-1").json()["messages"][0]["context"]["skillId"] == "mock-data-analysis"
    memory_id = client.get(prefix + "/memory").json()[0]["id"]
    reply = client.patch(prefix + f"/memory/{memory_id}", json={"kind": "certification", "value": "ADsP"})
    assert reply.status_code == 200 and reply.json()["source"] == "user_claim"
    injected = client.post(prefix + "/chat", json={"message": "test", "userId": "bob"})
    assert injected.status_code == 422 and "bob" not in injected.text
    document = client.post(prefix + "/documents?filename=resume.json", content=json_template())
    assert document.status_code == 201
    narrative = client.post(prefix + "/narrative", json={"topic": "프로젝트 경험으로 지원동기"})
    assert narrative.status_code == 200 and narrative.json()["mockData"] and narrative.json()["draft"]["status"] == "draft"
    path = f"{prefix}/documents/{document.json()['id']}"
    assert client.post(path + "/draft", json={}).status_code == 200
    assert client.get(path + "/draft/download").headers["content-disposition"].startswith("attachment")
    client.cookies.set("cuk_session", "bob-session")
    assert client.get(prefix + "/memory").json() == []
    assert client.get(prefix + "/conversations/session-1").status_code == 404
    assert client.delete(prefix + f"/memory/{memory_id}").status_code == 404
    assert client.get(path).status_code == client.get(path + "/draft/download").status_code == 404
    assert client.post("/api/chat").json() == {"text": "공고 원문 답변", "held": True, "citations": []}


def test_router_upload_limit_and_model_timeout(service):
    client = client_for(service)
    client.cookies.set("cuk_session", "alice-session")
    result = client.post("/api/assistant/documents?filename=too-big.docx", content=b"x" * (MAX_UPLOAD_BYTES + 1))
    assert result.status_code == 413 and result.json()["detail"]["code"] == "upload_too_large"
    service.model.failures[CONSULTATION] = ModelTimeout("응답 시간 초과")
    result = client.post("/api/assistant/chat", json={"message": "무엇을 공부할까?"})
    assert result.status_code == 504 and result.json()["detail"]["code"] == "model_timeout"
    assert service.memory("alice") == []


def test_router_reuses_the_main_session_dependency(service):
    import time
    from app import main

    app = FastAPI()
    app.include_router(make_router(main.current_user, service))
    app.router.routes.extend(route for route in main.app.routes if getattr(route, "path", None) == "/api/chat")
    token = "demo-session-for-test"

    class Session:
        def get(self, model, identifier):
            if model is main.SessionRow and identifier == main.token_hash(token):
                return SimpleNamespace(user_id="alice", expires_at=time.time() + 60)
            if model is main.User and identifier == "alice":
                return SimpleNamespace(id="alice")

    app.dependency_overrides[main.get_db] = Session
    client = TestClient(app)
    assert client.get("/api/assistant/memory").status_code == 401
    client.cookies.set("cuk_session", token)
    created = client.post("/api/assistant/memory", json={"kind": "interest", "value": "가상 분석"})
    assert created.status_code == 201
    assert [fact.value for fact in service.memory("alice")] == ["가상 분석"]
    assert client.post("/api/chat", json={"oppId": "made-up", "question": "언제까지예요?"}).status_code == 404
