"""Resource offers: community members pledging donations through the
public "Offer Resources" portal. Accepted offers become inventory."""

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.resource import InventoryItem, ResourceCategory
    from app.models.user import User


class OfferStatus(str, enum.Enum):
    PLEDGED = "pledged"    # submitted, awaiting coordinator review
    ACCEPTED = "accepted"  # coordinator confirmed, awaiting hand-over
    RECEIVED = "received"  # goods received and added to inventory
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class ResourceOffer(Base, TenantMixin, TimestampMixin):
    __tablename__ = "resource_offers"

    donor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    donor_name: Mapped[str | None] = mapped_column(String(200))
    donor_phone: Mapped[str | None] = mapped_column(String(30))

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resource_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[OfferStatus] = mapped_column(
        Enum(OfferStatus, name="offer_status"),
        default=OfferStatus.PLEDGED,
        nullable=False,
        index=True,
    )
    extra_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # set when the offer is received and converted into stock
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="SET NULL")
    )

    donor: Mapped["User | None"] = relationship()
    category: Mapped["ResourceCategory"] = relationship()
    inventory_item: Mapped["InventoryItem | None"] = relationship()
