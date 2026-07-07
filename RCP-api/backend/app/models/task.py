"""Volunteer Dispatch & Task service: a coordinator assigns a task
(deliver goods, provide a skill) to a volunteer for a verified request."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.request import HelpRequest
    from app.models.user import User
    from app.models.volunteer import VolunteerProfile


class TaskStatus(str, enum.Enum):
    ASSIGNED = "assigned"    # dispatched, awaiting volunteer response
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class DispatchTask(Base, TenantMixin, TimestampMixin):
    __tablename__ = "dispatch_tasks"

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("help_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    volunteer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("volunteer_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"),
        default=TaskStatus.ASSIGNED,
        nullable=False,
        index=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    request: Mapped["HelpRequest"] = relationship(back_populates="tasks")
    volunteer: Mapped["VolunteerProfile"] = relationship(back_populates="tasks")
    assigned_by: Mapped["User | None"] = relationship()
