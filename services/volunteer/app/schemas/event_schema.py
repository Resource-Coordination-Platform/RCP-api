import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.districts import is_valid_district
from app.models.event import AssignmentStatus, BroadcastType, EventStatus, RequirementStatus


class RequirementCreate(BaseModel):
    skill: str = Field(min_length=2, max_length=100)
    required_count: int = Field(gt=0, le=1000)

    @field_validator("skill")
    @classmethod
    def normalise_skill(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_")


class DisasterEventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    source_district: str
    broadcast_type: BroadcastType = BroadcastType.RADIUS_L1
    # TARGETED only: explicit distant districts (adjacency bypassed)
    target_districts: list[str] | None = None
    requirements: list[RequirementCreate] = Field(min_length=1, max_length=50)

    @field_validator("source_district")
    @classmethod
    def district_must_exist(cls, v: str) -> str:
        if not is_valid_district(v):
            raise ValueError(f"Unknown district: {v!r}")
        return v

    @model_validator(mode="after")
    def targets_match_broadcast(self) -> "DisasterEventCreate":
        if self.broadcast_type is BroadcastType.TARGETED and not self.target_districts:
            raise ValueError("TARGETED broadcast requires target_districts")
        if self.broadcast_type is not BroadcastType.TARGETED and self.target_districts:
            raise ValueError("target_districts only applies to TARGETED broadcasts")
        skills = [r.skill for r in self.requirements]
        if len(skills) != len(set(skills)):
            raise ValueError("Duplicate skill buckets in requirements")
        return self


class RequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    skill: str
    required_count: int
    filled_count: int
    status: RequirementStatus


class DisasterEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    description: str | None
    source_district: str
    broadcast_type: BroadcastType
    target_districts: list[str]
    status: EventStatus
    requirements: list[RequirementRead]
    created_at: datetime


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    requirement_id: uuid.UUID
    volunteer_id: uuid.UUID
    status: AssignmentStatus
    responded_at: datetime | None
    created_at: datetime
