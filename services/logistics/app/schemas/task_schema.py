import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.task import TaskStatus


class DispatchTaskCreate(BaseModel):
    request_id: uuid.UUID
    volunteer_user_id: uuid.UUID
    title: str
    instructions: str | None = None


class DispatchTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    volunteer_user_id: uuid.UUID
    title: str
    instructions: str | None
    status: TaskStatus
    created_at: datetime
    accepted_at: datetime | None
    completed_at: datetime | None
