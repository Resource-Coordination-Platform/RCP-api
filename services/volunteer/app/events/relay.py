"""Outbox relay: drains unpublished outbox rows to RabbitMQ with
publisher confirms — same contract as services/iam/app/events/relay.py.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone

import pika
from sqlalchemy import select

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.outbox import Outbox

log = logging.getLogger("volunteer.outbox-relay")

BATCH_SIZE = 100
IDLE_SLEEP_S = 0.5
RECONNECT_SLEEP_S = 2.0


def _drain_once(channel) -> int:
    """Publish one batch. Returns number of rows published."""
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(Outbox)
                .where(Outbox.published_at.is_(None))
                .order_by(Outbox.id)
                .limit(BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            channel.basic_publish(
                exchange=settings.EVENTS_EXCHANGE,
                routing_key=row.routing_key,
                body=json.dumps(row.payload).encode(),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,  # persistent
                    message_id=str(row.event_id),
                ),
                mandatory=False,
            )
            # confirm_delivery() mode: basic_publish raises on broker nack,
            # so reaching this line means the broker has the message
            row.published_at = datetime.now(timezone.utc)
        db.commit()
        return len(rows)


def _relay_loop(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            connection = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
            channel = connection.channel()
            channel.exchange_declare(settings.EVENTS_EXCHANGE, "topic", durable=True)
            channel.confirm_delivery()
            log.info("outbox relay connected to broker")
            while not stop.is_set():
                if _drain_once(channel) == 0:
                    time.sleep(IDLE_SLEEP_S)
                    connection.process_data_events(0)  # heartbeat upkeep
        except Exception:
            log.exception("outbox relay disconnected; retrying")
            time.sleep(RECONNECT_SLEEP_S)


def start_relay() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=_relay_loop, args=(stop,), daemon=True, name="outbox-relay").start()
    return stop
