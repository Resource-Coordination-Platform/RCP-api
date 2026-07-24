"""Event-carried replica of IAM users (read-path data only).

Maintained by app/events/consumers/iam.py from iam.user.* events.
The source of truth is schema_iam.users — this table exists so rendering
"assigned to Nimal Perera" never requires a runtime call to IAM.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserReplica(Base):
    __tablename__ = "user_replicas"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    # Not TenantMixin: global actors (VOLUNTEER/VICTIM/DONATOR) have no
    # tenant, and they still need a replica so dispatch can render their
    # name. NULL here means "global user", never "all tenants".
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # timestamp from the IAM event; guards against out-of-order updates
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
