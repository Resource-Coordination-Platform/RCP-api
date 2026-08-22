import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.alert import AlertSeverity

# Admin ගෙන් එන Data ටික (Request)
class DisasterAlertCreate(BaseModel):
    title: str
    message: str
    severity: AlertSeverity

# Frontend එකට ආපහු යවන Data ටික (Response)
class DisasterAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    message: str
    severity: AlertSeverity
    created_by: uuid.UUID
    created_at: datetime