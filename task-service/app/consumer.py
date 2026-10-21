import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.bus import ack, take_one
from app.models import ProcessedEvent, UserDirectory

_stop = threading.Event()
_thread: threading.Thread | None = None


def handle_user_event(db: Session, event: dict) -> None:
    event_id = uuid.UUID(event["event_id"])
    if db.get(ProcessedEvent, event_id) is not None:
        return
    if event.get("event_type") == "UserRegistered":
        now = datetime.now(timezone.utc)
        user_id = uuid.UUID(event["user_id"])
        row = db.get(UserDirectory, user_id)
        email = str(event["email"]).lower()
        name = str(event["name"])
        if row is None:
            db.add(UserDirectory(user_id=user_id, email=email, name=name, synced_at=now))
        else:
            row.email = email
            row.name = name
            row.synced_at = now
    db.add(ProcessedEvent(event_id=event_id, processed_at=datetime.now(timezone.utc)))
    db.commit()


def consume_once(_session_factory: sessionmaker[Session] | None = None) -> int:
    message = take_one("user-events")
    if message is None:
        return 0
    from app.database import shards

    for shard in shards:
        db = shard.Session()
        try:
            handle_user_event(db, message["body"])
        except Exception:
            db.rollback()
            return 0
        finally:
            db.close()
    ack(message)
    return 1


def start_consumer() -> None:
    global _thread
    from app.relay import flag_enabled

    if not flag_enabled("CONSUMER_ENABLED"):
        return
    from app.database import SessionLocal

    _stop.clear()

    def run() -> None:
        while not _stop.is_set():
            try:
                consume_once(SessionLocal)
            except Exception:
                pass
            _stop.wait(1)

    _thread = threading.Thread(target=run, name="user-consumer", daemon=True)
    _thread.start()


def stop_consumer() -> None:
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)


def main() -> None:
    import signal

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
