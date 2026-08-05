import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserType


class TenantOnboard(BaseModel):
    """Creates a tenant plus its first tenant_admin user in one step."""

    name: str
    slug: str = Field(pattern=r"^[a-z0-9-]{3,80}$")
    description: str | None = None
    admin_email: EmailStr
    admin_password: str = Field(min_length=10)
    admin_full_name: str


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    created_at: datetime


class GlobalUserRegister(BaseModel):
    """Mobile-app signup: the global (tenant-less) actor pool."""

    email: EmailStr
    password: str = Field(min_length=10)
    full_name: str
    phone: str | None = None
    user_type: UserType = Field(
        description="Mobile actors only: VOLUNTEER, VICTIM "
    )
    latitude: float | None = None
    longitude: float | None = None


class TenantUserRegister(BaseModel):
    """Web-portal signup under a tenant. TENANT_ADMIN is only ever created
    through tenant onboarding, so self-registration is COORDINATOR-only."""

    email: EmailStr
    password: str = Field(min_length=10)
    full_name: str
    phone: str | None = None
    user_type: UserType = Field(
        default=UserType.COORDINATOR, description="Portal actors: COORDINATOR"
    )


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None  # None == global (mobile app) user
    user_type: UserType
    email: EmailStr
    full_name: str
    phone: str | None
    status: str
    roles: list[str]
    created_at: datetime
    latitude: float | None = None
    longitude: float | None = None




class LoginRequest(BaseModel):
    """tenant_slug present == web-portal login (tenant-bound users);
    absent == mobile-app login (global pool)."""

    tenant_slug: str | None = None
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str

 #added by kesh.this ude for get tenants/locations endpoint
class TenantLocationRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    latitude: float
    longitude: float

    class Config:
        from_attributes = True