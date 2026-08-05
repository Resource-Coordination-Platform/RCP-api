import uuid
import enum
from sqlalchemy import String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# Severity එකට Enum එකක් හදාගමු (වැරදි අගයන් වැටෙන එක නවත්වන්න)
class AlertSeverity(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class DisasterAlert(Base, TimestampMixin):
    __tablename__ = "disaster_alerts"
    
    # මේක අයිති Logistics Schema එකට
    __table_args__ = {"schema": "schema_logistics"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # මේ Alert එක අදාළ වෙන්නේ මොන Tenant (කඳවුරටද) කියන එක
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # HIGH, MEDIUM, LOW
    severity: Mapped[AlertSeverity] = mapped_column(
        SQLEnum(AlertSeverity, name="alert_severity", create_type=False), 
        nullable=False
    )
    
    # මේක හැදුව Admin ගේ ID එක (මෙතන ForeignKey ගහන්නේ නෑ, මොකද User ඉන්නේ IAM Schema එකේ නිසා)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)