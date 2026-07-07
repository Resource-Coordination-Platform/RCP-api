"""Inventory & Resource Tracking service models.

ResourceCategory implements the "Customizable Workflow Engine": tenant
admins define their own categories (e.g. Emergency Shelter, Food Bank)
with a JSON form schema — no code changes required.
"""

import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class InventoryStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    DEPLETED = "depleted"
    EXPIRED = "expired"


class ResourceCategory(Base, TenantMixin, TimestampMixin):
    __tablename__ = "resource_categories"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(50), default="unit", nullable=False)
    # admin-defined extra fields for this category's request/offer forms,
    # e.g. [{"name": "family_size", "type": "number", "required": true}]
    form_schema: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="resource_categories")
    items: Mapped[list["InventoryItem"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class InventoryItem(Base, TenantMixin, TimestampMixin):
    """A tracked stock of donated goods (food, medicine, tools)."""

    __tablename__ = "inventory_items"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resource_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # reserved = promised to an approved request but not yet delivered
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[InventoryStatus] = mapped_column(
        Enum(InventoryStatus, name="inventory_status"),
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
