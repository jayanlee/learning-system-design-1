import uuid

import pytest
from sqlalchemy import func, select

from app.bus import count_dead_letters, make_visible, publish, receive, truncate_bus
from app.consumer import consume_once, handle_task_event
from app.database import SessionLocal
from app.models import AuditLog, Notification


@pytest.fixture(autouse=True)
def clean_bus() -> None:
    truncate_bus()


def _event(event_type: str, **extra: object) -> dict:
    owner = str(uuid.uuid4())
    assignee = str(uuid.uuid4())
    body = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "task_id": str(uuid.uuid4()),
        "owner_id": owner,
        "assignee_id": assignee,
        "actor_id": owner,
        "title": "Write spec",
        "status": "in_progress",
    }
    body.update(extra)
    return body


def test_duplicate_event_inserts_one_notification() -> None:
    event = _event("TaskAssigned")
    with SessionLocal() as db:
        handle_task_event(db, event)
    with SessionLocal() as db:
        handle_task_event(db, event)
        notes = db.scalar(select(func.count()).select_from(Notification))
        audits = db.scalar(select(func.count()).select_from(AuditLog))
    assert notes == 1
    assert audits == 1


def test_bus_redelivery_is_still_one_notification() -> None:
    event = _event("TaskStatusChanged")
    publish("task-events", event)
    publish("task-events", event)
    assert consume_once(SessionLocal) == 1
    assert consume_once(SessionLocal) == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Notification)) == 1


def test_message_moves_to_the_dead_letter_queue_after_five_receives() -> None:
    publish("task-events", _event("TaskCreated"))
    for _ in range(5):
        message = receive("task-events")
        assert message is not None
        make_visible(message["id"])
    assert receive("task-events") is None
    assert count_dead_letters("task-events") == 1
