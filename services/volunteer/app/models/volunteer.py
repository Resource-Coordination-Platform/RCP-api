"""Volunteer read/operational profile.

Identity (email, password, name) is owned by IAM; this table is created
from `iam.user.registered` events (event-carried state replication) and
enriched by the volunteer through the mobile app (district, city,
skills, availability). It is the table the matching engine queries —
no cross-service call sits on the hot path.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class VolunteerProfile(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "volunteer_profiles"
    __table_args__ = (
        # the matching engine's exact access path:
        # WHERE available_status AND base_district IN (...) AND skills ? :skill
        Index(
            "ix_volunteer_profiles_matching",
            "base_district",
            "available_status",
        ),
        Index(
            "ix_volunteer_profiles_skills",
            "skills",
            postgresql_using="gin",
        ),
    )

    # logical reference to schema_iam.users (global user) — NO cross-schema FK
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False
    )

    # replicated identity fields (source of truth: IAM events)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # IAM's timestamp for the identity fields above; guards replica upserts
    # against out-of-order delivery. Never compare against local updated_at —
    # that clock moves on every local profile edit.
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # profile fields owned by THIS service (set via the mobile app)
    base_district: Mapped[str | None] = mapped_column(String(40), index=True)
    city: Mapped[str | None] = mapped_column(String(120))
    available_status: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # flat list of skill slugs, e.g. ["boat_driver", "first_aid"]
    skills: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    @property
    def is_matchable(self) -> bool:
        return self.is_active and self.available_status and self.base_district is not None
