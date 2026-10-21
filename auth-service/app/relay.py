import os
import random
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Outbox


def flag_enabled(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


def backoff_seconds(attempts: int) -> float:
    cap = min(60.0, 0.5 * (2**attempts))
    return cap * random.uniform(0.5, 1.0)


def enqueue(db: Session, event_type: str, fields: dict) -> uuid.UUID:
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    payload = {"event_id": str(event_id), "event_type": event_type, **fields}
    db.add(
        Outbox(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            created_at=now,
            attempts=0,
            next_attempt_at=now,
        )
    )
    return event_id


def relay_once(
    session_factory: sessionmaker[Session],
    publisher: object,
    worker_id: str,
    queue_for: Callable[[str], str],
    lease_seconds: int = 30,
) -> int:
    db = session_factory()
    try:
        now = datetime.now(timezone.utc)
        rows = list(
            db.scalars(
                select(Outbox)
                .where(
                    Outbox.published_at.is_(None),
                    Outbox.next_attempt_at <= now,
                    or_(Outbox.locked_until.is_(None), Outbox.locked_until < now),
                )
                .order_by(Outbox.created_at)
                .limit(20)
                .with_for_update(skip_locked=True)
            )
        )
        until = now + timedelta(seconds=lease_seconds)
        ids = []
        for row in rows:
            row.locked_by = worker_id
            row.locked_until = until
            ids.append(row.id)
        db.commit()
    finally:
        db.close()

    published = 0
    for row_id in ids:
        db = session_factory()
        try:
            row = db.get(Outbox, row_id)
            if row is None or row.published_at is not None or row.locked_by != worker_id:
                continue
            try:
                publisher.publish(queue_for(row.event_type), row.payload)  # type: ignore[attr-defined]
            except Exception:
                row.attempts += 1
                row.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds(row.attempts))
                row.locked_by = None
                row.locked_until = None
                db.commit()
                continue
            row.published_at = datetime.now(timezone.utc)
            row.locked_by = None
            row.locked_until = None
            db.commit()
            published += 1
        finally:
            db.close()
    return published


_stop = threading.Event()
_thread: threading.Thread | None = None


def start_relay(loop: Callable[[], None]) -> None:
    global _thread
    if not flag_enabled("RELAY_ENABLED"):
        return
    _stop.clear()

    def run() -> None:
        while not _stop.is_set():
            try:
                loop()
            except Exception:
                pass
            _stop.wait(1)

    _thread = threading.Thread(target=run, name="outbox-relay", daemon=True)
    _thread.start()


def stop_relay() -> None:
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)
