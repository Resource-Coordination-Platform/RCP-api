"""DisasterEvent aggregate: the event, its skill quotas, and the
volunteer assignments against those quotas.

Concurrency contract: EventRequirement.filled_count is only ever moved
by an atomic conditional UPDATE (filled_count < required_count) — see
services/matching.py. That single statement is the first-come-first-serve
gate; no application-level lock is involved.
"""

import enum
import uuid
from datetime import datetime


from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import SCHEMA, Base, TenantMixin, TimestampMixin, UUIDPkMixin


class EventStatus(str, enum.Enum):
    DECLARED = "DECLARED"          # created; matching not yet run
    BROADCASTING = "BROADCASTING"  # notifications out, quotas filling
    TEAM_FORMED = "TEAM_FORMED"    # every requirement fulfilled
    CLOSED = "CLOSED"              # tenant closed the response


class BroadcastType(str, enum.Enum):
    RADIUS_L1 = "RADIUS_L1"  # source district only
    RADIUS_L2 = "RADIUS_L2"  # source district + adjacency list
    TARGETED = "TARGETED"    # explicit distant district(s), bypassing adjacency


class RequirementStatus(str, enum.Enum):
    OPEN = "OPEN"
    FULFILLED = "FULFILLED"


class AssignmentStatus(str, enum.Enum):
    NOTIFIED = "NOTIFIED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    REJECTED_FULL = "REJECTED_FULL"  # accepted too late: quota already full
    EN_ROUTE = "EN_ROUTE"
    COMPLETED = "COMPLETED"


class DisasterEvent(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "disaster_events"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # canonical district name from app/domain/districts.py
    source_district: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    broadcast_type: Mapped[BroadcastType] = mapped_column(
        Enum(BroadcastType, name="broadcast_type", inherit_schema=True),
        default=BroadcastType.RADIUS_L1,
        nullable=False,
    )
    # TARGETED only: the explicit districts to draw volunteers from
    target_districts: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status", inherit_schema=True),
        default=EventStatus.DECLARED,
        nullable=False,
        index=True,
    )
    # who declared it (schema_iam.users id, logical reference)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    requirements: Mapped[list["EventRequirement"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["EventVolunteerMapping"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    
    # 👇 මෙන්න මේ Location Columns දෙක අලුතින් එකතු කරන්න Map ekata
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)


class EventRequirement(Base, UUIDPkMixin, TimestampMixin):
    """A skill bucket with a quota, e.g. boat_driver 0/10."""

    __tablename__ = "event_requirements"
    __table_args__ = (
        UniqueConstraint("event_id", "skill", name="uq_event_requirements_event_skill"),
        CheckConstraint("required_count > 0", name="ck_event_requirements_positive"),
        CheckConstraint(
            "filled_count >= 0 AND filled_count <= required_count",
            name="ck_event_requirements_bounds",
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.disaster_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill: Mapped[str] = mapped_column(String(100), nullable=False)
    required_count: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[RequirementStatus] = mapped_column(
        Enum(RequirementStatus, name="requirement_status", inherit_schema=True),
        default=RequirementStatus.OPEN,
        nullable=False,
    )

    event: Mapped[DisasterEvent] = relationship(back_populates="requirements")

    @property
    def is_full(self) -> bool:
        return self.filled_count >= self.required_count


class EventVolunteerMapping(Base, UUIDPkMixin, TimestampMixin):
    """Bridge: one volunteer's participation in one event, against one
    skill bucket. A volunteer holds at most one assignment per event."""

    __tablename__ = "event_volunteer_mappings"
    __table_args__ = (
        UniqueConstraint("event_id", "volunteer_id", name="uq_evm_event_volunteer"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.disaster_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.event_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    volunteer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.volunteer_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignment_status", inherit_schema=True),
        default=AssignmentStatus.NOTIFIED,
        nullable=False,
        index=True,
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    event: Mapped[DisasterEvent] = relationship(back_populates="assignments")
    requirement: Mapped[EventRequirement] = relationship()
    # resolved from the registry once app.models is imported
    volunteer: Mapped["VolunteerProfile"] = relationship()  # noqa: F821
