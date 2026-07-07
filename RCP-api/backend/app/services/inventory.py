"""Inventory & Resource Tracking service logic (ORM examples).

Stock reservation uses row-level locking (SELECT ... FOR UPDATE) so
concurrent approvals during a crisis spike cannot oversell stock —
this is the "data integrity under high-volume requests" requirement.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InventoryItem, InventoryStatus, ResourceCategory
from app.schemas.resource_schema import InventoryItemCreate, ResourceCategoryCreate


def create_category(
    db: Session, tenant_id: uuid.UUID, data: ResourceCategoryCreate
) -> ResourceCategory:
    category = ResourceCategory(tenant_id=tenant_id, **data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def list_categories(db: Session, tenant_id: uuid.UUID) -> list[ResourceCategory]:
    stmt = (
        select(ResourceCategory)
        .where(
            ResourceCategory.tenant_id == tenant_id,
            ResourceCategory.is_active.is_(True),
        )
        .order_by(ResourceCategory.name)
    )
    return list(db.scalars(stmt))


def add_inventory_item(
    db: Session, tenant_id: uuid.UUID, data: InventoryItemCreate
) -> InventoryItem:
    item = InventoryItem(tenant_id=tenant_id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_inventory(db: Session, tenant_id: uuid.UUID) -> list[InventoryItem]:
    stmt = (
        select(InventoryItem)
        .where(InventoryItem.tenant_id == tenant_id)
        .order_by(InventoryItem.created_at.desc())
    )
    return list(db.scalars(stmt))


def reserve_stock(
    db: Session, tenant_id: uuid.UUID, item_id: uuid.UUID, quantity: int
) -> InventoryItem:
    """Atomically reserve stock for an approved request."""
    stmt = (
        select(InventoryItem)
        .where(InventoryItem.id == item_id, InventoryItem.tenant_id == tenant_id)
        .with_for_update()
    )
    item = db.scalars(stmt).one_or_none()
    if item is None:
        raise ValueError("Inventory item not found")
    if item.quantity_available < quantity:
        raise ValueError(
            f"Only {item.quantity_available} available, {quantity} requested"
        )

    item.quantity_reserved += quantity
    if item.quantity_available == 0:
        item.status = InventoryStatus.RESERVED
    db.commit()
    db.refresh(item)
    return item


def release_stock(
    db: Session, tenant_id: uuid.UUID, item_id: uuid.UUID, quantity: int
) -> InventoryItem:
    """Return reserved stock (e.g. a request was cancelled)."""
    stmt = (
        select(InventoryItem)
        .where(InventoryItem.id == item_id, InventoryItem.tenant_id == tenant_id)
        .with_for_update()
    )
    item = db.scalars(stmt).one_or_none()
    if item is None:
        raise ValueError("Inventory item not found")

    item.quantity_reserved = max(0, item.quantity_reserved - quantity)
    if item.quantity_available > 0 and item.status == InventoryStatus.RESERVED:
        item.status = InventoryStatus.AVAILABLE
    db.commit()
    db.refresh(item)
    return item
