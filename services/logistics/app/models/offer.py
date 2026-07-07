import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import SCHEMA, Base, TenantMixin, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.resource import ResourceCategory


class OfferStatus(str, enum.Enum):
    PLEDGED = "pledged"
    ACCEPTED = "accepted"
    RECEIVED = "received"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class ResourceOffer(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "resource_offers"

    # logical reference to schema_iam.users — NO cross-schema FK
    donor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    donor_name: Mapped[str | None] = mapped_column(String(200))
    donor_phone: Mapped[str | None] = mapped_column(String(30))

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.resource_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[OfferStatus] = mapped_column(
        Enum(OfferStatus, name="offer_status", inherit_schema=True),
        default=OfferStatus.PLEDGED,
        nullable=False,
        index=True,
    )
    extra_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.inventory_items.id", ondelete="SET NULL"),
    )

    category: Mapped["ResourceCategory"] = relationship()
