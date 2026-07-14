"""Outbox writer: thin binding of rcp_common.outbox to this service's
Outbox model. The envelope format lives exactly once, in packages/common."""

import uuid
from typing import Any

from sqlalchemy.orm import Session
from rcp_common.outbox import emit as _emit

from app.core.config import settings
from app.models.outbox import Outbox


def emit(
    db: Session,
    *,
    routing_key: str,
    tenant_id: uuid.UUID | None,
    data: dict[str, Any],
    schema_version: int = 1,
    trace_id: str | None = None,
) -> None:
    _emit(
        db,
        outbox_model=Outbox,
        producer=settings.SERVICE_NAME,
        routing_key=routing_key,
        tenant_id=tenant_id,
        data=data,
        schema_version=schema_version,
        trace_id=trace_id,
    )
