import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.resource import InventoryStatus


class ResourceCategoryCreate(BaseModel):
    name: str
    description: str | None = None
    unit: str = "unit"
    form_schema: list[dict[str, Any]] | None = None


class ResourceCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    unit: str
    form_schema: list[dict[str, Any]] | None
    is_active: bool


class InventoryItemCreate(BaseModel):
    category_id: uuid.UUID
    name: str
    quantity_total: int = Field(ge=0)
    expiry_date: date | None = None
    storage_location: str | None = None
    donor_name: str | None = None


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    quantity_total: int
    quantity_reserved: int
    quantity_available: int
    status: InventoryStatus
    expiry_date: date | None
    storage_location: str | None
    created_at: datetime
