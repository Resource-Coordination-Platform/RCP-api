"""Inventory: categories + stock with row-locked atomic reservation."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.events.publisher import emit
from app.models import InventoryItem, InventoryStatus, ResourceCategory
from app.schemas.resource_schema import InventoryItemCreate, ResourceCategoryCreate

LOW_STOCK_THRESHOLD = 5


def create_category(
    db: Session, tenant_id: uuid.UUID, data: ResourceCategoryCreate
) -> ResourceCategory:
    category = ResourceCategory(tenant_id=tenant_id, **data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def list_categories(db: Session, tenant_id: uuid.UUID) -> list[ResourceCategory]:
    return list(
        db.scalars(
            select(ResourceCategory)
            .where(
                ResourceCategory.tenant_id == tenant_id,
                ResourceCategory.is_active.is_(True),
            )
            .order_by(ResourceCategory.name)
        )
    )


def add_inventory_item(
    db: Session, tenant_id: uuid.UUID, data: InventoryItemCreate
) -> InventoryItem:
    item = InventoryItem(tenant_id=tenant_id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_inventory(db: Session, tenant_id: uuid.UUID) -> list[InventoryItem]:
    return list(
        db.scalars(
            select(InventoryItem)
            .where(InventoryItem.tenant_id == tenant_id)
            .order_by(InventoryItem.created_at.desc())
        )
    )


def reserve_stock(
    db: Session, principal: Principal, item_id: uuid.UUID, quantity: int
) -> InventoryItem:
    """Row-locked so concurrent approvals during a crisis spike cannot
    oversell stock."""
    item = db.scalars(
        select(InventoryItem)
        .where(InventoryItem.id == item_id, InventoryItem.tenant_id == principal.tenant_id)
        .with_for_update()
    ).one_or_none()
    if item is None:
        raise ValueError("Inventory item not found")
    if item.quantity_available < quantity:
        raise ValueError(f"Only {item.quantity_available} available, {quantity} requested")

    item.quantity_reserved += quantity
    if item.quantity_available == 0:
        item.status = InventoryStatus.RESERVED
    if item.quantity_available <= LOW_STOCK_THRESHOLD:
        emit(
            db,
            routing_key="logistics.inventory.low-stock",
            tenant_id=principal.tenant_id,
            data={
                "item_id": str(item.id),
                "category_id": str(item.category_id),
                "name": item.name,
                "quantity_available": item.quantity_available,
            },
        )
    db.commit()
    db.refresh(item)
    return item


def release_stock(
    db: Session, tenant_id: uuid.UUID, item_id: uuid.UUID, quantity: int
) -> InventoryItem:
    item = db.scalars(
        select(InventoryItem)
        .where(InventoryItem.id == item_id, InventoryItem.tenant_id == tenant_id)
        .with_for_update()
    ).one_or_none()
    if item is None:
        raise ValueError("Inventory item not found")

    item.quantity_reserved = max(0, item.quantity_reserved - quantity)
    if item.quantity_available > 0 and item.status == InventoryStatus.RESERVED:
        item.status = InventoryStatus.AVAILABLE
    db.commit()
    db.refresh(item)
    return item
