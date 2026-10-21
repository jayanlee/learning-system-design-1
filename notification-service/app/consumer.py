import signal
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.bus import ack, take_one
from app.models import AuditLog, Notification, ProcessedEvent

_stop = threading.Event()
_thread: threading.Thread | None = None


def _recipient(event: dict) -> uuid.UUID | None:
    if event.get("event_type") == "TaskAssigned" and event.get("assignee_id"):
        return uuid.UUID(event["assignee_id"])
    if event.get("event_type") == "TaskOwnerTransferred" and event.get("owner_id"):
        return uuid.UUID(event["owner_id"])
    if event.get("event_type") != "TaskStatusChanged":
        return None
    actor = event.get("actor_id")
    owner = event.get("owner_id")
    assignee = event.get("assignee_id")
    if actor == owner and assignee and assignee != actor:
        return uuid.UUID(assignee)
    if actor == assignee and owner and owner != actor:
        return uuid.UUID(owner)
    return None


def handle_task_event(db: Session, event: dict) -> None:
    event_id = uuid.UUID(event["event_id"])
    if db.get(ProcessedEvent, event_id) is not None:
        return
    now = datetime.now(timezone.utc)
    task_raw = event.get("task_id")
    actor_raw = event.get("actor_id")
    db.add(
        AuditLog(
            event_id=event_id,
            action=str(event.get("event_type")),
            actor_id=uuid.UUID(actor_raw) if actor_raw else None,
            task_id=uuid.UUID(task_raw) if task_raw else None,
            payload=event,
            created_at=now,
        )
    )
    recipient = _recipient(event)
    if recipient is not None:
        db.add(
            Notification(
                user_id=recipient,
                task_id=uuid.UUID(task_raw) if task_raw else None,
                type=str(event.get("event_type")),
                payload={"title": event.get("title"), "status": event.get("status")},
                created_at=now,
            )
        )
    db.add(ProcessedEvent(event_id=event_id, processed_at=now))
    db.commit()


def consume_once(session_factory: sessionmaker[Session]) -> int:
    message = take_one("task-events")
    if message is None:
        return 0
    db = session_factory()
    try:
        handle_task_event(db, message["body"])
    except Exception:
        db.rollback()
        return 0
    finally:
        db.close()
    ack(message)
    return 1


def start_consumer() -> None:
    global _thread
    from app.database import SessionLocal
    from app.relay_flags import flag_enabled

    if not flag_enabled("CONSUMER_ENABLED"):
        return
    _stop.clear()

    def run() -> None:
        while not _stop.is_set():
            try:
                consume_once(SessionLocal)
            except Exception:
                pass
            _stop.wait(1)

    _thread = threading.Thread(target=run, name="task-consumer", daemon=True)
    _thread.start()


def stop_consumer() -> None:
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)


def main() -> None:
    from app.database import SessionLocal

    def handle_signal(_signum: int, _frame: object) -> None:
        _stop.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    while not _stop.is_set():
        try:
            consume_once(SessionLocal)
        except Exception:
            pass
        _stop.wait(0.5)


if __name__ == "__main__":
    main()
