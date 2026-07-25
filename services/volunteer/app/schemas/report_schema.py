# volunteer/app/schemas/report_schema.py
import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class VolunteerReportCreate(BaseModel):
    category: str
    severity: str
    district: str
    city: str
    description: Optional[str] = None
    image_url: Optional[str] = None

class VolunteerReportRead(BaseModel):
    id: uuid.UUID
    volunteer_id: uuid.UUID
    category: str
    severity: str
    district: str
    city: str
    description: Optional[str]
    image_url: Optional[str]
    status: str
    created_at: datetime

    class Config:
        orm_mode = True