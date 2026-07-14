"""Consumer for iam.user.* events.

Replicates *global VOLUNTEER users only* into schema_volunteer as
VolunteerProfile rows (event-carried state replication) so the matching
engine never queries schema_iam. IAM owns identity (name, phone,
active); this service owns the operational half of the profile
(district, city, skills, availability), which the volunteer completes
from the mobile app after registering.

Reliability contract (same as logistics' iam consumer):
- quorum queue with DLX; manual ack only after the DB transaction commits
- idempotent via processed_events (redelivery is a no-op)
- out-of-order safe: identity upserts are guarded by source updated_at
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
from app.models import ProcessedEvent, VolunteerProfile

log = logging.getLogger("volunteer.iam-consumer")

BINDINGS = ["iam.user.*"]
RECONNECT_SLEEP_S = 2.0


def _already_processed(db: Session, event_id: uuid.UUID) -> bool:
    return db.get(ProcessedEvent, event_id) is not None


def _upsert_profile(db: Session, data: dict) -> None:
    if data.get("user_type") != "VOLUNTEER":
        return  # victims/donators/portal staff are not matchable actors here
    user_id = uuid.UUID(data["user_id"])
    profile = db.scalars(
        select(VolunteerProfile).where(VolunteerProfile.user_id == user_id)
    ).first()
    source_updated_at = datetime.fromisoformat(data["updated_at"])
    if profile is None:
        db.add(
            VolunteerProfile(
                user_id=user_id,
                full_name=data["full_name"],
                phone=data.get("phone"),
                is_active=data.get("is_active", True),
                available_status=False,  # opts in from the app once ready
                source_updated_at=source_updated_at,
            )
        )
    elif profile.source_updated_at is None or profile.source_updated_at <= source_updated_at:
        # Guarded by the *source* (IAM) timestamp, never the local
        # updated_at — that clock moves on every local profile edit and
        # would make legitimate identity updates look stale.
        # Only the replicated identity fields; never touch the
        # service-owned operational fields.
        profile.full_name = data["full_name"]
        profile.phone = data.get("phone")
        profile.is_active = data.get("is_active", True)
        profile.source_updated_at = source_updated_at
    # else: stale out-of-order event — ignore


def _deactivate_profile(db: Session, data: dict) -> None:
    profile = db.scalars(
        select(VolunteerProfile).where(
            VolunteerProfile.user_id == uuid.UUID(data["user_id"])
        )
    ).first()
    if profile is not None:
        profile.is_active = False
        profile.available_status = False


def _handle(envelope: dict) -> None:
    event_id = uuid.UUID(envelope["event_id"])
    event_type = envelope["event_type"]
    data = envelope["data"]

    with SessionLocal() as db:
        if _already_processed(db, event_id):
            return
        if event_type in ("iam.user.registered", "iam.user.updated"):
            _upsert_profile(db, data)
        elif event_type == "iam.user.deactivated":
            _deactivate_profile(db, data)
        db.add(ProcessedEvent(event_id=event_id))
        db.commit()


def _on_message(channel, method, properties, body: bytes) -> None:
    try:
        _handle(json.loads(body))
        channel.basic_ack(method.delivery_tag)
    except Exception:
        log.exception("failed to process event; dead-lettering")
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
