import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres@localhost:5432/sd_task"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["RATE_LIMIT_PER_MINUTE"] = "5"
os.environ["RELAY_ENABLED"] = "false"
os.environ["CONSUMER_ENABLED"] = "false"
os.environ["BUS_DATABASE_URL"] = "postgresql+psycopg://postgres@localhost:5432/sd_bus"

import jwt
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def token(user_id: uuid.UUID, email: str, name: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")


def auth(user_id: uuid.UUID, email: str, name: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(user_id, email, name)}"}


def test_health_and_ready() -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_create_list_and_hide_other_users() -> None:
    owner = uuid.uuid4()
    other = uuid.uuid4()
    created = client.post(
        "/api/tasks",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"title": "Write spec", "description": "short"},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["version"] == 1
    listed = client.get("/api/tasks", headers=auth(owner, "ada@example.com", "Ada"))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    missing = client.patch(
        f"/api/tasks/{task_id}",
        headers=auth(other, "bea@example.com", "Bea"),
        json={"version": 1, "status": "done"},
    )
    assert missing.status_code == 404


def test_assign_waits_for_directory_then_assignee_can_update() -> None:
    owner = uuid.uuid4()
    assignee = uuid.uuid4()
    created = client.post(
        "/api/tasks",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"title": "Write spec"},
    )
    task_id = created.json()["id"]
    early = client.post(
        f"/api/tasks/{task_id}/assign",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"assignee_email": "bea@example.com", "version": 1},
    )
    assert early.status_code == 409

    client.post(
        "/api/tasks",
        headers=auth(assignee, "bea@example.com", "Bea"),
        json={"title": "Bea's own task"},
    )
    assigned = client.post(
        f"/api/tasks/{task_id}/assign",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"assignee_email": "bea@example.com", "version": 1},
    )
    assert assigned.status_code == 200
    assert assigned.json()["assignee_email"] == "bea@example.com"

    updated = client.patch(
        f"/api/tasks/{task_id}",
        headers=auth(assignee, "bea@example.com", "Bea"),
        json={"version": assigned.json()["version"], "status": "in_progress"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"

    forbidden = client.delete(
        f"/api/tasks/{task_id}",
        headers=auth(assignee, "bea@example.com", "Bea"),
    )
    assert forbidden.status_code == 403
    deleted = client.delete(f"/api/tasks/{task_id}", headers=auth(owner, "ada@example.com", "Ada"))
    assert deleted.status_code == 204


def test_stale_version_conflicts() -> None:
    owner = uuid.uuid4()
    created = client.post(
        "/api/tasks",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"title": "Write spec"},
    )
    task_id = created.json()["id"]
    stale = client.patch(
        f"/api/tasks/{task_id}",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"version": 2, "title": "Changed"},
    )
    assert stale.status_code == 409


def test_idempotency_key_replays_and_rejects_a_different_body() -> None:
    owner = uuid.uuid4()
    headers = auth(owner, "ada@example.com", "Ada")
    headers["Idempotency-Key"] = "create-1"
    first = client.post("/api/tasks", headers=headers, json={"title": "Write spec"})
    second = client.post("/api/tasks", headers=headers, json={"title": "Write spec"})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    listed = client.get("/api/tasks", headers=auth(owner, "ada@example.com", "Ada"))
    assert len(listed.json()) == 1
    different = client.post("/api/tasks", headers=headers, json={"title": "Other"})
    assert different.status_code == 409


def test_rate_limit() -> None:
    owner = uuid.uuid4()
    headers = auth(owner, "ada@example.com", "Ada")
    for index in range(5):
        response = client.post("/api/tasks", headers=headers, json={"title": f"Task {index}"})
        assert response.status_code == 201
    blocked = client.post("/api/tasks", headers=headers, json={"title": "Too many"})
    assert blocked.status_code == 429
