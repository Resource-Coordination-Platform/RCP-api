"""Request & Needs Management service: the lifecycle of a help request
from submission through verification to fulfilment."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.resource import ResourceCategory
    from app.models.task import DispatchTask
    from app.models.user import User


class RequestStatus(str, enum.Enum):
    PENDING = "pending"          # submitted, awaiting coordinator verification
    VERIFIED = "verified"        # confirmed as a genuine, non-duplicate need
    APPROVED = "approved"        # resources reserved / dispatch planned
    IN_PROGRESS = "in_progress"  # a volunteer task is underway
    FULFILLED = "fulfilled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class UrgencyLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HelpRequest(Base, TenantMixin, TimestampMixin):
    __tablename__ = "help_requests"

    # nullable: requests can be filed on behalf of someone without an account
    requester_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    requester_name: Mapped[str | None] = mapped_column(String(200))
    requester_phone: Mapped[str | None] = mapped_column(String(30))

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resource_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_needed: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    urgency: Mapped[UrgencyLevel] = mapped_column(
        Enum(UrgencyLevel, name="urgency_level"),
        default=UrgencyLevel.MEDIUM,
        nullable=False,
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        default=RequestStatus.PENDING,
        nullable=False,
        index=True,
    )
    # answers to the category's admin-defined form_schema fields
    extra_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    area: Mapped[str | None] = mapped_column(String(200))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    # privacy flag for vulnerable individuals: hide identity from volunteers
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    requester: Mapped["User | None"] = relationship(foreign_keys=[requester_id])
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_id])
    category: Mapped["ResourceCategory"] = relationship()
    tasks: Mapped[list["DispatchTask"]] = relationship(back_populates="request")
