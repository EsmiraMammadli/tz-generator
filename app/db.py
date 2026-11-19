"""SQLAlchemy modelləri. Sessiya state-i JSON sütununda saxlanır (sadə və atomik)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from . import config


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | confirmed
    language: Mapped[str] = mapped_column(String(8), default="az")
    site_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    state: Mapped[dict] = mapped_column(JSON, default=dict)


class MessageRow(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | ai
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # chips, show_tree
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TZVersionRow(Base):
    __tablename__ = "tz_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    json_snapshot: Mapped[dict] = mapped_column(JSON)
    file_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedbackRow(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)  # sessiya silinsə də anonim qalır
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


_engine = None
_Session = None


def normalize_url(url: str) -> str:
    """Supabase/Neon/Render `postgres://...` və ya `postgresql://...` verir: SQLAlchemy üçün psycopg (v3) sürücüsünə çevrilir."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {
        "pool_pre_ping": True,   # Neon/Supabase boş bağlantını bağlayır: ölü bağlantı avtomatik dəyişir
        "pool_recycle": 300,
        "pool_size": 5,          # pulsuz planlarda bağlantı limiti kiçikdir
        "max_overflow": 5,
        # Supabase pooler (pgbouncer, transaction rejimi) hazırlanmış sorğuları dəstəkləmir
        "connect_args": {"prepare_threshold": None},
    }


def init_db(url: str | None = None) -> None:
    global _engine, _Session
    url = normalize_url(url or config.DATABASE_URL)
    if url.startswith("sqlite:///"):
        from pathlib import Path
        Path(url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(url, **_engine_kwargs(url))
    if url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(_engine, "connect")
        def _fk(conn, _):  # SQLite-də ON DELETE CASCADE üçün
            conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(_engine, expire_on_commit=False)


def backend() -> str:
    """'sqlite' | 'postgresql' (admin və log üçün; şifrə heç vaxt göstərilmir)."""
    return _engine.dialect.name if _engine is not None else "?"


def get_db():
    with _Session() as s:
        yield s


def purge_stale(db, days: int | None = None) -> int:
    """Tamamlanmamış sessiyalar `days` gündən sonra silinir."""
    cutoff = utcnow() - timedelta(days=days or config.RETENTION_DAYS)
    ids = db.scalars(select(SessionRow.id).where(SessionRow.status == "active", SessionRow.updated_at < cutoff)).all()
    for sid in ids:
        db.execute(delete(MessageRow).where(MessageRow.session_id == sid))
        db.execute(delete(TZVersionRow).where(TZVersionRow.session_id == sid))
        db.execute(delete(SessionRow).where(SessionRow.id == sid))
    db.commit()
    return len(ids)
