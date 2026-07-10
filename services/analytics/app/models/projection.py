import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import SCHEMA, Base


class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class InventoryStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    DEPLETED = "depleted"
    EXPIRED = "expired"


class CategoryProjection(Base):
    __tablename__ = "analytics_categories"

    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="unit")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InventoryProjection(Base):
    __tablename__ = "analytics_inventory_items"

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.analytics_categories.category_id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=InventoryStatus.AVAILABLE.value)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RequestProjection(Base):
    __tablename__ = "analytics_requests"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    quantity_needed: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RequestStatus.PENDING.value)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProcessedEvent(Base):
    """Idempotency ledger for event-driven projections.

    Today's dashboard endpoints query the logistics read model directly;
    as heavier aggregates arrive they will be materialized into
    schema_analytics from rcp.events, deduplicated through this table.
    """

    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
