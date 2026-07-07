import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import SCHEMA, Base, TenantMixin, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.resource import ResourceCategory
    from app.models.task import DispatchTask


class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class UrgencyLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HelpRequest(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "help_requests"

    # logical references to schema_iam.users — bare UUIDs, NO cross-schema FK
    requester_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    requester_name: Mapped[str | None] = mapped_column(String(200))
    requester_phone: Mapped[str | None] = mapped_column(String(30))

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.resource_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_needed: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    urgency: Mapped[UrgencyLevel] = mapped_column(
        Enum(UrgencyLevel, name="urgency_level", inherit_schema=True),
        default=UrgencyLevel.MEDIUM,
        nullable=False,
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status", inherit_schema=True),
        default=RequestStatus.PENDING,
        nullable=False,
        index=True,
    )
    extra_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    area: Mapped[str | None] = mapped_column(String(200))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    category: Mapped["ResourceCategory"] = relationship()
    tasks: Mapped[list["DispatchTask"]] = relationship(back_populates="request")
