"""Analytics projection consumer.

Consumes logistics domain events and maintains analytics-owned read models in
schema_analytics so reporting no longer reads the logistics database directly.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime

from app.core.config import settings
from app.db.database import SessionLocal
from app.models import CategoryProjection, InventoryProjection, ProcessedEvent, RequestProjection

log = logging.getLogger("analytics.consumer")

BINDINGS = [
    "logistics.request.*",
    "logistics.inventory.*",
    "logistics.resource-category.*",
]
RECONNECT_SLEEP_S = 2.0


def _is_stale(row_updated_at, incoming_updated_at) -> bool:
    """Out-of-order guard: never let an older event overwrite a newer
    projection. Events without a timestamp are applied unconditionally."""
    return (
        row_updated_at is not None
        and incoming_updated_at is not None
        and incoming_updated_at < row_updated_at
    )


def _upsert_category(db, data: dict, tenant_id: uuid.UUID) -> None:
    row = db.get(CategoryProjection, uuid.UUID(data["category_id"]))
    if row is not None and _is_stale(row.updated_at, _parse_dt(data.get("updated_at"))):
        return
    if row is None:
        db.add(
            CategoryProjection(
                category_id=uuid.UUID(data["category_id"]),
                tenant_id=tenant_id,
                name=data["name"],
                description=data.get("description"),
                unit=data.get("unit", "unit"),
                is_active=bool(data.get("is_active", True)),
                updated_at=_parse_dt(data.get("updated_at")),
            )
        )
        return
    row.name = data["name"]
    row.description = data.get("description")
    row.unit = data.get("unit", "unit")
    row.is_active = bool(data.get("is_active", True))
    row.updated_at = _parse_dt(data.get("updated_at"))


def _upsert_inventory(db, data: dict, tenant_id: uuid.UUID) -> None:
    item_id = uuid.UUID(data["item_id"])
    row = db.get(InventoryProjection, item_id)
    if row is not None and _is_stale(row.updated_at, _parse_dt(data.get("updated_at"))):
        return
    payload = dict(
        item_id=item_id,
        tenant_id=tenant_id,
        category_id=uuid.UUID(data["category_id"]),
        name=data["name"],
        quantity_total=int(data.get("quantity_total", 0)),
        quantity_reserved=int(data.get("quantity_reserved", 0)),
        quantity_available=int(data.get("quantity_available", 0)),
        status=data.get("status", "available"),
        updated_at=_parse_dt(data.get("updated_at")),
    )
    if row is None:
        db.add(InventoryProjection(**payload))
        return
    for key, value in payload.items():
        setattr(row, key, value)


def _upsert_request(db, data: dict, tenant_id: uuid.UUID) -> None:
    request_id = uuid.UUID(data["request_id"])
    row = db.get(RequestProjection, request_id)
    if row is not None and _is_stale(row.updated_at, _parse_dt(data.get("updated_at"))):
        return
    payload = dict(
        request_id=request_id,
        tenant_id=tenant_id,
        category_id=uuid.UUID(data["category_id"]),
        quantity_needed=int(data.get("quantity_needed", 0)),
        status=data.get("status", "pending"),
        urgency=data.get("urgency", "medium"),
        updated_at=_parse_dt(data.get("updated_at")),
    )
    if row is None:
        db.add(RequestProjection(**payload))
        return
    for key, value in payload.items():
        setattr(row, key, value)


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _handle(envelope: dict) -> None:
    event_id = uuid.UUID(envelope["event_id"])
    event_type = envelope["event_type"]
    tenant_id = uuid.UUID(envelope["tenant_id"])
    data = envelope["data"]

    with SessionLocal() as db:
        if db.get(ProcessedEvent, event_id) is not None:
            return

        if event_type in (
            "logistics.resource-category.created",
            "logistics.resource-category.updated",
        ):
            _upsert_category(db, data, tenant_id)
        elif event_type == "logistics.inventory.item-updated":
            _upsert_inventory(db, data, tenant_id)
        elif event_type == "logistics.request.submitted":
            _upsert_request(db, data, tenant_id)
        elif event_type == "logistics.request.status-changed":
            _upsert_request(db, data, tenant_id)

        db.add(ProcessedEvent(event_id=event_id, event_type=event_type))
        db.commit()


def _declare_topology(channel) -> None:
    channel.exchange_declare(settings.EVENTS_EXCHANGE, "topic", durable=True)
    channel.exchange_declare(settings.DLX_EXCHANGE, "topic", durable=True)
    channel.queue_declare(
        "analytics.projections.q",
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-dead-letter-exchange": settings.DLX_EXCHANGE,
        },
    )
    channel.queue_declare("dlq.analytics.projections", durable=True)
    channel.queue_bind("dlq.analytics.projections", settings.DLX_EXCHANGE, routing_key="#")
    for binding in BINDINGS:
        channel.queue_bind("analytics.projections.q", settings.EVENTS_EXCHANGE, routing_key=binding)


def _on_message(channel, method, properties, body: bytes) -> None:
    try:
        _handle(json.loads(body))
        channel.basic_ack(method.delivery_tag)
    except Exception:
        log.exception("failed to process analytics event; dead-lettering")
        channel.basic_nack(method.delivery_tag, requeue=False)


def _consume_loop(stop: threading.Event) -> None:
    try:
        import pika
    except Exception:
        log.warning("pika is not installed; analytics consumer disabled")
        stop.wait()
        return
    while not stop.is_set():
        try:
            connection = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
            channel = connection.channel()
            _declare_topology(channel)
            channel.basic_qos(prefetch_count=32)
            channel.basic_consume("analytics.projections.q", _on_message)
            log.info("consuming analytics.projections.q")
            channel.start_consuming()
        except Exception:
            log.exception("analytics consumer disconnected; retrying")
            time.sleep(RECONNECT_SLEEP_S)


def start_consumer() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=_consume_loop, args=(stop,), daemon=True, name="analytics-consumer").start()
    return stop