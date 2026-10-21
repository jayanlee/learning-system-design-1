import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

TaskStatus = Literal["todo", "in_progress", "done"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = "todo"


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    version: int = Field(ge=1)


class AssignRequest(BaseModel):
    assignee_email: EmailStr
    version: int = Field(ge=1)


class TransferRequest(BaseModel):
    new_owner_email: EmailStr
    version: int = Field(ge=1)


class TaskResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    assignee_id: uuid.UUID | None
    assignee_email: str | None
    title: str
    description: str | None
    status: TaskStatus
    version: int
    created_at: datetime
    updated_at: datetime
