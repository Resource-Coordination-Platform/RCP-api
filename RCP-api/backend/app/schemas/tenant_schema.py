import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class TenantCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    address: str | None = None


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    contact_email: str | None
    is_active: bool
    created_at: datetime
