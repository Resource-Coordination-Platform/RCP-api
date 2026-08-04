"""Schemas for the super-admin (platform operator) console.

These back the /api/admin surface: cross-tenant visibility and lifecycle
control that no tenant-scoped role is allowed to exercise.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserType


class TenantSummary(BaseModel):
    """A tenant plus the operator-relevant rollups computed in one query."""

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    status: str
    created_at: datetime
    user_count: int
    admin_count: int
    coordinator_count: int


class TenantStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(active|suspended)$")


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    tenant_slug: str | None = None
    user_type: UserType
    email: EmailStr
    full_name: str
    phone: str | None
    status: str
    roles: list[str]
    created_at: datetime


class UserStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(active|disabled)$")


class SuperAdminCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)
    full_name: str
    phone: str | None = None


class UserTypeCount(BaseModel):
    user_type: str
    count: int


class PlatformStats(BaseModel):
    total_tenants: int
    active_tenants: int
    suspended_tenants: int
    total_users: int
    global_users: int
    tenant_users: int
    super_admins: int
    users_by_type: list[UserTypeCount]
    tenants_last_30d: int
    users_last_30d: int


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=10)
