from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.base import Base

class SafeZone(Base):
    __tablename__ = "safe_zones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False) #  (Latitude)
    lng = Column(Float, nullable=False) # (Longitude)
    type = Column(String, nullable=False) # 'camp' or 'medical'
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())