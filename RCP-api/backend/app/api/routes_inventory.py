"""Inventory & Resource Tracking service endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.db.database import get_db
from app.models import User, UserRole
from app.schemas.resource_schema import (
    InventoryItemCreate,
    InventoryItemRead,
    ResourceCategoryCreate,
    ResourceCategoryRead,
)
from app.services import inventory as inventory_service

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.post(
    "/categories",
    response_model=ResourceCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    data: ResourceCategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.TENANT_ADMIN)),
):
    """Customizable workflow engine: admin defines a resource category."""
    return inventory_service.create_category(db, user.tenant_id, data)


@router.get("/categories", response_model=list[ResourceCategoryRead])
def list_categories(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return inventory_service.list_categories(db, user.tenant_id)


@router.post("/items", response_model=InventoryItemRead, status_code=status.HTTP_201_CREATED)
def add_item(
    data: InventoryItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.TENANT_ADMIN, UserRole.COORDINATOR)
    ),
):
    return inventory_service.add_inventory_item(db, user.tenant_id, data)


@router.get("/items", response_model=list[InventoryItemRead])
def list_items(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.TENANT_ADMIN, UserRole.COORDINATOR)
    ),
):
    return inventory_service.list_inventory(db, user.tenant_id)


@router.post("/items/{item_id}/reserve", response_model=InventoryItemRead)
def reserve(
    item_id: uuid.UUID,
    quantity: int,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.TENANT_ADMIN, UserRole.COORDINATOR)
    ),
):
    try:
        return inventory_service.reserve_stock(db, user.tenant_id, item_id, quantity)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
