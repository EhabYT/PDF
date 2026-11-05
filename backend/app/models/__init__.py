from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, ForeignKey, Text, JSON, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def uid() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String(512))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_codes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_login: Mapped[datetime | None] = mapped_column(DateTime)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    user_agent: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class RateLimit(Base):
    __tablename__ = "rate_limits"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[datetime] = mapped_column(DateTime, default=now)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    original_filename: Mapped[str] = mapped_column(String(250))
    document_type: Mapped[str] = mapped_column(String(16), default="image")
    category: Mapped[str] = mapped_column(String(64), default="Other Documents")
    detected_type: Mapped[str] = mapped_column(String(100), default="")
    organization: Mapped[str] = mapped_column(String(120), default="")
    subject: Mapped[str] = mapped_column(String(120), default="")
    detected_date: Mapped[str] = mapped_column(String(32), default="")
    date_source: Mapped[str] = mapped_column(String(16), default="")
    description: Mapped[str] = mapped_column(String(500), default="")
    suggested_name: Mapped[str] = mapped_column(String(180), default="")
    approved_name: Mapped[str] = mapped_column(String(180), default="")
    naming_status: Mapped[str] = mapped_column(String(16), default="pending")
    name_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    pages: Mapped[list["Page"]] = relationship(cascade="all, delete-orphan", passive_deletes=True, order_by="Page.ordinal")
    sources: Mapped[list["SourceFile"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    jobs: Mapped[list["ProcessingJob"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    exports: Mapped[list["Export"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class SourceFile(Base):
    __tablename__ = "source_files"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(250))
    path: Mapped[str] = mapped_column(String(300), unique=True)
    checksum: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(BigInteger)
    mime: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(8))
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("document_id", "ordinal"), CheckConstraint("rotation IN (0,90,180,270)"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_files.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer)
    original_path: Mapped[str] = mapped_column(String(300))
    processed_path: Mapped[str | None] = mapped_column(String(300))
    thumbnail_path: Mapped[str | None] = mapped_column(String(300))
    ocr_path: Mapped[str | None] = mapped_column(String(300))
    checksum: Mapped[str] = mapped_column(String(64))
    processed_checksum: Mapped[str | None] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    rotation: Mapped[int] = mapped_column(Integer, default=0)
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    corners: Mapped[list | None] = mapped_column(JSON)
    detection: Mapped[dict] = mapped_column(JSON, default=dict)
    processing_status: Mapped[str] = mapped_column(String(16), default="uploaded", index=True)
    error_message: Mapped[str] = mapped_column(String(300), default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[SourceFile] = relationship()


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(16), default="process")
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    completed_pages: Mapped[int] = mapped_column(Integer, default=0)
    current_page: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(String(300), default="")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    settings_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Export(Base):
    __tablename__ = "exports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(String(300), unique=True)
    format: Mapped[str] = mapped_column(String(16))
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    checksum: Mapped[str] = mapped_column(String(64), default="")
    page_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class OwnerSetting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("owner_id", "setting_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    setting_key: Mapped[str] = mapped_column(String(64))
    setting_value: Mapped[dict] = mapped_column(JSON)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


Index("ix_jobs_claim", ProcessingJob.status, ProcessingJob.created_at)
