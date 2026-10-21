import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserDirectory(Base):
    """Local copy of account fields. Auth is the source; this row can lag."""

    __tablename__ = "user_directory"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_owner_id", "owner_id"),
        Index("ix_tasks_assignee_id", "assignee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    moved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)
    event_type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
