import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, current_principal
from app.db.database import get_db
from app.models import GLOBAL_USER_TYPES, Tenant, User, UserType
from app.schemas.auth_schema import (
    GlobalUserRegister,
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    RefreshRequest,
    TenantOnboard,
    TenantRead,
    TenantUserRegister,
    TokenPair,
    UserRead,
)
from app.services import auth as auth_service 


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def onboard_tenant(data: TenantOnboard, db: Session = Depends(get_db)):
    if db.scalars(select(Tenant).where(Tenant.slug == data.slug)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken")
    return auth_service.onboard_tenant(db, data)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_global(data: GlobalUserRegister, db: Session = Depends(get_db)):
    """Mobile-app signup (global pool: VOLUNTEER / VICTIM )."""
    if data.user_type not in GLOBAL_USER_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Mobile registration accepts VOLUNTEER, VICTIM or DONATOR only",
        )
    if db.scalars(
        select(User).where(User.tenant_id.is_(None), User.email == data.email)
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return auth_service.register_global_user(db, data)


@router.post(
    "/tenants/{tenant_slug}/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register_tenant_user(
    tenant_slug: str, data: TenantUserRegister, db: Session = Depends(get_db)
):
    """Web-portal signup under a tenant. Self-registration is COORDINATOR
    only; TENANT_ADMIN exists solely through tenant onboarding."""
    if data.user_type != UserType.COORDINATOR:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Tenant registration accepts COORDINATOR only",
        )
    tenant = db.scalars(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if tenant is None or tenant.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    if db.scalars(
        select(User).where(User.tenant_id == tenant.id, User.email == data.email)
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return auth_service.register_tenant_user(db, tenant, data)


@router.post("/login", response_model=TokenPair)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """One endpoint, two populations: requests carrying tenant_slug resolve
    against that tenant's users; requests without it resolve against the
    global pool. A portal user can never log in through the mobile path
    (and vice versa) because the lookups are disjoint by tenant_id."""
    try:
        pair = auth_service.login(db, data)
        if pair is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
        return pair
    except ValueError as exc:
        if str(exc) == "USER_DISABLED":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Your account has been disabled or banned. Please contact support.",
            )
        if str(exc) == "TENANT_SUSPENDED":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Your organization/tenant account has been suspended. Please contact support.",
            )
        raise


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    pair = auth_service.refresh(db, data.refresh_token)
    if pair is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return pair



""" New additional endpoints added by Kesh"""
# අලුතින් එකතු කරන GET Endpoint එක
@router.get("/tenants", response_model=list[TenantRead])
def get_tenants(db: Session = Depends(get_db)):
    """මෙමඟින් සියලුම Tenants ලාගේ ලැයිස්තුව ලබාදේ."""
    return auth_service.get_all_tenants(db)


@router.get("/me", response_model=UserRead)
def get_current_user_profile(
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    """Fetch current logged-in user profile."""
    user = auth_service.get_user_by_id(db, uuid.UUID(principal.user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.patch("/me", response_model=UserRead)
def update_current_user_profile(
    data: ProfileUpdate,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    """Update profile details (full_name, phone) of the logged-in user."""
    user = auth_service.update_user_profile(db, uuid.UUID(principal.user_id), data)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.post("/me/change-password")
def change_password(
    data: PasswordChange,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    """Change current logged-in user password."""
    try:
        success = auth_service.change_user_password(
            db, uuid.UUID(principal.user_id), data
        )
        if not success:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        return {"message": "Password changed successfully"}
    except ValueError as exc:
        if str(exc) == "INVALID_CURRENT_PASSWORD":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Current password is incorrect"
            )
        raise