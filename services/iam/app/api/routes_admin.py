"""Super-admin (platform operator) console API.

Cross-tenant visibility and lifecycle control, all gated behind the
super_admin role. Tenant onboarding itself already lives at
POST /api/auth/tenants; this surface adds the operate/observe half.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_super_admin
from app.db.database import get_db
from app.models.user import UserType
from app.schemas.admin_schema import (
    AdminPasswordReset,
    AdminUserRead,
    PlatformStats,
    SuperAdminCreate,
    TenantStatusUpdate,
    TenantSummary,
    UserStatusUpdate,
)
from app.schemas.auth_schema import UserRead
from app.services import admin as admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=PlatformStats)
def platform_stats(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_super_admin),
):
    return admin_service.platform_stats(db)


@router.get("/tenants", response_model=list[TenantSummary])
def list_tenants(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_super_admin),
):
    return admin_service.list_tenants(db)


@router.get("/tenants/{tenant_id}", response_model=TenantSummary)
def get_tenant(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_super_admin),
):
    tenant = admin_service.get_tenant(db, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return tenant


@router.patch("/tenants/{tenant_id}/status", response_model=TenantSummary)
def update_tenant_status(
    tenant_id: uuid.UUID,
    data: TenantStatusUpdate,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_super_admin),
):
    tenant = admin_service.set_tenant_status(db, tenant_id, data.status)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return admin_service.get_tenant(db, tenant_id)


@router.get("/users", response_model=list[AdminUserRead])
def list_users(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_super_admin),
    tenant_id: uuid.UUID | None = None,
    user_type: UserType | None = None,
    status: str | None = None,
    q: str | None = None,
    scope: str | None = Query(default=None, pattern=r"^(global|tenant)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return admin_service.list_users(
        db,
        tenant_id=tenant_id,
        user_type=user_type,
        status=status,
        q=q,
        scope=scope,
        limit=limit,
        offset=offset,
    )


@router.patch("/users/{user_id}/status", response_model=AdminUserRead)
def update_user_status(
    user_id: uuid.UUID,
    data: UserStatusUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_super_admin),
):
    if str(user_id) == principal.user_id and data.status == "disabled":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "You cannot disable your own account"
        )
    user = admin_service.set_user_status(db, user_id, data.status)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "tenant_slug": None,
        "user_type": user.user_type,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "status": user.status,
        "roles": user.roles,
        "created_at": user.created_at,
    }


@router.post(
    "/super-admins",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_super_admin(
    data: SuperAdminCreate,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_super_admin),
):
    user = admin_service.create_super_admin(db, data)
    if user is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return user


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: uuid.UUID,
    data: AdminPasswordReset,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_super_admin),
):
    """Super-admin reset password for any user (e.g. setting a temporary password)."""
    user = admin_service.admin_reset_user_password(db, user_id, data.new_password)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return {"message": "Password reset successfully", "user_id": str(user_id)}
