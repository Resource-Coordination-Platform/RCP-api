"""Volunteer profiles with skills and availability — feeds the
Volunteer Dispatch & Task service (skill/location-based assignment)."""

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Column, Enum, Float, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import DispatchTask
    from app.models.user import User


class AvailabilityStatus(str, enum.Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


# many-to-many: a volunteer has many skills, a skill belongs to many volunteers
volunteer_skills = Table(
    "volunteer_skills",
    Base.metadata,
    Column(
        "volunteer_id",
        UUID(as_uuid=True),
        ForeignKey("volunteer_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Skill(Base):
    """Skill catalogue, e.g. first aid, plumbing, transport."""

    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    volunteers: Mapped[list["VolunteerProfile"]] = relationship(
        secondary=volunteer_skills, back_populates="skills"
    )


class VolunteerProfile(Base, TenantMixin, TimestampMixin):
    __tablename__ = "volunteer_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    availability: Mapped[AvailabilityStatus] = mapped_column(
        Enum(AvailabilityStatus, name="availability_status"),
        default=AvailabilityStatus.OFFLINE,
        nullable=False,
    )
    # coarse location for "nearby task" matching (no GPS hardware — out of scope)
    area: Mapped[str | None] = mapped_column(String(200))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    user: Mapped["User"] = relationship(back_populates="volunteer_profile")
    skills: Mapped[list[Skill]] = relationship(
        secondary=volunteer_skills, back_populates="volunteers"
    )
    tasks: Mapped[list["DispatchTask"]] = relationship(back_populates="volunteer")
