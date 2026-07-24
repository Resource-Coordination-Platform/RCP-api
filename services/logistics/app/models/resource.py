import enum
import uuid
from datetime import date
from typing import Any

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import SCHEMA, Base, TenantMixin, TimestampMixin, UUIDPkMixin


class InventoryStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    DEPLETED = "depleted"
    EXPIRED = "expired"


class ResourceCategory(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    """The customizable workflow engine: admins define categories with a
    JSONB form schema and approval flow, no code changes required.

    Both JSONB columns are validated before they are written
    (`app/services/form_schema.py`, `app/services/workflow.py`) and enforced
    on every request that uses the category — a definition here is a
    contract, not documentation."""

    __tablename__ = "resource_categories"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(50), default="unit", nullable=False)
    form_schema: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    # {"initial": ..., "transitions": {...}} — null means the platform default
    workflow: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    items: Mapped[list["InventoryItem"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class InventoryItem(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "inventory_items"

    # in-schema FK: allowed and encouraged
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.resource_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[InventoryStatus] = mapped_column(
        Enum(InventoryStatus, name="inventory_status", inherit_schema=True),
        default=InventoryStatus.AVAILABLE,
        nullable=False,
    )
    expiry_date: Mapped[date | None] = mapped_column(Date)
    storage_location: Mapped[str | None] = mapped_column(String(200))
    donor_name: Mapped[str | None] = mapped_column(String(200))

    category: Mapped[ResourceCategory] = relationship(back_populates="items")

    @property
    def quantity_available(self) -> int:
        return self.quantity_total - self.quantity_reserved
