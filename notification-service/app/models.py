import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)
    action: Mapped[str] = mapped_column(String(50))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
