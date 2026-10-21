import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IdempotencyKey


def request_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def replay(db: Session, user_id: uuid.UUID, key: str | None, body_hash: str) -> JSONResponse | None:
    if not key:
        return None
    row = db.get(IdempotencyKey, (user_id, key))
    if row is None:
        return None
    if row.request_hash != body_hash:
        raise HTTPException(status_code=409, detail="Idempotency key was already used with a different request")
    return JSONResponse(status_code=row.response_status, content=row.response_body)


def remember(
    db: Session,
    user_id: uuid.UUID,
    key: str | None,
    body_hash: str,
    status_code: int,
    body: dict,
) -> None:
    if not key:
        return
    db.add(
        IdempotencyKey(
            user_id=user_id,
            key=key,
            request_hash=body_hash,
            response_status=status_code,
            response_body=body,
            created_at=datetime.now(timezone.utc),
        )
    )


def commit_or_replay(
    db: Session,
    user_id: uuid.UUID,
    key: str | None,
    body_hash: str,
) -> JSONResponse | None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        stored = replay(db, user_id, key, body_hash)
        if stored is not None:
            return stored
        raise HTTPException(status_code=409, detail="Idempotency key was already used with a different request") from None
    return None
