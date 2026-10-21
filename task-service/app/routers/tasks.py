import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from app.access import (
    bump,
    clean,
    list_for,
    open_task,
    to_response,
    transfer_owner,
    upsert_directory,
    upsert_everywhere,
)
from app.database import session_for
from app.idempotency import commit_or_replay, remember, replay, request_hash
from app.models import Task, UserDirectory
from app.rate_limit import enforce
from app.relay import enqueue
from app.schemas import AssignRequest, TaskCreate, TaskResponse, TaskUpdate, TransferRequest
from app.security import bearer_scheme, get_principal

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> list[dict]:
    principal = get_principal(credentials)
    return list_for(principal.user_id)


@router.post("", status_code=201)
def create_task(
    body: TaskCreate,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    principal = get_principal(credentials)
    enforce(principal.user_id)
    upsert_everywhere(principal)
    payload = body.model_dump()
    body_hash = request_hash(payload)
    db = session_for(principal.user_id)
    try:
        stored = replay(db, principal.user_id, idempotency_key, body_hash)
        if stored is not None:
            return stored
        title = clean(body.title)
        if title is None:
            raise HTTPException(status_code=422, detail="Title is required")
        now = datetime.now(timezone.utc)
        upsert_directory(db, principal.user_id, principal.email, principal.name)
        task = Task(
            owner_id=principal.user_id,
            title=title,
            description=clean(body.description),
            status=body.status,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(task)
        db.flush()
        enqueue(
            db,
            "TaskCreated",
            {
                "task_id": str(task.id),
                "owner_id": str(task.owner_id),
                "actor_id": str(principal.user_id),
                "title": task.title,
                "status": task.status,
            },
        )
        response_body = to_response(db, task)
        remember(db, principal.user_id, idempotency_key, body_hash, 201, response_body)
        replayed = commit_or_replay(db, principal.user_id, idempotency_key, body_hash)
        if replayed is not None:
            return replayed
        return JSONResponse(status_code=201, content=response_body)
    finally:
        db.close()


@router.patch("/{task_id}")
def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    principal = get_principal(credentials)
    enforce(principal.user_id)
    db, task = open_task(task_id, principal.user_id, owner_only=False)
    try:
        previous_status = task.status
        bump(task, body.version)
        changes = body.model_dump(exclude_unset=True)
        if "title" in changes:
            title = clean(changes["title"])
            if title is None:
                raise HTTPException(status_code=422, detail="Title is required")
            task.title = title
        if "description" in changes:
            task.description = clean(changes["description"])
        if changes.get("status") is not None and changes["status"] != previous_status:
            task.status = changes["status"]
            enqueue(
                db,
                "TaskStatusChanged",
                {
                    "task_id": str(task.id),
                    "owner_id": str(task.owner_id),
                    "assignee_id": str(task.assignee_id) if task.assignee_id else None,
                    "actor_id": str(principal.user_id),
                    "title": task.title,
                    "status": task.status,
                },
            )
        db.commit()
        db.refresh(task)
        return to_response(db, task)
    finally:
        db.close()


@router.post("/{task_id}/assign")
def assign_task(
    task_id: uuid.UUID,
    body: AssignRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    principal = get_principal(credentials)
    enforce(principal.user_id)
    payload = body.model_dump()
    body_hash = request_hash(payload)
    db, task = open_task(task_id, principal.user_id, owner_only=True)
    try:
        stored = replay(db, principal.user_id, idempotency_key, body_hash)
        if stored is not None:
            return stored
        bump(task, body.version)
        assignee = db.scalar(select(UserDirectory).where(UserDirectory.email == body.assignee_email.lower()))
        if assignee is None:
            raise HTTPException(status_code=409, detail="Assignee is not in the task directory yet")
        task.assignee_id = assignee.user_id
        enqueue(
            db,
            "TaskAssigned",
            {
                "task_id": str(task.id),
                "owner_id": str(task.owner_id),
                "assignee_id": str(assignee.user_id),
                "actor_id": str(principal.user_id),
                "title": task.title,
                "status": task.status,
            },
        )
        db.flush()
        response_body = to_response(db, task)
        remember(db, principal.user_id, idempotency_key, body_hash, 200, response_body)
        replayed = commit_or_replay(db, principal.user_id, idempotency_key, body_hash)
        if replayed is not None:
            return replayed
        return JSONResponse(status_code=200, content=response_body)
    finally:
        db.close()


@router.post("/{task_id}/transfer")
def transfer_task(
    task_id: uuid.UUID,
    body: TransferRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    principal = get_principal(credentials)
    enforce(principal.user_id)
    return transfer_owner(principal, task_id, body.new_owner_email, body.version, idempotency_key)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: uuid.UUID,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Response:
    principal = get_principal(credentials)
    enforce(principal.user_id)
    db, task = open_task(task_id, principal.user_id, owner_only=False)
    try:
        if task.owner_id != principal.user_id:
            raise HTTPException(status_code=403, detail="Only the owner can delete a task")
        db.delete(task)
        db.commit()
        return Response(status_code=204)
    finally:
        db.close()
