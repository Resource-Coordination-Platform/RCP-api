import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.districts import is_valid_district


class VolunteerProfileUpdate(BaseModel):
    """Fields the volunteer edits from the mobile app. Identity fields
    (name, phone) are replicated from IAM and not editable here."""

    base_district: str
    city: str | None = None
    available_status: bool = False
    skills: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("base_district")
    @classmethod
    def district_must_exist(cls, v: str) -> str:
        if not is_valid_district(v):
            raise ValueError(f"Unknown district: {v!r}")
        return v

    @field_validator("skills")
    @classmethod
    def normalise_skills(cls, v: list[str]) -> list[str]:
        return sorted({s.strip().lower().replace(" ", "_") for s in v if s.strip()})


class AvailabilityUpdate(BaseModel):
    available_status: bool


class VolunteerProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    phone: str | None
    base_district: str | None
    city: str | None
    available_status: bool
    skills: list[str]
    is_active: bool
    created_at: datetime


class VolunteerDirectoryEntry(BaseModel):
    """What the web portal sees. Separate from VolunteerProfileRead so the
    self-service and coordinator views can diverge without one leaking
    fields into the other. `phone` is included deliberately: a coordinator
    who dispatches a volunteer needs to be able to reach them."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    phone: str | None
    base_district: str | None
    city: str | None
    available_status: bool
    skills: list[str]
    created_at: datetime


class VolunteerDirectoryPage(BaseModel):
    items: list[VolunteerDirectoryEntry]
    total: int
    limit: int
    offset: int
