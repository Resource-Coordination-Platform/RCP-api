from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime

# common things
class SafeZoneBase(BaseModel):
    name: str
    lat: float
    lng: float
    type: str

# we just pass because no extra fields rather than inherited from class SafeZoneBase
class SafeZoneCreate(SafeZoneBase):
    pass

# data that send to frontend
class SafeZoneRead(SafeZoneBase):
    id: UUID
    tenant_id: UUID
    created_by: UUID
    created_at: datetime

    # this need for convert sql alchemy to pydantic
    model_config = ConfigDict(from_attributes=True)