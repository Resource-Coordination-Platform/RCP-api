import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from rcp_common.exceptions import NotFoundError
from sqlalchemy.orm import Session

from app.api.dependencies import get_principal, require_roles
from app.core.auth import Principal
from app.db.database import get_db
from app.schemas.resource_schema import (
    InventoryItemCreate,
    InventoryItemRead,
    ResourceCategoryCreate,
    ResourceCategoryRead,
    ResourceCategoryUpdate,
    DonationNeedRead,
)
from app.services import inventory as inventory_service


router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.post(
    "/categories", response_model=ResourceCategoryRead, status_code=status.HTTP_201_CREATED
)
def create_category(
    data: ResourceCategoryCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin")),
):
    return inventory_service.create_category(db, principal.tenant_id, data)


@router.get("/categories", response_model=list[ResourceCategoryRead])
def list_categories(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    return inventory_service.list_categories(db, principal.tenant_id, include_inactive)


@router.get("/categories/{category_id}", response_model=ResourceCategoryRead)
def get_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    try:
        return inventory_service.get_category(db, principal.tenant_id, category_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.patch("/categories/{category_id}", response_model=ResourceCategoryRead)
def update_category(
    category_id: uuid.UUID,
    data: ResourceCategoryUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin")),
):
    try:
        return inventory_service.update_category(db, principal.tenant_id, category_id, data)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.delete("/categories/{category_id}", response_model=ResourceCategoryRead)
def deactivate_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin")),
):
    """Soft delete: the category stops accepting new requests but stays
    attached to the ones already recorded against it."""
    try:
        return inventory_service.deactivate_category(db, principal.tenant_id, category_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.post("/items", response_model=InventoryItemRead, status_code=status.HTTP_201_CREATED)
def add_item(
    data: InventoryItemCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    return inventory_service.add_inventory_item(db, principal.tenant_id, data)


@router.get("/items", response_model=list[InventoryItemRead])
def list_items(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    return inventory_service.list_inventory(db, principal.tenant_id)


@router.post("/items/{item_id}/reserve", response_model=InventoryItemRead)
def reserve(
    item_id: uuid.UUID,
    quantity: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    try:
        return inventory_service.reserve_stock(db, principal, item_id, quantity)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))






@router.get("/needs", response_model=list[DonationNeedRead])
def list_donation_needs(
    db: Session = Depends(get_db),
    # මෙතන තමයි වැදගත්ම කෑල්ල. Volunteer ට only මේක බලන්න පුළුවන් වෙන්න ඕනේ!
    principal: Principal = Depends(require_roles("volunteer")),
):
    """Volunteer ට හිඟ බඩු (Shortages) බලාගන්න තියෙන Endpoint එක"""  #meka bn swagger ui eke penawana margopadeshaya yakow :)
    return inventory_service.get_donation_needs(db)