import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.bus import LocalPublisher, publish, truncate_bus
from app.consumer import consume_once
from app.database import SessionLocal, shards
from app.main import app
from app.models import Outbox, UserDirectory
from app.relay import relay_once

client = TestClient(app)


def auth(user_id: uuid.UUID, email: str, name: str) -> dict[str, str]:
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, "test-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def setup_module() -> None:
    truncate_bus()


def relay_all() -> int:
    total = 0
    for shard in shards:
        total += relay_once(shard.Session, LocalPublisher(), "task-relay", lambda _event_type: "task-events")
    return total


def outbox_rows() -> list[tuple[str, object]]:
    rows: list[tuple[str, object]] = []
    for shard in shards:
        db = shard.Session()
        try:
            for row in db.scalars(select(Outbox)).all():
                rows.append((row.event_type, row.published_at))
        finally:
            db.close()
    return rows


def test_create_publishes_one_task_event() -> None:
    truncate_bus()
    owner = uuid.uuid4()
    created = client.post(
        "/api/tasks",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"title": "Write spec"},
    )
    assert created.status_code == 201
    rows = outbox_rows()
    assert len(rows) == 1
    assert rows[0][0] == "TaskCreated"
    assert rows[0][1] is None
    assert relay_all() == 1
    assert relay_all() == 0


def test_user_event_is_applied_once_and_then_assign_works() -> None:
    truncate_bus()
    owner = uuid.uuid4()
    assignee = uuid.uuid4()
    created = client.post(
        "/api/tasks",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"title": "Write spec"},
    )
    task_id = created.json()["id"]
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "event_type": "UserRegistered",
        "user_id": str(assignee),
        "email": "bea@example.com",
        "name": "Bea",
    }
    publish("user-events", event)
    publish("user-events", event)
    assert consume_once(SessionLocal) == 1
    assert consume_once(SessionLocal) == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(UserDirectory).where(UserDirectory.email == "bea@example.com")) == 1
    assigned = client.post(
        f"/api/tasks/{task_id}/assign",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"assignee_email": "bea@example.com", "version": 1},
    )
    assert assigned.status_code == 200
    assert assigned.json()["assignee_email"] == "bea@example.com"
