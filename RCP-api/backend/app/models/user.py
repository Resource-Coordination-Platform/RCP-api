"""User accounts with the RBAC role hierarchy required to protect
vulnerable community members' data."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.volunteer import VolunteerProfile


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"    # platform operator (cross-tenant)
    TENANT_ADMIN = "tenant_admin"  # CBO admin: manages categories, users
    COORDINATOR = "coordinator"    # verifies requests, dispatches volunteers
    VOLUNTEER = "volunteer"        # receives and completes tasks
    MEMBER = "member"              # public user: requests help / offers resources


class User(Base, TenantMixin, TimestampMixin):
    __tablename__ = "users"
    # the same email may exist in different tenants, but only once per tenant
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.MEMBER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    volunteer_profile: Mapped["VolunteerProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
