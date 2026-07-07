from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Tenant, User
from app.schemas.auth_schema import (
    LoginRequest,
    RefreshRequest,
    TenantOnboard,
    TenantRead,
    TokenPair,
    UserRegister,
    UserRead,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def onboard_tenant(data: TenantOnboard, db: Session = Depends(get_db)):
    if db.scalars(select(Tenant).where(Tenant.slug == data.slug)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken")
    return auth_service.onboard_tenant(db, data)


@router.post(
    "/tenants/{tenant_slug}/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register(tenant_slug: str, data: UserRegister, db: Session = Depends(get_db)):
    tenant = db.scalars(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if tenant is None or tenant.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    if db.scalars(
        select(User).where(User.tenant_id == tenant.id, User.email == data.email)
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return auth_service.register_user(db, tenant, data)


@router.post("/login", response_model=TokenPair)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    pair = auth_service.login(db, data)
    if pair is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return pair


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    pair = auth_service.refresh(db, data.refresh_token)
    if pair is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return pair
