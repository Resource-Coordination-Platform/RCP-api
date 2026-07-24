"""Inventory: categories + stock with row-locked atomic reservation."""

import uuid

from rcp_common.exceptions import NotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.events.publisher import emit
from app.models import InventoryItem, InventoryStatus, ResourceCategory
from app.schemas.resource_schema import (
    InventoryItemCreate,
    ResourceCategoryCreate,
    ResourceCategoryUpdate,
)

LOW_STOCK_THRESHOLD = 5


def _category_event(category: ResourceCategory) -> dict:
    now = category.updated_at or category.created_at
    return {
        "category_id": str(category.id),
        "name": category.name,
        "description": category.description,
        "unit": category.unit,
        "is_active": category.is_active,
        "updated_at": now.isoformat() if now else None,
    }


def create_category(
    db: Session, tenant_id: uuid.UUID, data: ResourceCategoryCreate
) -> ResourceCategory:
    category = ResourceCategory(tenant_id=tenant_id, **data.model_dump())
    db.add(category)
    db.flush()
    emit(
        db,
        routing_key="logistics.resource-category.created",
        tenant_id=tenant_id,
        data=_category_event(category),
    )
    db.commit()
    db.refresh(category)
    return category


def list_categories(
    db: Session, tenant_id: uuid.UUID, include_inactive: bool = False
) -> list[ResourceCategory]:
    stmt = (
        select(ResourceCategory)
        .where(ResourceCategory.tenant_id == tenant_id)
        .order_by(ResourceCategory.name)
    )
    if not include_inactive:
        stmt = stmt.where(ResourceCategory.is_active.is_(True))
    return list(db.scalars(stmt))


def get_category(
    db: Session, tenant_id: uuid.UUID, category_id: uuid.UUID
) -> ResourceCategory:
    category = db.scalars(
        select(ResourceCategory).where(
            ResourceCategory.id == category_id,
            ResourceCategory.tenant_id == tenant_id,
        )
    ).one_or_none()
    if category is None:
        raise NotFoundError("Resource category not found")
    return category


def update_category(
    db: Session,
    tenant_id: uuid.UUID,
    category_id: uuid.UUID,
    data: ResourceCategoryUpdate,
) -> ResourceCategory:
    """Partial update. Definitions were already validated by the schema
    layer; requests submitted *before* the change keep the extra_fields they
    were validated against — a redefinition is never applied retroactively."""
    category = get_category(db, tenant_id, category_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.flush()
    emit(
        db,
        routing_key="logistics.resource-category.updated",
        tenant_id=tenant_id,
        data=_category_event(category),
    )
    db.commit()
    db.refresh(category)
    return category


def deactivate_category(
    db: Session, tenant_id: uuid.UUID, category_id: uuid.UUID
) -> ResourceCategory:
    """Retire a category without destroying history: help requests reference
    it with ON DELETE RESTRICT, and a fulfilled request must stay auditable,
    so retirement is always a soft delete."""
    category = get_category(db, tenant_id, category_id)
    if category.is_active:
        category.is_active = False
        db.flush()
        emit(
            db,
            routing_key="logistics.resource-category.updated",
            tenant_id=tenant_id,
            data=_category_event(category),
        )
        db.commit()
        db.refresh(category)
    return category


def add_inventory_item(
    db: Session, tenant_id: uuid.UUID, data: InventoryItemCreate
) -> InventoryItem:
    item = InventoryItem(tenant_id=tenant_id, **data.model_dump())
    db.add(item)
    db.flush()
    now = item.created_at
    emit(
        db,
        routing_key="logistics.inventory.item-updated",
        tenant_id=tenant_id,
        data={
            "item_id": str(item.id),
            "category_id": str(item.category_id),
            "name": item.name,
            "quantity_total": item.quantity_total,
            "quantity_reserved": item.quantity_reserved,
            "quantity_available": item.quantity_available,
            "status": item.status.value,
            "updated_at": now.isoformat() if now else None,
        },
    )
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
    now = item.updated_at
    emit(
        db,
        routing_key="logistics.inventory.item-updated",
        tenant_id=principal.tenant_id,
        data={
            "item_id": str(item.id),
            "category_id": str(item.category_id),
            "name": item.name,
            "quantity_total": item.quantity_total,
            "quantity_reserved": item.quantity_reserved,
            "quantity_available": item.quantity_available,
            "status": item.status.value,
            "updated_at": now.isoformat() if now else None,
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
    now = item.updated_at
    emit(
        db,
        routing_key="logistics.inventory.item-updated",
        tenant_id=tenant_id,
        data={
            "item_id": str(item.id),
            "category_id": str(item.category_id),
            "name": item.name,
            "quantity_total": item.quantity_total,
            "quantity_reserved": item.quantity_reserved,
            "quantity_available": item.quantity_available,
            "status": item.status.value,
            "updated_at": now.isoformat() if now else None,
        },
    )
    db.commit()
    db.refresh(item)
    return item
