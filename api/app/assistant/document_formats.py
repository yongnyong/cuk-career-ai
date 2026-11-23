"""Read supported template fields and fill copies using their original locations."""
import io
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException
from docx import Document
from docx.oxml.ns import qn
from docx.opc.exceptions import PackageNotFoundError
from docx.text.paragraph import Paragraph
from lxml.etree import XMLSyntaxError
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError

from .contracts import FieldKind, TemplateField, TemplateInput
from .errors import UnsupportedDocument, UploadTooLarge

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MIME_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "json": "application/json",
}
_ALIASES = {
    "personal": ("성명", "이름", "인적사항", "연락처", "이메일", "주소", "name", "fullname", "email", "phone", "personal"),
    "department": ("학과", "학부", "전공", "department", "major"),
    "grade": ("학년", "grade"),
    "status": ("학적", "재학상태", "status"),
    "education": ("학력", "교육기관", "학교", "education", "school"),
    "training": ("교육", "교육이력", "수료", "training"),
    "certification": ("자격증", "자격증명", "자격사항", "취득자격증", "자격증취득일", "취득일", "certification", "certificate", "certificates", "certificatedate"),
    "job": ("근무경력", "직장경력", "work", "employment"),
    "internship": ("인턴", "인턴십", "internship"),
    "career": ("경력", "이력", "경력사항", "career", "experience"),
    "project": ("프로젝트", "프로젝트경험", "프로젝트이력", "project", "projects"),
    "activity": ("활동", "교내외활동", "대외활동", "activity", "activities"),
    "award": ("수상", "수상경력", "award", "awards"),
    "skill": ("역량", "보유역량", "기술", "보유기술", "skill", "skills"),
    "interest": ("관심분야", "interest"),
    "goal": ("진로목표", "희망직무", "goal"),
    "narrative": ("자기소개", "자기소개서", "지원동기", "기술역량", "직무역량", "소개", "motivation", "coverletter", "narrative"),
}
_MARKER = re.compile(r"\{\{([^{}\r\n]{1,200})\}\}")
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def infer_kind(label: str) -> FieldKind:
    key = label_key(label)
    return next((kind for kind, aliases in _ALIASES.items() if key in aliases), "unknown")


def label_key(label: str) -> str:
    return re.sub(r"[\W_]+", "", label.casefold())


@dataclass
class ParsedTemplate:
    fields: list[TemplateField]
    locations: list
    warnings: list[str]
    source: object = None


def validate_upload(filename: str, contents: bytes) -> tuple[str, str]:
    if not contents:
        raise UnsupportedDocument("비어 있는 문서예요.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise UploadTooLarge("문서 크기는 최대 5MiB예요.")
    name = filename.replace("\\", "/").split("/")[-1]
    if not name or len(name) > 180 or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise UnsupportedDocument("파일 이름을 확인해 주세요.")
    suffix = PurePosixPath(name).suffix.lower().lstrip(".")
    if suffix not in MIME_TYPES:
        raise UnsupportedDocument("DOCX, 입력 가능한 PDF, JSON 양식을 지원해요.")
    return name, suffix


def _field(index: int, label: str) -> TemplateField:
    text = " ".join(label.split())[:240]
    return TemplateField(id=f"field-{index + 1}", label=text or f"양식 항목 {index + 1}", kind=infer_kind(text))


def _docx(contents: bytes) -> ParsedTemplate:
    with ZipFile(io.BytesIO(contents)) as package:
        entries = package.infolist()
        members = {entry.filename for entry in entries}
        if "[Content_Types].xml" not in members or "word/document.xml" not in members:
            raise UnsupportedDocument("일반 DOCX 파일을 업로드해 주세요.")
        if len(entries) > 1000 or sum(entry.file_size for entry in entries) > 24 * 1024 * 1024:
            raise UploadTooLarge("DOCX 압축을 푼 문서가 너무 커요.")
        for entry in entries:
            name = entry.filename.lower()
            if "vbaproject" in name or name.startswith(("word/embeddings/", "word/activex/")):
                raise UnsupportedDocument("매크로 또는 내장 개체가 있는 DOCX는 지원하지 않아요.")
            if name.endswith(".rels"):
                for relation in fromstring(package.read(entry)):
                    if relation.get("TargetMode") == "External":
                        if not (relation.get("Type", "").endswith("/hyperlink")
                                and relation.get("Target", "").lower().startswith(("https://", "http://", "mailto:"))):
                            raise UnsupportedDocument("외부 개체에 연결된 DOCX는 지원하지 않아요.")

    doc = Document(io.BytesIO(contents))
    labels, locations = [], []
    for paragraph in doc.element.body.iter(qn("w:p")):
        if next(paragraph.iterancestors(qn("w:txbxContent")), None) is not None:
            continue
        nodes = [node for node in paragraph.iter(qn("w:t"))
                 if next(node.iterancestors(qn("w:p")), None) is paragraph]
        whole = "".join(node.text or "" for node in nodes)
        for match in _MARKER.finditer(whole):
            if match[1].strip():
                labels.append(match[1])
                locations.append((nodes, match.start(), match.end()))

    for row in doc.element.body.iter(qn("w:tr")):
        cells = row.findall(qn("w:tc"))
        if len(cells) != 2:
            continue
        label = "".join(cells[0].itertext(qn("w:t"))).strip()
        value = cells[1]
        children = [child.tag for child in value]
        paragraphs = value.findall(qn("w:p"))
        if (infer_kind(label) != "unknown" and len(paragraphs) == 1
                and set(children) <= {qn("w:tcPr"), qn("w:p")}
                and all(child.tag == qn("w:pPr") or
                        (child.tag == qn("w:r") and all(item.tag == qn("w:rPr") for item in child))
                        for child in paragraphs[0])):
            labels.append(label)
            locations.append((paragraphs[0],))
    return ParsedTemplate([_field(index, label) for index, label in enumerate(labels)], locations, [], doc)


def _widget_fields(reader):
    for page in reader.pages:
        if "/AA" in page:
            raise UnsupportedDocument("페이지 동작이 포함된 PDF는 지원하지 않아요.")
        for ref in page.get("/Annots", []):
            widget = ref.get_object()
            if widget.get("/Subtype") != "/Widget":
                action = widget["/A"] if "/A" in widget else {}
                action_type = action.get("/S")
                uri = str(action.get("/URI", "")).lower()
                if ("/AA" in widget or "/Next" in action or action_type not in (None, "/URI", "/GoTo")
                        or action_type == "/URI" and not uri.startswith(("https://", "http://", "mailto:"))):
                    raise UnsupportedDocument("자동 동작이 포함된 PDF 주석은 지원하지 않아요.")
                if widget.get("/Subtype") in ("/FileAttachment", "/RichMedia", "/Screen", "/Sound", "/Movie", "/3D"):
                    raise UnsupportedDocument("내장 첨부나 재생 개체가 있는 PDF는 지원하지 않아요.")
                continue
            node = widget
            names = []
            chain = []
            while node is not None:
                if len(chain) == 20:
                    raise UnsupportedDocument("PDF 필드 구조를 해석할 수 없어요.")
                chain.append(node)
                if node.get("/T"):
                    names.insert(0, str(node["/T"]))
                if "/A" in node or "/AA" in node:
                    raise UnsupportedDocument("동작이 설정된 PDF 필드는 지원하지 않아요.")
                parent = node.get("/Parent")
                node = parent.get_object() if parent is not None else None
            yield ".".join(names), chain


def _pdf(contents: bytes) -> ParsedTemplate:
    reader = PdfReader(io.BytesIO(contents))
    if reader.is_encrypted:
        raise UnsupportedDocument("암호로 보호된 PDF는 지원하지 않아요.")
    if len(reader.pages) > 50:
        raise UploadTooLarge("PDF 양식은 최대 50페이지까지 지원해요.")
    root = reader.root_object
    form = root.get("/AcroForm")
    if form is None:
        raise UnsupportedDocument("입력 가능한 AcroForm 필드가 없는 PDF예요. 스캔본과 평면 PDF는 지원하지 않아요.")
    form = form.get_object()
    if "/XFA" in form:
        raise UnsupportedDocument("XFA 양식은 지원하지 않아요. AcroForm 양식으로 변환해 주세요.")
    names = root.get("/Names")
    if ("/OpenAction" in root or "/AA" in root
            or names is not None and ({"/JavaScript", "/EmbeddedFiles"} & set(names.get_object()))):
        raise UnsupportedDocument("스크립트·첨부 파일·자동 동작이 포함된 PDF는 지원하지 않아요.")
    fields = reader.get_fields() or {}
    widgets = list(_widget_fields(reader))
    displayed = {name for name, _ in widgets}
    if len(widgets) > 160 or len(fields) > 160:
        raise UploadTooLarge("PDF 필드가 너무 많아요.")
    if any(name and name not in fields for name in displayed):
        raise UnsupportedDocument("표준 필드 목록과 표시 위젯이 일치하지 않는 PDF예요.")
    if any(any(node.get("/FT") == "/Sig" for node in chain) for _, chain in widgets):
        raise UnsupportedDocument("서명 필드가 있는 PDF는 지원하지 않아요.")
    labels, locations, warnings = [], [], []
    for name, field in fields.items():
        if name not in displayed:
            continue
        if field.get("/FT") != "/Tx" or (field.get("/Ff", 0) & 1) or field.get("/V"):
            warnings.append("읽기 전용·기존 값·텍스트 이외의 PDF 필드는 보존합니다.")
            continue
        labels.append(str(field.get("/TU") or name))
        locations.append(name)
    return ParsedTemplate([_field(index, label) for index, label in enumerate(labels)], locations,
                          list(dict.fromkeys(warnings)), reader)


def parse_template(format: str, contents: bytes) -> ParsedTemplate:
    try:
        if format == "docx":
            parsed = _docx(contents)
        elif format == "pdf":
            if not contents.startswith(b"%PDF-"):
                raise UnsupportedDocument("파일의 실제 형식이 PDF가 아니에요.")
            parsed = _pdf(contents)
        elif format == "json":
            fields = TemplateInput.model_validate_json(contents).fields
            parsed = ParsedTemplate([
                field if field.kind != "unknown" else field.model_copy(update={"kind": infer_kind(field.label)})
                for field in fields
            ], [field.id for field in fields], [])
        else:
            raise UnsupportedDocument("지원하지 않는 문서 형식이에요.")
        if not parsed.fields:
            raise UnsupportedDocument("자동 입력할 필드를 찾지 못했어요. DOCX 자리표시자, 빈 양식 셀 또는 PDF 텍스트 필드를 확인해 주세요.")
        if len(parsed.fields) > 80:
            raise UploadTooLarge("자동 입력할 필드는 최대 80개까지 지원해요.")
        return parsed
    except (BadZipFile, PackageNotFoundError, XMLSyntaxError, DefusedXmlException, PyPdfError,
            ValidationError, UnicodeError, ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError):
        raise UnsupportedDocument("손상됐거나 지원하지 않는 구조의 문서예요.") from None


def _replace_text(nodes, start: int, end: int, value: str) -> None:
    position = 0
    inserted = False
    for node in nodes:
        text = node.text or ""
        edge = position + len(text)
        if position < end and edge > start:
            lower, upper = max(start - position, 0), min(end - position, len(text))
            node.text = text[:lower] + (value if not inserted else "") + text[upper:]
            node.set(_XML_SPACE, "preserve")
            inserted = True
        position = edge


def render_template(format: str, contents: bytes, values: dict[str, str]) -> bytes:
    parsed = parse_template(format, contents)
    output = io.BytesIO()
    entries = [(location, values[field.id]) for field, location in zip(parsed.fields, parsed.locations)
               if field.id in values]
    if format == "json":
        result = {"draft": True, "fields": [
            {**field.model_dump(mode="json"), "value": values.get(field.id)} for field in parsed.fields
        ]}
        return json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    if format == "docx":
        for field, location in reversed(list(zip(parsed.fields, parsed.locations))):
            value = values.get(field.id, "")
            value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", "", value)
            if len(location) == 1 and value:
                Paragraph(location[0], parsed.source).add_run(value)
            elif len(location) != 1:
                _replace_text(*location, " / ".join(value.splitlines()))
        parsed.source.save(output)
    elif entries:
        try:
            writer = PdfWriter(clone_from=parsed.source)
            writer.update_page_form_field_values(None, dict(entries), auto_regenerate=False)
            writer.write(output)
            result = PdfReader(io.BytesIO(output.getvalue()))
            canonical = result.get_fields() or {}
            for name, value in entries:
                visible = [chain for label, chain in _widget_fields(result) if label == name]
                if (str(canonical.get(name, {}).get("/V")) != value or not visible
                        or any(
                            str(next((node["/V"] for node in chain if "/V" in node), None)) != value
                            or not chain[0].get("/AP") or not chain[0]["/AP"].get("/N")
                            for chain in visible
                        )):
                    raise UnsupportedDocument("PDF 필드와 표시 값이 일치하지 않아 초안을 반환할 수 없어요.")
        except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, OSError, RecursionError):
            raise UnsupportedDocument("이 PDF의 입력 필드를 안전하게 작성할 수 없어요.") from None
    else:
        return contents
    return output.getvalue()
