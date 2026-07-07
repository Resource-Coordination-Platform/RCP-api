"""Tenant = one community-based organisation (CBO) hosting its own
private coordination hub. Maps to the Identity & Tenant Management service."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.resource import ResourceCategory
    from app.models.user import User


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # URL-safe identifier used to resolve the tenant from a subdomain
    # or the X-Tenant-Slug header (see middlewares/tenant_context.py)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    resource_categories: Mapped[list["ResourceCategory"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
