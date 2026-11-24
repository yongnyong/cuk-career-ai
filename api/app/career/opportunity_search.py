"""Public posting chunks, BM25 retrieval and optional cached embedding retrieval."""
import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from ..career_db import SearchSection
from .embeddings import EmbeddingUnavailable, configured_embeddings


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def canonical_url(value):
    parts = urlsplit(value)
    query = [(key, value) for key, value in parse_qsl(parts.query)
             if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(sorted(query)), ""))


def current_postings(rows):
    """Deduplicate IDs first, then reposts sharing the same official URL and domain."""
    by_id = {}
    for row in rows:
        if not row or row.get("isVirtual") or not row.get("id") or not row.get("versions"):
            continue
        previous = by_id.get(row["id"])
        version = row["versions"][-1]
        if previous is None or (version["version"], version.get("checkedAt", "")) > (
                previous["versions"][-1]["version"], previous["versions"][-1].get("checkedAt", "")):
            by_id[row["id"]] = row
    result = {}
    for row in by_id.values():
        kind = "startup" if row.get("type") == "창업지원" else "employment"
        url = row.get("source", {}).get("url") or row.get("applyUrl", "")
        key = (kind, canonical_url(url), re.sub(r"\s+", "", row.get("title", "")).lower()) if url else (kind, row["id"])
        previous = result.get(key)
        if previous is None or row["versions"][-1].get("checkedAt", "") > previous["versions"][-1].get("checkedAt", ""):
            result[key] = row
    return sorted(result.values(), key=lambda row: row["id"])


@dataclass(frozen=True)
class Section:
    id: str
    posting_id: str
    kind: str
    version: int
    section_id: str
    title: str
    source_url: str
    quote: str
    content_hash: str

    def citation(self):
        return dict(postingId=self.posting_id, version=self.version, sectionId=self.section_id,
                    quote=self.quote, sourceUrl=self.source_url,
                    basis="metadata" if self.section_id.startswith("title:") else "source")


def posting_sections(rows):
    sections = []
    for row in current_postings(rows):
        version = row["versions"][-1]["version"]
        kind = "startup" if row.get("type") == "창업지원" else "employment"
        url = row.get("source", {}).get("url") or row.get("applyUrl", "")
        if not re.fullmatch(r"https?://[^\s]+", url):
            continue
        source_sections = [{"id": "title", "text": row.get("title", "")}, *row.get("sections", [])]
        for source in source_sections:
            if re.search(r"직무 연결|검수|주의사항|분류 참고", source.get("title", "")):
                continue
            if source.get("title") == "모집 기한":
                continue
            if source.get("title") == "공고" and source.get("text") in {
                    row.get("title"), f"{row.get('org')} · {row.get('title')}"}:
                continue
            if source.get("provenance") in {"service", "generated", "summary"}:
                continue
            requirement = next((item for item in row.get("startup", {}).get("requirements", [])
                                if item.get("id") == source.get("id")), None)
            source_url = (requirement or {}).get("evidence_url") or url
            if not re.fullmatch(r"https?://[^\s]+", source_url):
                source_url = url
            text = source.get("text", "")
            if re.search(r"지원 조건은 원문 링크에서 확인|원문에서 제출서류·접수 방법·모집 부문을 확인", text):
                continue
            # Every quote remains an exact substring of one current original section.
            for start in range(0, len(text), 900):
                quote = text[start:start + 1100].strip()
                if not quote:
                    continue
                sid = str(source.get("id", "body")) + ":" + str(start)
                content_hash = digest(row.get("title", "") + "\n" + source_url + "\n" + quote)
                key = digest(f"{row['id']}|{version}|{sid}|{content_hash}")
                sections.append(Section(key, row["id"], kind, version, sid,
                    row.get("title", ""), source_url, quote, content_hash))
    return sections


_STOP = {"취업", "창업", "추천", "공고", "준비", "지원", "위한", "모집", "있는", "하고", "싶어", "주세요",
         # 채용 공고 어디에나 나오는 말: 이 단어 하나로 간호사·물류직 공고가 AI 연구원 추천에 걸렸다
         "연구원", "신입", "경력", "사원", "직원", "채용", "담당", "업무", "학과"}
# 긴 단어를 두 글자씩 나눌 때 생기는 흔한 조각("인공지능학과" → "공지"·"학과")
_STOP_GRAMS = {"공지", "학과", "모집", "채용", "업무", "담당", "지원", "신입", "경력", "사원", "직원"}
_SUPPORT_TOPICS = (
    (r"판로|바이어|구매처", ("판로", "바이어", "구매처", "판매망", "유통")),
    (r"시제품.*(?:제작|지원|자금|개발)|제작비|개발비", ("시제품", "제작비", "개발비", "프로토타입", "poc")),
    (r"경진대회|창업대회|창업경진", ("경진대회", "창업대회", "창업경진", "해커톤")),
)


def tokens(text):
    terms = []
    for word in re.findall(r"[a-z][a-z0-9+#.]*|[0-9]+|[가-힣]+", text.lower()):
        if word in _STOP:
            continue
        terms.append(word)
        if re.fullmatch(r"[가-힣]{3,}", word):
            terms.extend(gram for gram in (word[i:i + 2] for i in range(len(word) - 1)) if gram not in _STOP_GRAMS)
    return terms


def keyword_scores(sections, query):
    words = set(tokens(query))
    documents = [Counter(tokens(section.quote)) for section in sections]
    frequencies = Counter(term for document in documents for term in document)
    average = sum(sum(document.values()) for document in documents) / max(1, len(documents))
    scores = {}
    for section, document in zip(sections, documents):
        score = 0.0
        length = sum(document.values())
        for term in words & document.keys():
            frequency = document[term]
            idf = math.log(1 + (len(documents) - frequencies[term] + .5) / (frequencies[term] + .5))
            score += idf * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * length / max(average, 1)))
        if score > 0:
            scores[section.id] = score
    return scores


def posting_ranks(sections, scores):
    best = {}
    for section in sections:
        if section.id in scores:
            best[section.posting_id] = max(best.get(section.posting_id, 0), scores[section.id])
    return sorted(best, key=lambda pid: (-best[pid], pid))


class OpportunitySearch:
    def __init__(self, sessions, source, embeddings=None):
        self.sessions, self.source, self.embeddings = sessions, source, embeddings
        self.lock = RLock()
        self.fingerprint = ""
        self.sections = []
        self.postings = {}

    def refresh(self):
        with self.lock:
            postings = current_postings(self.source())
            sections = posting_sections(postings)
            fingerprint = digest("|".join(section.id for section in sections))
            if fingerprint != self.fingerprint:
                ids = {section.id for section in sections}
                # Publish one complete snapshot in a transaction. Existing vectors retain their IDs.
                for attempt in range(2):
                    try:
                        with self.sessions() as db, db.begin():
                            existing = set(db.scalars(select(SearchSection.id)).all())
                            for section in sections:
                                if section.id not in existing:
                                    db.add(SearchSection(**asdict(section)))
                            if ids:
                                db.execute(delete(SearchSection).where(SearchSection.id.not_in(ids)))
                            else:
                                db.execute(delete(SearchSection))
                        break
                    except IntegrityError:
                        if attempt:
                            raise
                self.sections, self.fingerprint = sections, fingerprint
            self.postings = {row["id"]: row for row in postings}
            return list(self.sections), dict(self.postings)

    def index_embeddings(self, batch_size=24):
        if not self.embeddings:
            raise EmbeddingUnavailable("GEMINI_API_KEY와 임베딩 모델을 설정하세요.")
        sections, _ = self.refresh()
        with self.sessions() as db:
            existing = {row.id for row in db.scalars(select(SearchSection)).all()
                        if row.embedding_model == self.embeddings.model
                        and row.embedding_dimensions == self.embeddings.dimensions and row.embedding}
        pending = [section for section in sections if section.id not in existing]
        for start in range(0, len(pending), batch_size):
            batch = pending[start:start + batch_size]
            vectors = self.embeddings.embed([section.title + "\n" + section.quote for section in batch])
            with self.sessions() as db, db.begin():
                for section, vector in zip(batch, vectors):
                    row = db.get(SearchSection, section.id)
                    if row:
                        row.embedding = vector
                        row.embedding_model = self.embeddings.model
                        row.embedding_dimensions = self.embeddings.dimensions
        return len(pending)

    def search(self, query, kind, *, offset=0, limit=100, focus=""):
        from ..assistant.privacy import redact
        query = redact(query).strip()[:600]
        sections, _ = self.refresh()
        sections = [section for section in sections if section.kind == kind]
        topic = next((words for pattern, words in _SUPPORT_TOPICS if kind == "startup"
                      and re.search(pattern, focus)), ())
        if topic:
            matching = {section.posting_id for section in sections
                        if any(word in section.quote.lower() for word in topic)}
            sections = [section for section in sections if section.posting_id in matching]
        lexical = keyword_scores(sections, query)
        ranks = [posting_ranks(sections, lexical)]
        semantic = {}
        mode = "keyword"
        if self.embeddings and tokens(query):
            ids = {section.id for section in sections}
            with self.sessions() as db:
                vectors = [row for row in db.scalars(select(SearchSection).where(
                    SearchSection.embedding_model == self.embeddings.model,
                    SearchSection.embedding_dimensions == self.embeddings.dimensions)).all()
                    if row.id in ids and row.embedding]
            if vectors:
                try:
                    vector = self.embeddings.query(query)
                    for row in vectors:
                        if len(row.embedding) == len(vector):
                            score = sum(a * b for a, b in zip(vector, row.embedding))
                            if math.isfinite(score) and score >= .55:
                                semantic[row.id] = score
                    ranks.append(posting_ranks(sections, semantic))
                    mode = "hybrid"
                except EmbeddingUnavailable:
                    mode = "keyword_fallback"
        combined = defaultdict(float)
        for ranking in ranks:
            for rank, pid in enumerate(ranking, 1):
                combined[pid] += 1 / (60 + rank)
        ordered = sorted(combined, key=lambda pid: (-combined[pid], pid))
        grouped = defaultdict(list)
        for section in sections:
            if section.id in lexical or section.id in semantic:
                grouped[section.posting_id].append(section)
        hits = []
        for pid in ordered[offset:offset + limit]:
            evidence = sorted(grouped[pid], key=lambda section: (
                -lexical.get(section.id, 0) - semantic.get(section.id, 0), section.id))[:3]
            hits.append(dict(postingId=pid, version=evidence[0].version, score=combined[pid],
                             evidence=[section.citation() for section in evidence]))
        end = offset + len(hits)
        return dict(query=query, mode=mode, indexVersion=self.fingerprint, total=len(ordered),
                    nextOffset=end if end < len(ordered) else None, hits=hits)

    def evidence(self, posting_ids, query):
        sections, _ = self.refresh()
        selected = [section for section in sections if section.posting_id in posting_ids]
        scores = keyword_scores(selected, query)
        result = []
        for pid in posting_ids:
            candidates = [section for section in selected if section.posting_id == pid]
            matched = [section for section in candidates if scores.get(section.id, 0) > 0]
            if matched:
                candidates = matched
            candidates.sort(key=lambda section: (-scores.get(section.id, 0), section.section_id))
            result.extend(candidates[:3])
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", action="store_true")
    parser.add_argument("--embed", action="store_true")
    parser.add_argument("--startup-catalog")
    args = parser.parse_args()
    if not (args.index or args.embed or args.startup_catalog):
        parser.error("--index 또는 --embed를 선택하세요.")
    from pathlib import Path
    from ..career_db import CareerSessionLocal, Posting
    from ..assistant.service_data import ServiceCareerData
    import time
    if args.startup_catalog:
        rows = json.loads(Path(args.startup_catalog).read_text(encoding="utf-8"))["opportunities"]
        with CareerSessionLocal() as db, db.begin():
            for row in rows:
                if not row.get("isVirtual") and row.get("startup") and db.get(Posting, row["id"]) is None:
                    db.add(Posting(id=row["id"], raw_hash=digest(json.dumps(row, sort_keys=True)),
                                   data=row, checked_at=int(time.time())))
    data = ServiceCareerData(CareerSessionLocal, Posting, lambda user: None)
    search = OpportunitySearch(CareerSessionLocal, data.public_postings, configured_embeddings())
    sections, postings = search.refresh()
    embedded = search.index_embeddings() if args.embed else 0
    print(json.dumps(dict(postings=len(postings), sections=len(sections), embedded=embedded,
        embeddingModel=search.embeddings.model if search.embeddings else None), ensure_ascii=False))


if __name__ == "__main__":
    main()

