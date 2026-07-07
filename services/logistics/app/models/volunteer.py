"""Volunteer *operational* profiles. Identity (name, login) lives in IAM;
this schema owns only what dispatch needs: skills, availability, area."""

import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import SCHEMA, Base, TenantMixin, TimestampMixin, UUIDPkMixin


class AvailabilityStatus(str, enum.Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class VolunteerProfile(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "volunteer_profiles"

    # logical reference to schema_iam.users — NO cross-schema FK
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    availability: Mapped[AvailabilityStatus] = mapped_column(
        Enum(AvailabilityStatus, name="availability_status", inherit_schema=True),
        default=AvailabilityStatus.OFFLINE,
        nullable=False,
    )
    area: Mapped[str | None] = mapped_column(String(200))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    skills: Mapped[list["VolunteerSkill"]] = relationship(
        back_populates="volunteer", cascade="all, delete-orphan"
    )

    @property
    def skill_names(self) -> list[str]:
        return [s.skill for s in self.skills]


class VolunteerSkill(Base, UUIDPkMixin):
    __tablename__ = "volunteer_skills"

    volunteer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.volunteer_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill: Mapped[str] = mapped_column(String(100), nullable=False)

    volunteer: Mapped[VolunteerProfile] = relationship(back_populates="skills")
