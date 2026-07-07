"""Outbox writer — see services/iam/app/events/publisher.py for the pattern.
(Kept per-service until packages/py-shared is published as a wheel.)"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.outbox import Outbox


def emit(
    db: Session,
    *,
    routing_key: str,
    tenant_id: uuid.UUID,
    data: dict[str, Any],
    schema_version: int = 1,
    trace_id: str | None = None,
) -> None:
    event_id = uuid.uuid4()
    envelope = {
        "event_id": str(event_id),
        "event_type": routing_key,
        "schema_version": schema_version,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": str(tenant_id),
        "producer": settings.SERVICE_NAME,
        "trace_id": trace_id,
        "data": data,
    }
    db.add(Outbox(event_id=event_id, routing_key=routing_key, payload=envelope))
