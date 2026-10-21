import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import shards
from app.idempotency import commit_or_replay, remember, replay, request_hash
from app.models import Task, UserDirectory
from app.relay import enqueue
from app.schemas import TaskResponse
from app.security import Principal

# Tests set this to stop an owner transfer after the destination commit.
crash_after_destination = False


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def upsert_directory(db: Session, user_id: uuid.UUID, email: str, name: str) -> None:
    now = datetime.now(timezone.utc)
    row = db.get(UserDirectory, user_id)
    if row is None:
        db.add(UserDirectory(user_id=user_id, email=email.lower(), name=name, synced_at=now))
        return
    row.email = email.lower()
    row.name = name
    row.synced_at = now


def upsert_everywhere(principal: Principal) -> None:
    for shard in shards:
        db = shard.Session()
        try:
            upsert_directory(db, principal.user_id, principal.email, principal.name)
            db.commit()
        finally:
            db.close()


def to_response(db: Session, task: Task) -> dict:
    assignee_email = None
    if task.assignee_id is not None:
        directory = db.get(UserDirectory, task.assignee_id)
        if directory is not None:
            assignee_email = directory.email
    body = TaskResponse(
        id=task.id,
        owner_id=task.owner_id,
        assignee_id=task.assignee_id,
        assignee_email=assignee_email,
        title=task.title,
        description=task.description,
        status=task.status,  # type: ignore[arg-type]
        version=task.version,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
    return json.loads(body.model_dump_json())


def open_task(task_id: uuid.UUID, user_id: uuid.UUID, *, owner_only: bool) -> tuple[Session, Task]:
    for shard in shards:
        db = shard.Session()
        filters = [Task.id == task_id, Task.moved_at.is_(None)]
        if owner_only:
            filters.append(Task.owner_id == user_id)
        else:
            filters.append(or_(Task.owner_id == user_id, Task.assignee_id == user_id))
        task = db.scalar(select(Task).where(*filters))
        if task is not None:
            return db, task
        db.close()
    raise HTTPException(status_code=404, detail="Task not found")


def bump(task: Task, version: int) -> None:
    if task.version != version:
        raise HTTPException(status_code=409, detail="Task was updated. Reload and try again.")
    task.version += 1
    task.updated_at = datetime.now(timezone.utc)


def list_for(user_id: uuid.UUID) -> list[dict]:
    found: list[dict] = []
    for shard in shards:
        db = shard.Session()
        try:
            tasks = db.scalars(
                select(Task)
                .where(
                    Task.moved_at.is_(None),
                    or_(Task.owner_id == user_id, Task.assignee_id == user_id),
                )
                .order_by(Task.created_at.desc())
            ).all()
            found.extend(to_response(db, task) for task in tasks)
        finally:
            db.close()
    found.sort(key=lambda item: item["created_at"], reverse=True)
    return found


def transfer_owner(
    principal: Principal,
    task_id: uuid.UUID,
    new_owner_email: str,
    version: int,
    idempotency_key: str | None,
) -> JSONResponse:
    """Move a task to another owner.

    The task id links the two commits. A retry after a crash between them finds
    the destination row and only marks the source row moved.
    """
    located = _open_owned_active(task_id, principal.user_id)
    if located is None:
        raise HTTPException(status_code=404, detail="Task not found")
    source, task, source_index = located
    try:
        if task.owner_id != principal.user_id:
            raise HTTPException(status_code=404, detail="Task not found")
        new_owner = source.scalar(select(UserDirectory).where(UserDirectory.email == new_owner_email.lower()))
        if new_owner is None:
            raise HTTPException(status_code=409, detail="Assignee is not in the task directory yet")
        from app.database import shard_index

        dest_index = shard_index(new_owner.user_id)
        if dest_index == source_index:
            return _transfer_same_shard(source, task, principal, new_owner, new_owner_email, version, idempotency_key)

        dest = shards[dest_index].Session()
        try:
            existing = dest.scalar(select(Task).where(Task.id == task_id, Task.moved_at.is_(None)))
            if existing is None:
                if task.version != version:
                    raise HTTPException(status_code=409, detail="Task was updated. Reload and try again.")
                upsert_directory(dest, new_owner.user_id, new_owner.email, new_owner.name)
                copy = Task(
                    id=task.id,
                    owner_id=new_owner.user_id,
                    assignee_id=task.assignee_id,
                    title=task.title,
                    description=task.description,
                    status=task.status,
                    version=task.version + 1,
                    created_at=task.created_at,
                    updated_at=datetime.now(timezone.utc),
                )
                dest.add(copy)
                dest.flush()
                _enqueue_transfer(dest, copy, principal, previous_owner_id=task.owner_id)
                dest.commit()
                response_body = to_response(dest, copy)
                if crash_after_destination:
                    raise RuntimeError("injected crash between shards")
            else:
                if existing.owner_id != new_owner.user_id:
                    raise HTTPException(status_code=409, detail="Task was updated. Reload and try again.")
                response_body = to_response(dest, existing)
            task.moved_at = datetime.now(timezone.utc)
            source.commit()
            return JSONResponse(status_code=200, content=response_body)
        finally:
            dest.close()
    finally:
        source.close()


def _transfer_same_shard(
    source: Session,
    task: Task,
    principal: Principal,
    new_owner: UserDirectory,
    new_owner_email: str,
    version: int,
    idempotency_key: str | None,
) -> JSONResponse:
    body_hash = request_hash({"new_owner_email": new_owner_email, "version": version})
    stored = replay(source, principal.user_id, idempotency_key, body_hash)
    if stored is not None:
        return stored
    previous_owner_id = task.owner_id
    bump(task, version)
    task.owner_id = new_owner.user_id
    _enqueue_transfer(source, task, principal, previous_owner_id=previous_owner_id)
    source.flush()
    response_body = to_response(source, task)
    remember(source, principal.user_id, idempotency_key, body_hash, 200, response_body)
    replayed = commit_or_replay(source, principal.user_id, idempotency_key, body_hash)
    if replayed is not None:
        return replayed
    return JSONResponse(status_code=200, content=response_body)


def _open_owned_active(task_id: uuid.UUID, owner_id: uuid.UUID) -> tuple[Session, Task, int] | None:
    for index, shard in enumerate(shards):
        db = shard.Session()
        task = db.scalar(
            select(Task).where(Task.id == task_id, Task.moved_at.is_(None), Task.owner_id == owner_id)
        )
        if task is not None:
            return db, task, index
        db.close()
    return None


def _enqueue_transfer(db: Session, task: Task, principal: Principal, previous_owner_id: uuid.UUID) -> None:
    enqueue(
        db,
        "TaskOwnerTransferred",
        {
            "task_id": str(task.id),
            "owner_id": str(task.owner_id),
            "previous_owner_id": str(previous_owner_id),
            "assignee_id": str(task.assignee_id) if task.assignee_id else None,
            "actor_id": str(principal.user_id),
            "title": task.title,
            "status": task.status,
        },
    )
