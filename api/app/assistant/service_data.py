"""개인 진로 비서를 실제 서비스 자료에 연결한다.

- 학생 정보: 계정에 저장된 프로필(User.state.profile)에서 학과·학년·학적·목표·완료한 노드만 꺼낸다.
  아이디·입학년도·지역·출생연도·점수는 넘기지 않는다. 시연 계정은 브라우저가 보낸 시연 프로필을 쓴다.
- 공고: 공고 DB(Posting)의 웹 공고 형식을 비서 형식으로 바꾼다. 마감일이 확인되지 않은 공고는 판정할 수 없어 뺀다.
- 스킬트리: 웹과 같은 career/web_catalog.json.
- 저장: 로그인 계정은 Postgres(assistant_states·assistant_originals), 시연 계정은 서버 메모리(최근 사용자만, 재시작 시 삭제).
"""
import json
import re
import time
from collections import OrderedDict
from collections.abc import Callable
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Integer, JSON, LargeBinary, String, delete, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column

from .contracts import Condition, DocumentRecord, Draft, Fact, Opportunity, Profile, UserState
from .errors import Conflict, NotFound, StorageUnavailable
from .repository import MAX_DOCUMENTS
from .skill_context import CatalogSkillData

KST = timezone(timedelta(hours=9))
CATALOG = json.loads((Path(__file__).resolve().parent.parent / "career/web_catalog.json").read_text(encoding="utf-8"))
DEPT = {d["id"]: d["name"] for d in CATALOG["departments"]}
FIELD_DEPTS: dict[str, list[str]] = {}
for _d in CATALOG["departments"]:
    FIELD_DEPTS.setdefault(_d.get("field", ""), []).append(_d["name"])
JOB = {j["id"]: j["name"] for j in CATALOG["jobs"]}
SKILL = {s["id"]: s["name"] for s in CATALOG["skills"]}
STAGE = {"pre": "예비창업자", "1": "창업 1년 미만", "3": "창업 3년 미만", "7": "창업 7년 미만", "10": "창업 10년 미만"}
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
URL = re.compile(r"^https?://[^\s]+$")
# 이번 요청에서 웹 규칙 엔진이 이 학생에게 고른 공고 ID(직무·역량·전공 기준). 있으면 비서는 이 안에서만 공고를 고른다
FOCUS: ContextVar[tuple[str, ...] | None] = ContextVar("assistant_focus", default=None)
RETRIEVAL_QUERY: ContextVar[str] = ContextVar("assistant_retrieval_query", default="")


def _fact_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", text)[:80]


def profile_facts(p: dict | None) -> Profile:
    """웹 프로필 → 비서의 등록 정보. 서비스에 직접 등록한 값이라 출처는 system, 스스로 표시한 노드는 user_claim."""
    if not p:
        return Profile()
    facts: list[Fact] = []

    def add(fid: str, kind: str, value: Any, source: str = "system") -> None:
        text = str(value or "").strip()[:240]
        if text:
            facts.append(Fact(id=_fact_id(fid), kind=kind, value=text, source=source))

    add("profile-department", "department", DEPT.get(p.get("departmentId", "")))
    if isinstance(p.get("grade"), int) and 1 <= p["grade"] <= 9:
        add("profile-grade", "grade", p["grade"])
    if p.get("status") in ("재학", "휴학", "졸업예정"):
        add("profile-status", "status", p["status"])
    job = JOB.get(p.get("jobId", ""))
    if p.get("careerInterest") == "startup":
        stage = STAGE.get(str((p.get("startup") or {}).get("stage", "")))
        add("profile-goal", "goal", " · ".join(x for x in ("창업", stage, job) if x))
    else:
        add("profile-goal", "goal", f"취업 · {job}" if job else "취업")
    for sid, state in (p.get("skills") or {}).items():
        if state in ("self", "verified") and sid in SKILL:
            add(f"profile-skill-{sid}", "skill", SKILL[sid], "system" if state == "verified" else "user_claim")
    return Profile(facts=facts[:60])


def _condition(c: dict) -> Condition:
    label = (str(c.get("label") or "").strip() or "조건")[:240]
    key = c.get("key")
    if key == "status" and c.get("status"):
        return Condition(kind="status", label=label, values=c["status"][:20])
    if key == "grade" and c.get("grades"):
        return Condition(kind="grade", label=label, values=[str(g) for g in c["grades"]][:20])
    if key == "major" and c.get("majors"):
        names = [n for f in c["majors"] for n in FIELD_DEPTS.get(f, [])]
        if 0 < len(names) <= 20:
            return Condition(kind="department", label=label, values=names)
    if key == "skill" and c.get("skill") in SKILL and not c.get("min"):
        return Condition(kind="skill", label=label, values=[SKILL[c["skill"]]])
    # 학력·창업 단계·연령·지역·점수 조건은 비서가 판정하지 않고 '확인 필요'로 둔다(웹 규칙 엔진이 판정)
    return Condition(kind="other", label=label)


def to_opportunity(o: dict) -> Opportunity | None:
    try:
        if not ID.match(str(o.get("id", ""))):
            return None
        v = (o.get("versions") or [{}])[-1]
        if o.get("deadlineStatus") == "unknown" or not v.get("deadline"):
            return None
        deadline = datetime.fromisoformat(str(v["deadline"]).replace("Z", "+00:00"))
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=KST)
        if o.get("deadlineStatus") == "date_only":
            deadline = deadline.astimezone(KST).replace(hour=23, minute=59, second=59, microsecond=999999)
        body = "\n".join(f"{s.get('title', '')}: {s.get('text', '')}" for s in o.get("sections") or [])
        url = o.get("applyUrl") or (o.get("source") or {}).get("url") or ""
        return Opportunity(
            id=o["id"],
            type="startup" if o.get("type") == "창업지원" else "employment",
            title=str(o.get("title") or o["id"])[:240],
            organization=(str(o.get("org") or "").strip() or "기관 미상")[:240],
            description=(body.strip() or str(o.get("title") or o["id"]))[:2000],
            deadline=deadline,
            conditions=[_condition(c) for c in (o.get("required") or [])[:30]],
            documents=[str(x)[:240] for x in (o.get("documents") or []) if str(x).strip()][:30],
            mock=bool(o.get("isVirtual")),
            source_url=url if URL.match(url) and len(url) <= 2000 else None,
            version=v["version"] if isinstance(v.get("version"), int) and v["version"] >= 1 else None,
        )
    except (ValidationError, ValueError, TypeError, KeyError):
        return None


class ServiceCareerData:
    def __init__(self, career_session: Callable, Posting, profile_of: Callable[[str], dict | None], ttl: float = 300):
        self.career_session, self.Posting, self.profile_of, self.ttl = career_session, Posting, profile_of, ttl
        self.skills = CatalogSkillData(CATALOG)
        self._cache: tuple[float, dict[str, Opportunity]] = (0.0, {})
        self._lock = Lock()

    def public_postings(self) -> list[dict]:
        with self.career_session() as db:
            rows = [row for row in db.scalars(select(self.Posting.data)).all() if row]
        from ..startup_catalog import catalog
        from ..startup_db import DEFAULT_DB, connect
        if Path(DEFAULT_DB).is_file():
            with connect(DEFAULT_DB) as db:
                rows.extend(catalog(db)["opportunities"])
        from ..career.opportunity_search import current_postings
        return current_postings(rows)

    def get_profile(self, user_id: str) -> Profile:
        return profile_facts(self.profile_of(user_id))

    def _all(self) -> dict[str, Opportunity]:
        with self._lock:
            at, items = self._cache
            if time.monotonic() - at > self.ttl:
                rows = self.public_postings()
                items = {o.id: o for o in (to_opportunity(r) for r in rows if r) if o}
                self._cache = (time.monotonic(), items)
            return items

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        row = next((row for row in self.public_postings() if row["id"] == opportunity_id), None)
        return to_opportunity(row) if row else None

    def get_startup_posting(self, opportunity_id: str) -> dict | None:
        with self.career_session() as db:
            row = db.get(self.Posting, opportunity_id)
            if row and row.data and row.data.get("startup"):
                return row.data
        # The public startup catalog has its own database and publish path.
        # Read the same source as GET /api/startup/catalog when no career copy exists.
        from ..startup_catalog import catalog
        from ..startup_db import DEFAULT_DB, connect
        if Path(DEFAULT_DB).is_file():
            with connect(DEFAULT_DB) as db:
                return next((item for item in catalog(db)["opportunities"] if item["id"] == opportunity_id), None)
        return None

    def list_opportunities(self) -> list[Opportunity]:
        focus = FOCUS.get()
        if focus is not None:
            items = {item.id: item for item in (to_opportunity(row) for row in self.public_postings()) if item}
            return [items[pid] for pid in focus if pid in items]
        return [item.model_copy(deep=True) for item in self._all().values()]

    def focused_ids(self):
        return FOCUS.get()

    def get_skill_node(self, job_id, skill_id):
        return self.skills.get_skill_node(job_id, skill_id)

    def get_skill_tree(self, job_id):
        return self.skills.get_skill_tree(job_id)

    def list_career_roles(self):
        return self.skills.list_career_roles()


class _DocumentMixin:
    """문서 메서드는 get_state·save_state 위에서 같은 규칙으로 동작한다."""

    def get_document(self, user_id: str, document_id: str) -> DocumentRecord:
        record = self.get_state(user_id).documents.get(document_id)
        if not record:
            raise NotFound("문서를 찾을 수 없어요.")
        return record

    def save_draft(self, user_id: str, document_id: str, draft: Draft) -> None:
        state = self.get_state(user_id)
        document = state.documents.get(document_id)
        if not document:
            raise NotFound("문서를 찾을 수 없어요.")
        if (document.draft.revision if document.draft else 0) + 1 != draft.revision:
            raise Conflict("문서 초안이 변경됐어요. 새로 조회한 뒤 다시 시도해 주세요.")
        document.draft = draft
        self.save_state(user_id, state)

    def clear_conversation(self, user_id: str, conversation_id: str) -> None:
        state = self.get_state(user_id)
        if state.conversations.pop(conversation_id, None) is not None:
            self.save_state(user_id, state)


def make_pg_store(Base, SessionLocal):
    class AssistantStateRow(Base):
        __tablename__ = "assistant_states"
        user_id: Mapped[str] = mapped_column(String(80), primary_key=True)
        revision: Mapped[int] = mapped_column(Integer)
        data: Mapped[dict] = mapped_column(JSON)

    class AssistantOriginal(Base):
        __tablename__ = "assistant_originals"
        user_id: Mapped[str] = mapped_column(String(80), primary_key=True)
        document_id: Mapped[str] = mapped_column(String(80), primary_key=True)
        content: Mapped[bytes] = mapped_column(LargeBinary)

    class PgAssistantStore(_DocumentMixin):
        """사용자 ID로 범위를 제한하고, 읽은 revision과 같을 때만 저장한다(낙관적 잠금)."""

        def get_state(self, user_id: str) -> UserState:
            try:
                with SessionLocal() as db:
                    row = db.get(AssistantStateRow, user_id)
                    if not row:
                        return UserState()
                    return UserState.model_validate({**row.data, "revision": row.revision})
            except (SQLAlchemyError, ValidationError):
                raise StorageUnavailable("저장된 데이터를 읽을 수 없어요.") from None

        @staticmethod
        def _write(db, user_id: str, state: UserState) -> None:
            data = json.loads(state.model_dump_json())
            if state.revision == 0:
                db.add(AssistantStateRow(user_id=user_id, revision=1, data=data))
                db.flush()
            else:
                done = db.execute(
                    update(AssistantStateRow)
                    .where(AssistantStateRow.user_id == user_id, AssistantStateRow.revision == state.revision)
                    .values(revision=state.revision + 1, data=data)
                ).rowcount
                if not done:
                    raise Conflict("다른 요청이 정보를 변경했어요. 최신 상태에서 다시 시도해 주세요.")

        def save_state(self, user_id: str, state: UserState) -> None:
            try:
                with SessionLocal() as db:
                    self._write(db, user_id, state)
                    db.commit()
            except IntegrityError:
                raise Conflict("다른 요청이 정보를 변경했어요. 최신 상태에서 다시 시도해 주세요.") from None
            except SQLAlchemyError:
                raise StorageUnavailable("대화 상태를 저장할 수 없어요.") from None

        def create_document(self, user_id: str, record: DocumentRecord, original: bytes) -> None:
            state = self.get_state(user_id)
            if record.id in state.documents or len(state.documents) >= MAX_DOCUMENTS:
                raise Conflict("이미 존재하는 문서이거나 최대 보관 문서 수에 도달했어요.")
            state.documents[record.id] = record
            try:
                with SessionLocal() as db:  # 원본과 문서 정보를 한 트랜잭션으로 저장
                    db.add(AssistantOriginal(user_id=user_id, document_id=record.id, content=original))
                    self._write(db, user_id, state)
                    db.commit()
            except IntegrityError:
                raise Conflict("이미 존재하는 문서예요.") from None
            except SQLAlchemyError:
                raise StorageUnavailable("문서를 저장할 수 없어요.") from None

        def get_original(self, user_id: str, document_id: str) -> bytes:
            self.get_document(user_id, document_id)
            with SessionLocal() as db:
                row = db.get(AssistantOriginal, (user_id, document_id))
            if not row:
                raise StorageUnavailable("문서 원본을 읽을 수 없어요.")
            return row.content

        def delete_user(self, db, user_id: str) -> None:
            """회원 탈퇴: 호출한 쪽의 트랜잭션에서 기억·대화·문서를 함께 지운다."""
            db.execute(delete(AssistantOriginal).where(AssistantOriginal.user_id == user_id))
            db.execute(delete(AssistantStateRow).where(AssistantStateRow.user_id == user_id))

    return PgAssistantStore()


class MemoryAssistantStore(_DocumentMixin):
    """시연 계정용. 최근 max_users명만 서버 메모리에 두고, 재시작하면 사라진다.
    업로드 원본은 사용자당 1건, 전체 max_bytes까지만 두고 넘으면 오래된 사용자부터 지운다."""

    def __init__(self, max_users: int = 300, max_bytes: int = 20 * 1024 * 1024, max_documents: int = 1):
        self.max_users, self.max_bytes, self.max_documents = max_users, max_bytes, max_documents
        self.states: OrderedDict[str, UserState] = OrderedDict()
        self.originals: dict[tuple[str, str], bytes] = {}
        self.total = 0  # originals에 든 바이트 합계
        self.lock = Lock()

    def get_state(self, user_id: str) -> UserState:
        with self.lock:
            state = self.states.get(user_id)
            return state.model_copy(deep=True) if state else UserState()

    def _drop(self, user_id: str) -> None:
        self.states.pop(user_id, None)
        for key in [k for k in self.originals if k[0] == user_id]:
            self.total -= len(self.originals.pop(key))

    def _save_locked(self, user_id: str, state: UserState) -> None:
        current = self.states.get(user_id)
        if (current.revision if current else 0) != state.revision:
            raise Conflict("다른 요청이 정보를 변경했어요. 최신 상태에서 다시 시도해 주세요.")
        self.states[user_id] = state.model_copy(deep=True, update={"revision": state.revision + 1})
        self.states.move_to_end(user_id)
        while len(self.states) > self.max_users or (self.total > self.max_bytes and len(self.states) > 1):
            self._drop(next(iter(self.states)))

    def save_state(self, user_id: str, state: UserState) -> None:
        with self.lock:
            self._save_locked(user_id, state)

    def create_document(self, user_id: str, record: DocumentRecord, original: bytes) -> None:
        if len(original) > self.max_bytes:
            raise Conflict("시연 계정에서는 이 크기의 문서를 보관할 수 없어요.")
        with self.lock:  # 원본과 문서 정보를 같은 잠금 안에서 저장
            current = self.states.get(user_id)
            state = current.model_copy(deep=True) if current else UserState()
            if record.id in state.documents or len(state.documents) >= min(MAX_DOCUMENTS, self.max_documents):
                raise Conflict("시연 계정은 문서를 1건까지 보관해요. 로그인하면 더 올릴 수 있어요.")
            state.documents[record.id] = record
            self.originals[(user_id, record.id)] = original
            self.total += len(original)
            self._save_locked(user_id, state)

    def get_original(self, user_id: str, document_id: str) -> bytes:
        self.get_document(user_id, document_id)
        with self.lock:
            if (user_id, document_id) not in self.originals:
                raise StorageUnavailable("문서 원본을 읽을 수 없어요.")
            return self.originals[(user_id, document_id)]


class RoutingStore:
    """시연 사용자(demo:)는 메모리 저장소, 로그인 계정은 Postgres 저장소."""

    def __init__(self, accounts, demo: MemoryAssistantStore):
        self.accounts, self.demo = accounts, demo

    def _pick(self, user_id: str):
        return self.demo if user_id.startswith("demo:") else self.accounts

    def get_state(self, user_id: str) -> UserState:
        return self._pick(user_id).get_state(user_id)

    def save_state(self, user_id: str, state: UserState) -> None:
        self._pick(user_id).save_state(user_id, state)

    def create_document(self, user_id: str, record: DocumentRecord, original: bytes) -> None:
        self._pick(user_id).create_document(user_id, record, original)

    def get_document(self, user_id: str, document_id: str) -> DocumentRecord:
        return self._pick(user_id).get_document(user_id, document_id)

    def get_original(self, user_id: str, document_id: str) -> bytes:
        return self._pick(user_id).get_original(user_id, document_id)

    def save_draft(self, user_id: str, document_id: str, draft: Draft) -> None:
        self._pick(user_id).save_draft(user_id, document_id, draft)

    def clear_conversation(self, user_id: str, conversation_id: str) -> None:
        self._pick(user_id).clear_conversation(user_id, conversation_id)
