import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import shard_index, shards
from app.main import app
from app.models import Task
import app.access as access

client = TestClient(app)
quiet = TestClient(app, raise_server_exceptions=False)


def auth(user_id: uuid.UUID, email: str, name: str) -> dict[str, str]:
    from datetime import datetime, timedelta, timezone

    import jwt

    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, "test-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def pair_on_different_shards() -> tuple[uuid.UUID, uuid.UUID]:
    while True:
        first, second = uuid.uuid4(), uuid.uuid4()
        if shard_index(first) != shard_index(second):
            return first, second


def active_copies(task_id: str) -> int:
    total = 0
    for shard in shards:
        db = shard.Session()
        try:
            total += int(
                db.scalar(
                    select(func.count()).select_from(Task).where(Task.id == uuid.UUID(task_id), Task.moved_at.is_(None))
                )
                or 0
            )
        finally:
            db.close()
    return total


def test_assignee_list_reads_both_shards() -> None:
    owner, assignee = pair_on_different_shards()
    owned = client.post("/api/tasks", headers=auth(owner, "ada@example.com", "Ada"), json={"title": "On Ada's shard"})
    assigned_home = client.post(
        "/api/tasks",
        headers=auth(assignee, "bea@example.com", "Bea"),
        json={"title": "On Bea's shard"},
    )
    assert owned.status_code == 201
    assert assigned_home.status_code == 201
    assigned = client.post(
        f"/api/tasks/{owned.json()['id']}/assign",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"assignee_email": "bea@example.com", "version": 1},
    )
    assert assigned.status_code == 200
    listed = client.get("/api/tasks", headers=auth(assignee, "bea@example.com", "Bea"))
    titles = {item["title"] for item in listed.json()}
    assert titles == {"On Ada's shard", "On Bea's shard"}


def test_transfer_crash_then_retry_leaves_one_visible_task() -> None:
    owner, new_owner = pair_on_different_shards()
    created = client.post("/api/tasks", headers=auth(owner, "ada@example.com", "Ada"), json={"title": "Move me"})
    client.post("/api/tasks", headers=auth(new_owner, "bea@example.com", "Bea"), json={"title": "Bea's task"})
    task_id = created.json()["id"]
    access.crash_after_destination = True
    try:
        interrupted = quiet.post(
            f"/api/tasks/{task_id}/transfer",
            headers=auth(owner, "ada@example.com", "Ada"),
            json={"new_owner_email": "bea@example.com", "version": 1},
        )
        assert interrupted.status_code == 500
        assert active_copies(task_id) == 2
        still_owner = client.get("/api/tasks", headers=auth(owner, "ada@example.com", "Ada"))
        still_new = client.get("/api/tasks", headers=auth(new_owner, "bea@example.com", "Bea"))
        assert any(item["id"] == task_id for item in still_owner.json())
        assert any(item["id"] == task_id for item in still_new.json())
    finally:
        access.crash_after_destination = False

    finished = client.post(
        f"/api/tasks/{task_id}/transfer",
        headers=auth(owner, "ada@example.com", "Ada"),
        json={"new_owner_email": "bea@example.com", "version": 1},
    )
    assert finished.status_code == 200
    assert finished.json()["owner_id"] == str(new_owner)
    assert active_copies(task_id) == 1
    old_list = client.get("/api/tasks", headers=auth(owner, "ada@example.com", "Ada"))
    new_list = client.get("/api/tasks", headers=auth(new_owner, "bea@example.com", "Bea"))
    assert all(item["id"] != task_id for item in old_list.json())
    assert any(item["id"] == task_id for item in new_list.json())
