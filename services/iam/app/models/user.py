"""Identity model with two disjoint actor populations.

Global users (mobile app: VOLUNTEER / VICTIM / DONATOR) have no tenant —
they are a platform-wide pool that any tenant may draw on during a
disaster. Tenant-bound users (web portal: TENANT_ADMIN / COORDINATOR)
must belong to exactly one tenant. The pairing of user_type and
tenant_id is enforced by a CHECK constraint, not application discipline.
"""

import enum
import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import SCHEMA, Base, TimestampMixin


class UserType(str, enum.Enum):
    # Platform operator (super admin console) — tenant_id must be NULL
    SUPER_ADMIN = "SUPER_ADMIN"
    # Global pool (mobile app) — tenant_id must be NULL
    VOLUNTEER = "VOLUNTEER"
    VICTIM = "VICTIM"
    DONATOR = "DONATOR"
    # Tenant-bound (web portal) — tenant_id must be set
    TENANT_ADMIN = "TENANT_ADMIN"
    COORDINATOR = "COORDINATOR"

    @property
    def is_global(self) -> bool:
        return self in GLOBAL_USER_TYPES


# SUPER_ADMIN is a platform-wide operator: like the mobile pool it carries no
# tenant, but it is never self-registerable — it exists only through bootstrap
# or promotion by an existing super admin. Kept out of GLOBAL_USER_TYPES so the
# mobile registration path can never mint one.
GLOBAL_USER_TYPES = frozenset({UserType.VOLUNTEER, UserType.VICTIM, UserType.DONATOR})
TENANT_USER_TYPES = frozenset({UserType.TENANT_ADMIN, UserType.COORDINATOR})
PLATFORM_USER_TYPES = frozenset({UserType.SUPER_ADMIN})


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        # tenant-bound users: unique per tenant (NULLs never collide here)
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        # global users: tenant_id IS NULL rows escape the constraint above,
        # so the global pool needs its own partial unique index
        Index(
            "uq_users_global_email",
            "email",
            unique=True,
            postgresql_where="tenant_id IS NULL",
        ),
        # user_type and tenant_id must agree: portal actors are tenant-bound,
        # mobile actors are global. This is the decoupling invariant.
        CheckConstraint(
            "(user_type IN ('TENANT_ADMIN', 'COORDINATOR')) = (tenant_id IS NOT NULL)",
            name="ck_users_type_tenancy",
        ),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.tenants.id", ondelete="CASCADE"),
        nullable=True,  # NULL == global (mobile app) user
        index=True,
    )
    user_type: Mapped[UserType] = mapped_column(
        Enum(UserType, name="user_type", inherit_schema=True, native_enum=True),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    # active | disabled
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    role_assignments: Mapped[list["RoleAssignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_global(self) -> bool:
        return self.tenant_id is None

    @property
    def roles(self) -> list[str]:
        """Effective roles: the user_type is always an implicit role; extra
        tenant-scoped grants (e.g. a coordinator who is also tenant_admin)
        come from role_assignments."""
        implicit = self.user_type.value.lower()
        granted = [ra.role for ra in self.role_assignments]
        return [implicit, *(r for r in granted if r != implicit)]

    @property
    def is_active(self) -> bool:
        return self.status == "active"


class RoleAssignment(Base):
    __tablename__ = "role_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_role_assignments_user_role"),
    )

    # NULL for grants on global users (e.g. a vetted volunteer given
    # "team_lead"); set for tenant-scoped grants
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # super_admin | tenant_admin | coordinator | volunteer | victim | donator | team_lead
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    user: Mapped[User] = relationship(back_populates="role_assignments")
