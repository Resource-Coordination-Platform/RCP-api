import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)
    full_name: str
    phone: str | None = None
    # public signup may only request these two
    role: str = Field(default="member", pattern="^(member|volunteer)$")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: str | None
    status: str
    roles: list[str]
    created_at: datetime


class LoginRequest(BaseModel):
    tenant_slug: str
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str
