from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import GLOBAL_USER_TYPES, Tenant, User, UserType
from app.schemas.auth_schema import (
    GlobalUserRegister,
    LoginRequest,
    RefreshRequest,
    TenantOnboard,
    TenantRead,
    TenantUserRegister,
    TenantLocationRead,  #new added by Kesh
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
            "Mobile registration accepts VOLUNTEER, VICTIM only",
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



""" New additional endpoints added by Kesh"""
# අලුතින් එකතු කරන GET Endpoint එක
@router.get("/tenants", response_model=list[TenantRead])
def get_tenants(db: Session = Depends(get_db)):
    """මෙමඟින් සියලුම Tenants ලාගේ ලැයිස්තුව ලබාදේ."""
    # අපි කලින් auth.py එකේ ලියපු function එකට කතා කරනවා
    return auth_service.get_all_tenants(db)



@router.get("/tenants/locations", response_model=list[TenantLocationRead])
def list_tenant_locations(
    db: Session = Depends(get_db),
    
):
    """Map එකේ පෙන්වන්න Location තියෙන Active Tenants (සංවිධාන) ඔක්කොම ගන්නවා"""
    tenants = db.scalars(
        select(Tenant)
        .where(
            Tenant.status == "active",
            Tenant.latitude.is_not(None),
            Tenant.longitude.is_not(None)
        )
    ).all()
    return list(tenants)
    