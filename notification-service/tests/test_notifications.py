import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres@localhost:5432/sd_notify"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["CONSUMER_ENABLED"] = "false"
os.environ["BUS_DATABASE_URL"] = "postgresql+psycopg://postgres@localhost:5432/sd_bus"

import jwt
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Notification

client = TestClient(app)


def bearer(user_id: uuid.UUID) -> dict[str, str]:
    payload = {
        "sub": str(user_id),
        "email": "ada@example.com",
        "name": "Ada",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, "test-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_health_ready_and_empty_list() -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    user_id = uuid.uuid4()
    listed = client.get("/api/notifications", headers=bearer(user_id))
    assert listed.status_code == 200
    assert listed.json() == []


def test_mark_read_only_for_the_owner() -> None:
    owner = uuid.uuid4()
    other = uuid.uuid4()
    note_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            Notification(
                id=note_id,
                user_id=owner,
                task_id=None,
                type="TaskAssigned",
                payload={"title": "Write spec"},
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    hidden = client.post(f"/api/notifications/{note_id}/read", headers=bearer(other))
    assert hidden.status_code == 404
    marked = client.post(f"/api/notifications/{note_id}/read", headers=bearer(owner))
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None
    listed = client.get("/api/notifications", headers=bearer(owner))
    assert len(listed.json()) == 1
