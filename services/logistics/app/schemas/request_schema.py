import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.request import RequestStatus, UrgencyLevel


class HelpRequestCreate(BaseModel):
    category_id: uuid.UUID
    description: str
    quantity_needed: int = Field(default=1, ge=1)
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    requester_name: str | None = None
    requester_phone: str | None = None
    area: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_sensitive: bool = False
    extra_fields: dict[str, Any] | None = None


class HelpRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    category_id: uuid.UUID
    description: str
    quantity_needed: int
    urgency: UrgencyLevel
    status: RequestStatus
    area: str | None
    is_sensitive: bool
    created_at: datetime
    verified_at: datetime | None
    fulfilled_at: datetime | None


class HelpRequestStatusUpdate(BaseModel):
    status: RequestStatus
