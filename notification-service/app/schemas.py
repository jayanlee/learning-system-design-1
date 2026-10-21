import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    task_id: uuid.UUID | None
    type: str
    payload: dict
    read_at: datetime | None
    created_at: datetime
