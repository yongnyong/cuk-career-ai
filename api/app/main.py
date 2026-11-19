"""CUK Career AI API — 계정·세션·사용자 데이터.

원칙
- 비밀번호는 argon2 해시로만 저장한다.
- 세션 토큰은 HttpOnly 쿠키로만 전달하고, DB에는 토큰의 SHA-256만 저장한다.
- 이름·연락처·학번 전체는 받지 않는다(아이디는 가명).
"""
import hashlib
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import JSON, BigInteger, ForeignKey, String, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# 기본값: api/dev.db (실행 위치와 무관하게 같은 파일)
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{(Path(__file__).resolve().parent.parent / 'dev.db').as_posix()}"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"  # 운영(HTTPS)에서는 1
COOKIE = "cuk_session"
SESSION_TTL = 14 * 24 * 3600
MAX_STATE_BYTES = 200_000
ID_RE = re.compile(r"^[a-z0-9_]{4,16}$")
LOGIN_FAIL = "아이디 또는 비밀번호가 맞지 않아요."
# 관리자 아이디(쉼표 구분). 관리자는 서버 현황을 볼 수 있다
ADMIN_IDS = {x.strip() for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
hasher = PasswordHasher()
# 없는 아이디로 로그인해도 같은 시간이 걸리도록 검증에 쓰는 더미 해시
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(16))


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger)


class SessionRow(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[int] = mapped_column(BigInteger)


class Posting(Base):
    """수집한 공개 공고. data는 웹의 Opportunity 구조(web/src/lib/types.ts)와 같다."""

    __tablename__ = "postings"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    raw_hash: Mapped[str] = mapped_column(String(64))
    # 기회가 아닌 공지(결과 발표 등)나 마감일을 찾지 못한 공지는 data가 비어 있다
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    checked_at: Mapped[int] = mapped_column(BigInteger)


class Setting(Base):
    """서비스 전체 설정. key="catalog": 관리자가 고친 직무·스킬(웹의 기본 사전 위에 덮어쓴다)."""

    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)


Base.metadata.create_all(engine)
app = FastAPI(title="CUK Career AI API")


def get_db():
    with SessionLocal() as db:
        yield db


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# 로그인 실패 제한: 아이디별 5분에 5회 (단일 프로세스 기준, 재시작 시 초기화)
_failures: dict[str, list[float]] = {}
FAIL_WINDOW, FAIL_LIMIT = 300, 5


def too_many_failures(user_id: str) -> bool:
    recent = [t for t in _failures.get(user_id, []) if time.time() - t < FAIL_WINDOW]
    _failures[user_id] = recent
    return len(recent) >= FAIL_LIMIT


def start_session(db: Session, response: Response, user_id: str) -> None:
    token = secrets.token_urlsafe(32)
    db.add(SessionRow(token_hash=token_hash(token), user_id=user_id, expires_at=int(time.time()) + SESSION_TTL))
    db.commit()
    response.set_cookie(
        COOKIE, token, max_age=SESSION_TTL, httponly=True, samesite="lax", secure=COOKIE_SECURE, path="/"
    )


def current_user(cuk_session: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    if cuk_session:
        row = db.get(SessionRow, token_hash(cuk_session))
        if row and row.expires_at > time.time():
            user = db.get(User, row.user_id)
            if user:
                return user
    raise HTTPException(401, "로그인이 필요해요.")


class Credentials(BaseModel):
    id: str = Field(max_length=16)
    password: str = Field(max_length=128)


class StateBody(BaseModel):
    state: dict[str, Any]


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/opportunities")
def opportunities(db: Session = Depends(get_db)):
    rows = db.scalars(select(Posting).where(Posting.data.is_not(None))).all()
    return [r.data for r in rows if r.data]


@app.post("/api/auth/signup")
def signup(body: Credentials, response: Response, db: Session = Depends(get_db)):
    if not ID_RE.match(body.id):
        raise HTTPException(422, "아이디는 영문 소문자·숫자 4~16자로 입력해 주세요.")
    if len(body.password) < 6:
        raise HTTPException(422, "비밀번호는 6자 이상으로 입력해 주세요.")
    if db.get(User, body.id):
        raise HTTPException(409, "이미 사용 중인 아이디예요.")
    db.add(User(id=body.id, password_hash=hasher.hash(body.password), state=None, created_at=int(time.time())))
    db.commit()
    start_session(db, response, body.id)
    return {"id": body.id, "state": None, "admin": body.id in ADMIN_IDS}


@app.post("/api/auth/login")
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    if too_many_failures(body.id):
        raise HTTPException(429, "로그인 시도가 너무 많아요. 5분 뒤에 다시 시도해 주세요.")
    user = db.get(User, body.id)
    try:
        hasher.verify(user.password_hash if user else DUMMY_HASH, body.password)
        ok = user is not None
    except (VerificationError, InvalidHashError):
        ok = False
    if not ok:
        _failures.setdefault(body.id, []).append(time.time())
        raise HTTPException(401, LOGIN_FAIL)
    _failures.pop(body.id, None)
    start_session(db, response, user.id)
    return {"id": user.id, "state": user.state, "admin": user.id in ADMIN_IDS}


@app.post("/api/auth/logout")
def logout(response: Response, cuk_session: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if cuk_session:
        db.execute(delete(SessionRow).where(SessionRow.token_hash == token_hash(cuk_session)))
        db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "state": user.state, "admin": user.id in ADMIN_IDS}


class CatalogBody(BaseModel):
    skills: dict[str, dict[str, Any]] = Field(default_factory=dict, max_length=500)
    jobs: dict[str, dict[str, Any]] = Field(default_factory=dict, max_length=300)


@app.get("/api/catalog")
def catalog(db: Session = Depends(get_db)):
    row = db.get(Setting, "catalog")
    return row.value if row else {"skills": {}, "jobs": {}}


@app.put("/api/admin/catalog")
def save_catalog(body: CatalogBody, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.id not in ADMIN_IDS:
        raise HTTPException(403, "관리자만 고칠 수 있어요.")
    value = body.model_dump()
    if len(json.dumps(value, ensure_ascii=False).encode()) > 300_000:
        raise HTTPException(413, "저장할 내용이 너무 커요.")
    db.merge(Setting(key="catalog", value=value))
    db.commit()
    return {"ok": True}


@app.get("/api/admin/overview")
def admin_overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """관리자용 현황. 개수만 돌려주고 계정 아이디·내 데이터 같은 개인 단위 정보는 넣지 않는다."""
    if user.id not in ADMIN_IDS:
        raise HTTPException(403, "관리자만 볼 수 있어요.")
    rows = db.scalars(select(Posting)).all()
    data = [r.data for r in rows if r.data]
    now = datetime.now(timezone.utc)
    by_source: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for o in data:
        by_source[o["id"].split("-")[0]] = by_source.get(o["id"].split("-")[0], 0) + 1
        by_type[o["type"]] = by_type.get(o["type"], 0) + 1
    last = max((r.checked_at for r in rows), default=None)
    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "postings": {
            "total": len(data),
            "open": sum(datetime.fromisoformat(o["versions"][-1]["deadline"]) > now for o in data),
            "pendingReview": sum(not o.get("reviewed") for o in data),
            "bySource": by_source,
            "byType": by_type,
        },
        "lastCheckedAt": datetime.fromtimestamp(last, timezone.utc).isoformat() if last else None,
    }


@app.put("/api/me/state")
def save_state(body: StateBody, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if len(json.dumps(body.state, ensure_ascii=False).encode()) > MAX_STATE_BYTES:
        raise HTTPException(413, "저장할 데이터가 너무 커요.")
    user.state = body.state
    db.merge(user)
    db.commit()
    return {"ok": True}


@app.delete("/api/me")
def delete_me(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(SessionRow).where(SessionRow.user_id == user.id))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


from .chat import make_router  # noqa: E402

app.include_router(make_router(get_db, Posting))

from .process import make_router as make_process_router  # noqa: E402

app.include_router(make_process_router(get_db, current_user, lambda: ADMIN_IDS, Posting, Setting))


# 만료된 세션 정리는 로그인 시점에 가볍게 수행
@app.middleware("http")
async def purge_expired(request, call_next):
    if request.url.path == "/api/auth/login":
        with SessionLocal() as db:
            db.execute(delete(SessionRow).where(SessionRow.expires_at < int(time.time())))
            db.commit()
    return await call_next(request)

