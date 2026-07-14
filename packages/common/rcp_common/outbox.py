"""Shared outbox writer: the single definition of the event envelope.

Call emit() inside the same Session/transaction as the state change; each
service's relay worker does the actual AMQP publish. Services bind their
own Outbox model and service name once in app/events/publisher.py — the
envelope format itself must never be copied per service (the copies had
already drifted on tenant_id=None handling before this was extracted).
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

__all__ = ["build_envelope", "emit"]


def build_envelope(
    *,
    routing_key: str,
    producer: str,
    tenant_id: uuid.UUID | None,
    data: dict[str, Any],
    schema_version: int = 1,
    trace_id: str | None = None,
) -> tuple[uuid.UUID, dict[str, Any]]:
    event_id = uuid.uuid4()
    envelope = {
        "event_id": str(event_id),
        "event_type": routing_key,
        "schema_version": schema_version,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        # None == event about a global (tenant-less) actor
        "tenant_id": str(tenant_id) if tenant_id else None,
        "producer": producer,
        "trace_id": trace_id,
        "data": data,
    }
    return event_id, envelope


def emit(
    db: Session,
    *,
    outbox_model: type,
    producer: str,
    routing_key: str,
    tenant_id: uuid.UUID | None,
    data: dict[str, Any],
    schema_version: int = 1,
    trace_id: str | None = None,
) -> None:
    event_id, envelope = build_envelope(
        routing_key=routing_key,
        producer=producer,
        tenant_id=tenant_id,
        data=data,
        schema_version=schema_version,
        trace_id=trace_id,
    )
    db.add(outbox_model(event_id=event_id, routing_key=routing_key, payload=envelope))
