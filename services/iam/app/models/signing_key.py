from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SigningKey(Base):
    """Registry of JWT signing keys (public halves only). The private key
    never touches the database — private_ref points at the secrets-manager
    entry (or local file path in dev)."""

    __tablename__ = "signing_keys"

    kid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    public_pem: Mapped[str] = mapped_column(Text, nullable=False)
    private_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
