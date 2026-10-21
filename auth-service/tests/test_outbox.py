from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.bus import LocalPublisher, count_messages, truncate_bus
from app.database import SessionLocal
from app.main import app
from app.models import Outbox, User
from app.relay import backoff_seconds, enqueue, relay_once
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_bus() -> None:
    truncate_bus()


def test_backoff_grows_and_stays_inside_the_cap() -> None:
    low = backoff_seconds(1)
    assert 0.5 <= low <= 1
    high = backoff_seconds(20)
    assert 30 <= high <= 60


def test_outbox_rolls_back_with_the_user() -> None:
    db = SessionLocal()
    user = User(
        name="Ada",
        email="rollback@example.com",
        password_hash="x",
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    enqueue(db, "UserRegistered", {"user_id": str(user.id), "email": user.email, "name": user.name})
    db.rollback()
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert db.scalar(select(func.count()).select_from(Outbox)) == 0
    db.close()


def test_failed_publish_is_retried_once() -> None:
    registered = client.post(
        "/api/auth/register",
        json={"name": "Ada", "email": "ada@example.com", "password": "password1"},
    )
    assert registered.status_code == 201

    class Down:
        def publish(self, queue_name: str, body: dict) -> None:
            raise RuntimeError("bus down")

    assert relay_once(SessionLocal, Down(), "worker-a", lambda _event_type: "user-events") == 0
    with SessionLocal() as db:
        row = db.scalars(select(Outbox)).one()
        assert row.published_at is None
        assert row.attempts == 1
        assert row.locked_by is None
        assert row.locked_until is None
        assert row.next_attempt_at > datetime.now(timezone.utc)

    assert relay_once(SessionLocal, LocalPublisher(), "worker-b", lambda _event_type: "user-events") == 0

    with SessionLocal() as db:
        row = db.scalars(select(Outbox)).one()
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    assert relay_once(SessionLocal, LocalPublisher(), "worker-b", lambda _event_type: "user-events") == 1
    assert count_messages("user-events") == 1
    assert relay_once(SessionLocal, LocalPublisher(), "worker-b", lambda _event_type: "user-events") == 0


def test_lease_hides_a_row_from_a_second_worker() -> None:
    client.post(
        "/api/auth/register",
        json={"name": "Ada", "email": "ada@example.com", "password": "password1"},
    )
    with SessionLocal() as db:
        row = db.scalars(select(Outbox)).one()
        row.locked_by = "worker-a"
        row.locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)
        db.commit()

    assert relay_once(SessionLocal, LocalPublisher(), "worker-b", lambda _event_type: "user-events") == 0
    assert count_messages("user-events") == 0

    with SessionLocal() as db:
        row = db.scalars(select(Outbox)).one()
        row.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    assert relay_once(SessionLocal, LocalPublisher(), "worker-b", lambda _event_type: "user-events") == 1
    assert count_messages("user-events") == 1
