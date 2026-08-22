import uuid
from datetime import datetime
from pydantic import BaseModel

# App එකෙන් Data එද්දී බලාපොරොත්තු වෙන ෆෝමැට් එක
class VictimRequestCreate(BaseModel):
    disaster_type: str
    needs: list[str]
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None

# Admin ට Data යවද්දී බලාපොරොත්තු වෙන ෆෝමැට් එක
class VictimRequestRead(BaseModel):
    id: uuid.UUID
    victim_id: uuid.UUID | None
    disaster_type: str
    needs: list[str]
    description: str | None
    latitude: float | None
    longitude: float | None
    status: str
    event_id: uuid.UUID | None
    created_at: datetime

    class Config:
        from_attributes = True