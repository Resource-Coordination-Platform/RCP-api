# volunteer/app/models/report.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base

class VolunteerReport(Base):
    __tablename__ = "volunteer_reports"
    __table_args__ = {"schema": "schema_volunteer"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    volunteer_id = Column(UUID(as_uuid=True), ForeignKey("schema_volunteer.volunteer_profiles.id"), nullable=False)
    category = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    district = Column(String, nullable=False)
    city = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True) # Supabase bucket එකෙන් එන URL එක මෙතන සේව් වෙනවා
    status = Column(String, default="PENDING") # PENDING, VERIFIED, REJECTED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationship එක හදනවා volunteer profile එකත් එක්ක
    volunteer = relationship("VolunteerProfile")