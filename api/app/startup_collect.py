"""Build a small startup demo DB from public university and government notices.

Run from api: python -m app.startup_collect
PDF text extraction is optional: install pypdf to read the linked public PDFs.
Re-run without network: python -m app.startup_collect --reextract
"""
import argparse
import html
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser

from .collect import SKIP_TITLE, parse_body, scrub, strip_tags
from .startup_db import DEFAULT_DB, connect, digest, export_json, initialize, save_posting, summary
from .startup_extract import VERSION, application_period, application_status, category, extract_requirements
from .startup_nodes import rebuild_nodes


CUK = "https://www.catholic.ac.kr/ko/campuslife/notice.do?mode=view&articleNo="
BIZ = "https://www.bizinfo.go.kr/sii/siia/selectSIIA200Detail.do?pblancId=PBLN_000000000"
SAMPLE_URLS = [
    "https://business.catholic.ac.kr/business/community/notice.do?mode=view&articleNo=277825",
    *[CUK + article for article in ("277684", "275912", "276113", "270222", "270315")],
    "https://cukai.catholic.ac.kr/ai/community/notice.do?mode=view&articleNo=276869",
    *[BIZ + number for number in (
        "119859", "123352", "119021", "120276", "123273", "124885", "126774", "121634", "122308",
    )],
]
UA = "CUK-Startup-Demo/0.1 (public student project)"
ALLOWED_HOSTS = {urllib.parse.urlsplit(url).hostname for url in SAMPLE_URLS}
MAX_BYTES = 12 * 1024 * 1024


class PublicFetcher:
    def __init__(self):
        self.last = {}
        self.robots = {}

    def download(self, url):
        host = urllib.parse.urlsplit(url).hostname
        pause = 3 - (time.monotonic() - self.last.get(host, 0))
        if pause > 0:
            time.sleep(pause)
        self.last[host] = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as response:
            final_host = urllib.parse.urlsplit(response.url).hostname
            if final_host not in ALLOWED_HOSTS:
                raise ValueError("Unexpected redirect host")
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("Public document exceeds size limit")
            return data

    def get(self, url):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
            raise ValueError("Only configured public source hosts are supported")
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.robots:
            policy = RobotFileParser()
            try:
                policy.parse(self.download(origin + "/robots.txt").decode("utf-8").splitlines())
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                policy.parse([])
            self.robots[origin] = policy
        if not self.robots[origin].can_fetch(UA, url):
            raise ValueError("Source robots policy disallows this URL")
        return self.download(url)


def canonical(url):
    parts = urllib.parse.urlsplit(html.unescape(url))
    query = urllib.parse.parse_qs(parts.query)
    if parts.hostname and parts.hostname.endswith("catholic.ac.kr") and "articleNo" in query:
        return urllib.parse.urlunsplit(("https", parts.netloc, parts.path,
                                       urllib.parse.urlencode({"mode": "view", "articleNo": query["articleNo"][0]}), ""))
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def notice_id(url):
    params = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    if urllib.parse.urlsplit(url).hostname == 'www.k-startup.go.kr' and 'pbancSn' in params:
        return 'kstartup-' + params['pbancSn'][0]
    return "cuk-" + params["articleNo"][0] if "articleNo" in params else "biz-" + params["pblancId"][0]


def attachment_role(name):
    if re.search(r"공고|매뉴얼|안내|질의응답|소개자료|제출목록|포스터|목록", name):
        return "reference"
    if re.search(r"양식|서식|신청서|동의서|계획서|서약서|제출서류", name):
        return "template"
    return "unknown"


def attachments_from_html(page, url):
    found = {}
    # Catholic CMS exposes stable download links. Metadata only, unless reading is permitted.
    for href, label in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        href = html.unescape(href)
        name = strip_tags(label).strip()
        if "mode=download" in href and name:
            address = urllib.parse.urljoin(url, href)
            found[address] = {"url": address, "name": name}
    # Bizinfo previews expose public storage paths without the transient download token.
    for folder, filename, name in re.findall(
        r"file(?:Blank|Load)\('([^']+)'\s*\+\s*'/'\s*\+\s*'([^']+)'\s*,\s*'([^']+)'", page,
    ):
        address = urllib.parse.urljoin(url, folder.rstrip("/") + "/" + filename)
        found[address] = {"url": address, "name": html.unescape(name)}
    # The site's current download button carries a short-lived token. Use it only
    # in memory, retaining a stable token-free attachment identifier in the DB.
    for block in re.findall(r"<li\b[^>]*>(.*?)</li>", page, re.S):
        name_match = re.search(r'class="file_name"[^>]*>(.*?)</div>', block, re.S)
        link_match = re.search(r'href="([^"]*fileDown\.do[^"]*)"', block)
        if not name_match or not link_match:
            continue
        name = strip_tags(name_match[1])
        fetch_url = urllib.parse.urljoin(url, html.unescape(link_match[1]))
        parts = urllib.parse.urlsplit(fetch_url)
        params = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "downloadToken"]
        address = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(params), ""))
        found = {key: value for key, value in found.items() if value["name"] != name}
        found[address] = {"url": address, "name": name, "_fetch_url": fetch_url}
    return [{**item, "role": attachment_role(item["name"]), "extraction_status": "not_read"}
            for item in found.values()]


def parse_notice(page, url):
    if "bizinfo.go.kr" in url:
        title_match = re.search(r'<h2\b[^>]*class="title"[^>]*>(.*?)</h2>', page, re.S)
        start = page.find('class="view_cont"')
        end = page.find('id="iframe"', start)
        if start < 0 or end < 0:
            raise ValueError("Business notice content block missing")
        body = strip_tags(page[page.find(">", start) + 1:end].split('<a href="javascript:void(0);"')[0])
    else:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', page, re.S)
        body = parse_body(page)
    if not title_match or len(body.strip()) < 60:
        raise ValueError("Notice title or substantive body missing")
    title = strip_tags(title_match[1]).split(" | ")[0].strip()
    if SKIP_TITLE.search(title):
        raise ValueError("Results and personal lists are excluded")
    pub = re.search(r'등록일[\s\S]{0,180}?(20\d{2}[.-]\d{2}[.-]\d{2})', strip_tags(page))
    if not pub:
        pub = re.search(r'class="top_info"[\s\S]{0,400}?(20\d{2}\.\d{2}\.\d{2})', page)
    return title, scrub(re.sub(r"<[^>]*$", "", body)).strip(), pub[1].replace(".", "-") if pub else None


def source_record(posting_id, url, kind, content, now):
    content = scrub(content).replace("\x00", "")
    content = "\n".join(line.rstrip() for line in content.splitlines()).strip()
    return {"id": digest(f"{posting_id}|{url}|{kind}|{content}"), "posting_id": posting_id,
            "url": url, "kind": kind, "content": content, "content_hash": digest(content), "fetched_at": now}


def read_pdf(fetcher, attachment):
    from pypdf import PdfReader
    data = fetcher.get(attachment.get("_fetch_url", attachment["url"]))
    if not data.startswith(b"%PDF"):
        raise ValueError("Link did not return a PDF")
    reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) > 60:
        raise ValueError("PDF exceeds demo page limit")
    chunks = []
    for number, page in enumerate(reader.pages, 1):
        content = page.extract_text() or ""
        chunks.append(f"[PDF page {number}]\n{content}")
    text = "\n".join(chunks)
    if len(re.sub(r"\s|\[PDF page \d+\]", "", text)) < 80:
        raise ValueError("Image PDF requires OCR review")
    return text


def build_posting(url, title, published, sources, attachments, now):
    body = sources[0]["content"]
    year_match = re.search(r"20\d{2}", published or title)
    year = int(year_match[0]) if year_match else int(now[:4])
    period, start, end, date_note = application_period(body, year)
    notes = []
    if date_note:
        notes.append(date_note)
    if any(a["extraction_status"] not in ("extracted", "reference_not_parsed") for a in attachments):
        notes.append("미열람 첨부가 있어 제출서류 목록의 완전성 확인 필요")
    if sources[0].get("image_count", 0):
        notes.append("본문에 이미지가 있어 이미지 내 조건·서류 확인 필요")
    if "bizinfo" in url:
        notes.append("기업마당 요약 공고. 최종 자격·제출 기준은 수행기관 원문 확인 필요")
    requirements = [row for source in sources for row in extract_requirements(source, year, attachments)]
    supported_types = {row["document_type"] for row in requirements if row["necessity"] != "needs_review"}
    requirements = [row for row in requirements
                    if row["necessity"] != "needs_review" or row["document_type"] not in supported_types]
    for row in requirements:
        if row["stage"] == "application" and not row["deadline_date"] and end:
            row.update(deadline_text=period, deadline_date=end, deadline_precision="day")
    if not any(r["necessity"] != "needs_review" for r in requirements):
        notes.append("본문에서 명시적 제출물 미추출. 서류 없음으로 해석하지 않음")
    eligibility = "\n".join(line for line in body.splitlines() if re.search(
        r"대상|자격|예비창업|재학생|전공|팀장|팀원|인\s*이상|인\s*구성|사업자|거주|소재|업력", line))
    support = "\n".join(line for line in body.splitlines() if re.search(
        r"지원|활동비|상금|시상|멘토링|보육|장비|창업\s*자금", line))
    posting = {
        "id": notice_id(url), "title": title, "source_url": url,
        "source_site": "K-Startup(창업진흥원)" if 'k-startup.go.kr' in url else "기업마당" if "bizinfo" in url else "가톨릭대학교",
        "category": category(title), "published_date": published,
        "application_period": period, "application_start": start, "application_end": end,
        "application_end_precision": "day" if end else None,
        "application_status": application_status(start, end, body, now[:10]),
        "eligibility_text": eligibility, "support_text": support,
        "review_notes": json.dumps(notes, ensure_ascii=False),
        "content_hash": digest("\n".join(sorted(s["content_hash"] for s in sources))),
        "fetched_at": now, "extractor_version": VERSION,
    }
    return posting, requirements


def collect_one(fetcher, url, read_pdfs=True):
    url = canonical(url)
    page = fetcher.get(url).decode("utf-8", errors="replace")
    title, body, published = parse_notice(page, url)
    now = datetime.now(timezone.utc).isoformat()
    posting_id = notice_id(url)
    attachments = [{**a, "posting_id": posting_id} for a in attachments_from_html(page, url)]
    sources = [source_record(posting_id, url, "html", body, now)]
    sources[0]["image_count"] = len(re.findall(r"<img\b", page[page.find('class="b-content-box"'):], re.I)) if "catholic" in url else 0
    for attachment in attachments:
        if re.search(r"매뉴얼|질의응답|FAQ|소개자료|포스터|웹포스터", attachment["name"], re.I):
            attachment["extraction_status"] = "reference_not_parsed"
            continue
        if not attachment["name"].lower().endswith(".pdf"):
            attachment["extraction_status"] = "needs_attachment_review"
            continue
        if not read_pdfs:
            continue
        try:
            content = read_pdf(fetcher, attachment)
            kind = "template" if attachment["role"] == "template" else "pdf"
            sources.append(source_record(posting_id, attachment["url"], kind, content, now))
            attachment["extraction_status"] = "extracted"
        except (ImportError, ValueError, OSError, urllib.error.URLError) as exc:
            attachment["extraction_status"] = "needs_pdf_review"
            print(f"  PDF review needed: {attachment['name']} ({type(exc).__name__})", flush=True)
    if attachments:
        sources.append(source_record(posting_id, url, "attachment_index", "\n".join(a["name"] for a in attachments), now))
    posting, requirements = build_posting(url, title, published, sources, attachments, now)
    return posting, sources, attachments, requirements


def reextract(db):
    for stored in db.execute("SELECT * FROM postings").fetchall():
        attachments = [dict(row) for row in db.execute("SELECT * FROM attachments WHERE posting_id=? ORDER BY url", (stored["id"],))]
        templates = {a["url"] for a in attachments if a["role"] == "template"}
        sources = [source_record(row["posting_id"], row["url"],
                                 "template" if row["kind"] == "pdf" and row["url"] in templates else row["kind"],
                                 row["content"], row["fetched_at"])
                   for row in db.execute("SELECT * FROM sources WHERE posting_id=? AND current=1 ORDER BY CASE kind WHEN 'html' THEN 0 ELSE 1 END, id", (stored["id"],))]
        posting, requirements = build_posting(stored["source_url"], stored["title"], stored["published_date"], sources, attachments, stored["fetched_at"])
        # Retain observation-only gaps that cannot be recovered from normalized text.
        observation_notes = [note for note in json.loads(stored["review_notes"]) if note.startswith("본문에 이미지")]
        notes = list(dict.fromkeys(json.loads(posting["review_notes"]) + observation_notes))
        posting["review_notes"] = json.dumps(notes, ensure_ascii=False)
        save_posting(db, posting, sources, attachments, requirements)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=len(SAMPLE_URLS))
    parser.add_argument("--skip-pdfs", action="store_true")
    parser.add_argument("--reextract", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--export", type=Path, help="Export public data to portable JSON")
    args = parser.parse_args()
    if args.db.resolve() in {DEFAULT_DB.with_name("career.db"), DEFAULT_DB.with_name("dev.db")}:
        parser.error("Use a dedicated startup database path")
    initialize(args.db)
    failures = []
    with connect(args.db) as db:
        if args.reextract:
            reextract(db)
        elif not args.summary:
            fetcher = PublicFetcher()
            for url in SAMPLE_URLS[:max(0, args.limit)]:
                try:
                    posting, sources, attachments, requirements = collect_one(fetcher, url, not args.skip_pdfs)
                    save_posting(db, posting, sources, attachments, requirements)
                    print(f"Saved {posting['id']}: {posting['title']} / {len(requirements)} evidence records", flush=True)
                except (OSError, ValueError, urllib.error.URLError) as exc:
                    failures.append({"url": url, "error": type(exc).__name__})
                    print(f"Fetch failed: {url} ({type(exc).__name__})", flush=True)
        if args.reextract or not args.summary:
            rebuild_nodes(db)
        result = {**summary(db), "failures": failures, "db": str(args.db.resolve())}
        if args.export:
            export_json(db, args.export)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
