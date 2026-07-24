import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.resource import InventoryStatus
from app.services import form_schema as form_schema_service
from app.services import workflow as workflow_service


class ResourceCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    unit: str = Field(default="unit", min_length=1, max_length=50)
    form_schema: list[dict[str, Any]] | None = None
    workflow: dict[str, Any] | None = None

    @field_validator("form_schema")
    @classmethod
    def _check_form_schema(cls, value: Any) -> Any:
        """Normalise at the edge so a malformed definition is a 422 here, not
        a surprise at request-submission time."""
        return form_schema_service.validate_definition(value)

    @field_validator("workflow")
    @classmethod
    def _check_workflow(cls, value: Any) -> Any:
        return workflow_service.validate_definition(value)


class ResourceCategoryUpdate(BaseModel):
    """Partial update. Fields left out are untouched; an explicit null on
    form_schema/workflow clears it back to the platform default."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    form_schema: list[dict[str, Any]] | None = None
    workflow: dict[str, Any] | None = None
    is_active: bool | None = None

    @field_validator("form_schema")
    @classmethod
    def _check_form_schema(cls, value: Any) -> Any:
        return form_schema_service.validate_definition(value)

    @field_validator("workflow")
    @classmethod
    def _check_workflow(cls, value: Any) -> Any:
        return workflow_service.validate_definition(value)


class ResourceCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    unit: str
    form_schema: list[dict[str, Any]] | None
    workflow: dict[str, Any] | None
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
