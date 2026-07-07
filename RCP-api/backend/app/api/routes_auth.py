"""Identity & Tenant Management service endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.models import Tenant, User, UserRole
from app.schemas.tenant_schema import TenantCreate, TenantRead
from app.schemas.user_schema import Token, UserCreate, UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def register_tenant(data: TenantCreate, db: Session = Depends(get_db)):
    """Onboard a new community organisation (coordination hub)."""
    exists = db.scalars(select(Tenant).where(Tenant.slug == data.slug)).first()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken")
    tenant = Tenant(**data.model_dump())
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.post(
    "/tenants/{tenant_slug}/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register_user(tenant_slug: str, data: UserCreate, db: Session = Depends(get_db)):
    tenant = db.scalars(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")

    duplicate = db.scalars(
        select(User).where(User.tenant_id == tenant.id, User.email == data.email)
    ).first()
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    # public signup can never grant privileged roles
    role = data.role if data.role in (UserRole.MEMBER, UserRole.VOLUNTEER) else UserRole.MEMBER
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == form.username)).first()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = create_access_token(
        subject=str(user.id), tenant_id=str(user.tenant_id), role=user.role.value
    )
    return Token(access_token=token)
