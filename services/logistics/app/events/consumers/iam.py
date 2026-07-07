"""Consumer for iam.user.* / iam.tenant.* events.

Maintains schema_logistics.user_replicas (event-carried state replication)
so this service never queries schema_iam at runtime.

Reliability contract:
- quorum queue with DLX; manual ack only after the DB transaction commits
- idempotent via processed_events (redelivery is a no-op)
- out-of-order safe: upserts are guarded by source_updated_at
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime

import pika
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models import ProcessedEvent, UserReplica

log = logging.getLogger("logistics.iam-consumer")

BINDINGS = ["iam.user.*", "iam.tenant.*"]
RECONNECT_SLEEP_S = 2.0


def _already_processed(db: Session, event_id: uuid.UUID) -> bool:
    return db.get(ProcessedEvent, event_id) is not None


def _upsert_replica(db: Session, tenant_id: uuid.UUID, data: dict) -> None:
    source_updated_at = datetime.fromisoformat(data["updated_at"])
    replica = db.get(UserReplica, uuid.UUID(data["user_id"]))
    if replica is None:
        db.add(
            UserReplica(
                user_id=uuid.UUID(data["user_id"]),
                tenant_id=tenant_id,
                full_name=data["full_name"],
                phone=data.get("phone"),
                roles=data.get("roles", []),
                is_active=data.get("is_active", True),
                source_updated_at=source_updated_at,
            )
        )
    elif replica.source_updated_at <= source_updated_at:
        replica.full_name = data["full_name"]
        replica.phone = data.get("phone")
        replica.roles = data.get("roles", [])
        replica.is_active = data.get("is_active", True)
        replica.source_updated_at = source_updated_at
    # else: stale out-of-order event — ignore


def _deactivate_replica(db: Session, data: dict) -> None:
    replica = db.get(UserReplica, uuid.UUID(data["user_id"]))
    if replica is not None:
        replica.is_active = False


def _handle(envelope: dict) -> None:
    event_id = uuid.UUID(envelope["event_id"])
    event_type = envelope["event_type"]
    tenant_id = uuid.UUID(envelope["tenant_id"])
    data = envelope["data"]

    with SessionLocal() as db:
        if _already_processed(db, event_id):
            return
        if event_type in ("iam.user.registered", "iam.user.updated"):
            _upsert_replica(db, tenant_id, data)
        elif event_type == "iam.user.deactivated":
            _deactivate_replica(db, data)
        # iam.tenant.* currently informational for this service
        db.add(ProcessedEvent(event_id=event_id))
        db.commit()


def _on_message(channel, method, properties, body: bytes) -> None:
    try:
        _handle(json.loads(body))
        channel.basic_ack(method.delivery_tag)
    except Exception:
        log.exception("failed to process event; dead-lettering")
        # nack without requeue routes to the DLQ via the queue's DLX
        channel.basic_nack(method.delivery_tag, requeue=False)


def _declare_topology(channel) -> None:
    channel.exchange_declare(settings.EVENTS_EXCHANGE, "topic", durable=True)
    channel.exchange_declare(settings.DLX_EXCHANGE, "topic", durable=True)
    channel.queue_declare(
        settings.IAM_EVENTS_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-dead-letter-exchange": settings.DLX_EXCHANGE,
        },
    )
    channel.queue_declare(settings.IAM_EVENTS_DLQ, durable=True)
    channel.queue_bind(settings.IAM_EVENTS_DLQ, settings.DLX_EXCHANGE, routing_key="#")
    for binding in BINDINGS:
        channel.queue_bind(settings.IAM_EVENTS_QUEUE, settings.EVENTS_EXCHANGE, routing_key=binding)


def _consume_loop(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            connection = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
            channel = connection.channel()
            _declare_topology(channel)
            channel.basic_qos(prefetch_count=32)
            channel.basic_consume(settings.IAM_EVENTS_QUEUE, _on_message)
            log.info("consuming %s", settings.IAM_EVENTS_QUEUE)
            channel.start_consuming()
        except Exception:
            log.exception("consumer disconnected; retrying")
            time.sleep(RECONNECT_SLEEP_S)


def start_consumer() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=_consume_loop, args=(stop,), daemon=True, name="iam-consumer").start()
    return stop
