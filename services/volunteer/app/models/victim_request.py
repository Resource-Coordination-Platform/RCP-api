import uuid
from sqlalchemy import String, Text, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

class VictimRequest(Base, TimestampMixin):
    __tablename__ = "victim_requests"
    # මේ ටේබල් එක හදන්නේ volunteer ස්කීමා එක ඇතුළේ
    __table_args__ = {"schema": "schema_volunteer"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # ලොග් වෙලා ඉන්න Victim ගේ ID එක
    victim_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True) #we cant make a foreign key here because the victim is in a different service (iam) and we don't have cross-service foreign keys
    
    disaster_type: Mapped[str] = mapped_column(String(50), nullable=False)
    needs: Mapped[list[str]] = mapped_column(JSONB, nullable=False) # JSON Array එකක් විදිහට සේව් කරන්නේ
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # PENDING, APPROVED, REJECTED
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    
    # Admin Accept කරාම මේක Disaster Event එකකට ලින්ක් වෙනවා (උඹ කියපු Foreign Key එක!)
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("schema_volunteer.disaster_events.id"), nullable=True)