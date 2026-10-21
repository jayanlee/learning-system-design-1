import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification
from app.schemas import NotificationResponse
from app.security import bearer_scheme, get_user_id

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _to_response(row: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=row.id,
        user_id=row.user_id,
        task_id=row.task_id,
        type=row.type,
        payload=row.payload,
        read_at=row.read_at,
        created_at=row.created_at,
    )


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> list[NotificationResponse]:
    user_id = get_user_id(credentials)
    rows = db.scalars(
        select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
    ).all()
    return [_to_response(row) for row in rows]


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: uuid.UUID,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> NotificationResponse:
    user_id = get_user_id(credentials)
    row = db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
    return _to_response(row)
