import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import SCHEMA, Base, TenantMixin, TimestampMixin, UUIDPkMixin

# Payment එකේ තත්ත්වයන් (Status)
class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

class PaymentDonation(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "payment_donations"

    # සල්ලි ගෙවන Volunteer ගේ User ID එක (IAM එකෙන් එන)
    donor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # මොන බඩුව ගන්නද සල්ලි දුන්නේ කියලා දැනගන්න (Resource Category එකට ලින්ක් වෙනවා)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.resource_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ගෙවන ගාණ සහ මුදල් වර්ගය
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="LKR", nullable=False)
    
    # PayHere එකෙන් දෙන Unique Order ID එක
    payhere_order_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # ගෙවීම සාර්ථකද නැද්ද කියලා
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", inherit_schema=True),
        default=PaymentStatus.PENDING,
        nullable=False,
    )
    
    # මේ සල්ලි වලින් බඩු කීයක් අරන් දෙනවද කියලා
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)