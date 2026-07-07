"""Auth domain logic: onboarding, registration, login, refresh rotation."""

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
from app.models import RefreshToken, RoleAssignment, Tenant, User
from app.schemas.auth_schema import LoginRequest, TenantOnboard, TokenPair, UserRegister


def _user_registered_payload(user: User) -> dict:
    return {
        "user_id": str(user.id),
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
        email=data.admin_email,
        password_hash=hash_password(data.admin_password),
        full_name=data.admin_full_name,
    )
    db.add(admin)
    db.flush()
    db.add(RoleAssignment(tenant_id=tenant.id, user_id=admin.id, role="tenant_admin"))
    db.flush()
    db.refresh(admin)

    emit(db, routing_key="iam.tenant.created", tenant_id=tenant.id,
         data={"tenant_id": str(tenant.id), "name": tenant.name, "slug": tenant.slug})
    emit(db, routing_key="iam.user.registered", tenant_id=tenant.id,
         data=_user_registered_payload(admin))
    db.commit()
    db.refresh(tenant)
    return tenant


def register_user(db: Session, tenant: Tenant, data: UserRegister) -> User:
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    db.flush()
    db.add(RoleAssignment(tenant_id=tenant.id, user_id=user.id, role=data.role))
    db.flush()
    db.refresh(user)

    emit(db, routing_key="iam.user.registered", tenant_id=tenant.id,
         data=_user_registered_payload(user))
    db.commit()
    db.refresh(user)
    return user


def _issue_pair(db: Session, user: User, rotated_from=None) -> TokenPair:
    access = create_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id), roles=user.roles
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
    tenant = db.scalars(select(Tenant).where(Tenant.slug == data.tenant_slug)).first()
    if tenant is None or tenant.status != "active":
        return None
    user = db.scalars(
        select(User)
        .where(User.tenant_id == tenant.id, User.email == data.email)
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
