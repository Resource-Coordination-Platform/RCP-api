"""Auth domain logic: onboarding, registration, login, refresh rotation.

Two registration paths share one identity store:
- register_global_user: mobile actors (VOLUNTEER/VICTIM/DONATOR), no tenant
- register_tenant_user: portal actors (COORDINATOR; TENANT_ADMIN only via
  tenant onboarding), always tenant-bound
The DB CHECK constraint (ck_users_type_tenancy) backstops both paths.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.events.publisher import emit
from app.models import (
    GLOBAL_USER_TYPES,
    TENANT_USER_TYPES,
    RefreshToken,
    RoleAssignment,
    Tenant,
    User,
    UserType,
)
from app.schemas.auth_schema import (
    GlobalUserRegister,
    LoginRequest,
    TenantOnboard,
    TenantUserRegister,
    TokenPair,
)


def _user_registered_payload(user: User) -> dict:
    return {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "user_type": user.user_type.value,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "roles": user.roles,
        "is_active": user.is_active,
        "updated_at": (user.updated_at or datetime.now(timezone.utc)).isoformat(),
    }


def onboard_tenant(db: Session, data: TenantOnboard) -> Tenant:
    tenant = Tenant(name=data.name, slug=data.slug, description=data.description)
    db.add(tenant)
    db.flush()

    admin = User(
        tenant_id=tenant.id,
        user_type=UserType.TENANT_ADMIN,
        email=data.admin_email,
        password_hash=hash_password(data.admin_password),
        full_name=data.admin_full_name,
    )
    db.add(admin)
    db.flush()
    db.refresh(admin)

    emit(db, routing_key="iam.tenant.created", tenant_id=tenant.id,
         data={"tenant_id": str(tenant.id), "name": tenant.name, "slug": tenant.slug})
    emit(db, routing_key="iam.user.registered", tenant_id=tenant.id,
         data=_user_registered_payload(admin))
    db.commit()
    db.refresh(tenant)
    return tenant


def register_tenant_user(db: Session, tenant: Tenant, data: TenantUserRegister) -> User:
    """Web-portal path: user is bound to the tenant for its whole lifetime."""
    if data.user_type not in TENANT_USER_TYPES:
        raise ValueError(f"{data.user_type} cannot be registered under a tenant")
    user = User(
        tenant_id=tenant.id,
        user_type=data.user_type,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    db.flush()
    db.refresh(user)

    emit(db, routing_key="iam.user.registered", tenant_id=tenant.id,
         data=_user_registered_payload(user))
    db.commit()
    db.refresh(user)
    return user


def register_global_user(db: Session, data: GlobalUserRegister) -> User:
    """Mobile-app path: identity in the global pool, tenant_id stays NULL."""
    if data.user_type not in GLOBAL_USER_TYPES:
        raise ValueError(f"{data.user_type} must be registered under a tenant")
    user = User(
        tenant_id=None,
        user_type=data.user_type,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    db.flush()
    db.refresh(user)

    emit(db, routing_key="iam.user.registered", tenant_id=None,
         data=_user_registered_payload(user))
    db.commit()
    db.refresh(user)
    return user


def _issue_pair(db: Session, user: User, rotated_from=None) -> TokenPair:
    access = create_access_token(
        user_id=str(user.id),
        user_type=user.user_type.value,
        roles=user.roles,
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
    )
    raw_refresh, refresh_hash = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
            rotated_from=rotated_from,
        )
    )
    db.commit()
    return TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_TTL_MINUTES * 60,
    )


def login(db: Session, data: LoginRequest) -> TokenPair | None:
    """Portal login carries a tenant_slug; mobile login does not. The two
    populations are disjoint (partial unique indexes), so each lookup is
    unambiguous."""
    if data.tenant_slug is not None:
        tenant = db.scalars(select(Tenant).where(Tenant.slug == data.tenant_slug)).first()
        if tenant is None or tenant.status != "active":
            return None
        user_filter = User.tenant_id == tenant.id
    else:
        user_filter = User.tenant_id.is_(None)

    user = db.scalars(
        select(User)
        .where(user_filter, User.email == data.email)
        .options(selectinload(User.role_assignments))
    ).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(data.password, user.password_hash):
        return None
    return _issue_pair(db, user)


def refresh(db: Session, raw_token: str) -> TokenPair | None:
    token_hash = hash_refresh_token(raw_token)
    record = db.scalars(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()
    now = datetime.now(timezone.utc)
    if record is None or record.expires_at < now:
        return None
    if record.revoked_at is not None:
        # reuse of a rotated token => assume theft, revoke the whole chain
        db.query(RefreshToken).filter(RefreshToken.user_id == record.user_id).update(
            {"revoked_at": now}
        )
        db.commit()
        return None

    user = db.scalars(
        select(User)
        .where(User.id == record.user_id)
        .options(selectinload(User.role_assignments))
    ).first()
    if user is None or not user.is_active:
        return None

    record.revoked_at = now  # rotate: old token is spent
    return _issue_pair(db, user, rotated_from=record.id)



#New Additional Functions added by Kesh
####




# Database එකෙන් සේරම Tenants ලව අරන් එන Function එක
def get_all_tenants(db: Session):
    # 'Tenant' Table එකේ තියෙන සේරම rows ටික අරන් List එකක් විදිහට දෙනවා
    return db.scalars(select(Tenant)).all()