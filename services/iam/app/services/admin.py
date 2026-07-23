"""Super-admin domain logic: cross-tenant reads and platform lifecycle.

Unlike the tenant-scoped services, everything here operates across the whole
identity store. Access is gated at the router by the super_admin role; this
module assumes the caller is already authorized.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password
from app.events.publisher import emit
from app.models import Tenant, User, UserType
from app.schemas.admin_schema import SuperAdminCreate

_TENANT_TYPES = (UserType.TENANT_ADMIN, UserType.COORDINATOR)
_GLOBAL_TYPES = (UserType.VOLUNTEER, UserType.VICTIM, UserType.DONATOR)


def list_tenants(db: Session) -> list[dict]:
    """Every tenant with its user rollups, newest first."""
    total = func.count(User.id)
    admins = func.count(User.id).filter(User.user_type == UserType.TENANT_ADMIN)
    coords = func.count(User.id).filter(User.user_type == UserType.COORDINATOR)

    rows = db.execute(
        select(
            Tenant,
            total.label("user_count"),
            admins.label("admin_count"),
            coords.label("coordinator_count"),
        )
        .outerjoin(User, User.tenant_id == Tenant.id)
        .group_by(Tenant.id)
        .order_by(Tenant.created_at.desc())
    ).all()

    return [
        {
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "description": t.description,
            "status": t.status,
            "created_at": t.created_at,
            "user_count": user_count,
            "admin_count": admin_count,
            "coordinator_count": coordinator_count,
        }
        for t, user_count, admin_count, coordinator_count in rows
    ]


def get_tenant(db: Session, tenant_id: uuid.UUID) -> dict | None:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        return None
    counts = db.execute(
        select(
            func.count(User.id),
            func.count(User.id).filter(User.user_type == UserType.TENANT_ADMIN),
            func.count(User.id).filter(User.user_type == UserType.COORDINATOR),
        ).where(User.tenant_id == tenant_id)
    ).one()
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "description": tenant.description,
        "status": tenant.status,
        "created_at": tenant.created_at,
        "user_count": counts[0],
        "admin_count": counts[1],
        "coordinator_count": counts[2],
    }


def set_tenant_status(db: Session, tenant_id: uuid.UUID, status: str) -> Tenant | None:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        return None
    tenant.status = status
    emit(
        db,
        routing_key="iam.tenant.status_changed",
        tenant_id=tenant.id,
        data={"tenant_id": str(tenant.id), "status": status},
    )
    db.commit()
    db.refresh(tenant)
    return tenant


def _slug_by_tenant(db: Session) -> dict[uuid.UUID, str]:
    return {t.id: t.slug for t in db.scalars(select(Tenant)).all()}


def list_users(
    db: Session,
    *,
    tenant_id: uuid.UUID | None = None,
    user_type: UserType | None = None,
    status: str | None = None,
    q: str | None = None,
    scope: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Cross-tenant user directory.

    scope: "global" (tenant-less pool), "tenant" (portal users), or None (all).
    """
    stmt = select(User).options(selectinload(User.role_assignments))

    if tenant_id is not None:
        stmt = stmt.where(User.tenant_id == tenant_id)
    if scope == "global":
        stmt = stmt.where(User.tenant_id.is_(None))
    elif scope == "tenant":
        stmt = stmt.where(User.tenant_id.is_not(None))
    if user_type is not None:
        stmt = stmt.where(User.user_type == user_type)
    if status is not None:
        stmt = stmt.where(User.status == status)
    if q:
        pattern = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(User.email).like(pattern)
            | func.lower(User.full_name).like(pattern)
        )

    stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
    users = db.scalars(stmt).all()
    slugs = _slug_by_tenant(db)

    return [
        {
            "id": u.id,
            "tenant_id": u.tenant_id,
            "tenant_slug": slugs.get(u.tenant_id) if u.tenant_id else None,
            "user_type": u.user_type,
            "email": u.email,
            "full_name": u.full_name,
            "phone": u.phone,
            "status": u.status,
            "roles": u.roles,
            "created_at": u.created_at,
        }
        for u in users
    ]


def set_user_status(db: Session, user_id: uuid.UUID, status: str) -> User | None:
    user = db.scalars(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.role_assignments))
    ).first()
    if user is None:
        return None
    user.status = status
    db.commit()
    db.refresh(user)
    return user


def create_super_admin(db: Session, data: SuperAdminCreate) -> User | None:
    """Promote a new platform operator. Returns None on email collision."""
    if db.scalars(
        select(User).where(User.tenant_id.is_(None), User.email == data.email)
    ).first():
        return None
    user = User(
        tenant_id=None,
        user_type=UserType.SUPER_ADMIN,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    emit(
        db,
        routing_key="iam.user.registered",
        tenant_id=None,
        data={
            "user_id": str(user.id),
            "tenant_id": None,
            "user_type": user.user_type.value,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "roles": user.roles,
            "is_active": user.is_active,
            "updated_at": (user.updated_at or datetime.now(timezone.utc)).isoformat(),
        },
    )
    db.commit()
    db.refresh(user)
    return user


def platform_stats(db: Session) -> dict:
    tenant_counts = db.execute(
        select(Tenant.status, func.count(Tenant.id)).group_by(Tenant.status)
    ).all()
    tenants_by_status = {status: count for status, count in tenant_counts}
    total_tenants = sum(tenants_by_status.values())

    type_counts = db.execute(
        select(User.user_type, func.count(User.id)).group_by(User.user_type)
    ).all()
    by_type = {ut: count for ut, count in type_counts}
    total_users = sum(by_type.values())
    tenant_users = sum(by_type.get(t, 0) for t in _TENANT_TYPES)
    global_users = sum(by_type.get(t, 0) for t in _GLOBAL_TYPES)

    since = datetime.now(timezone.utc) - timedelta(days=30)
    tenants_30d = db.scalar(
        select(func.count(Tenant.id)).where(Tenant.created_at >= since)
    )
    users_30d = db.scalar(
        select(func.count(User.id)).where(User.created_at >= since)
    )

    return {
        "total_tenants": total_tenants,
        "active_tenants": tenants_by_status.get("active", 0),
        "suspended_tenants": tenants_by_status.get("suspended", 0),
        "total_users": total_users,
        "global_users": global_users,
        "tenant_users": tenant_users,
        "super_admins": by_type.get(UserType.SUPER_ADMIN, 0),
        "users_by_type": [
            {"user_type": ut.value, "count": count} for ut, count in by_type.items()
        ],
        "tenants_last_30d": tenants_30d or 0,
        "users_last_30d": users_30d or 0,
    }
