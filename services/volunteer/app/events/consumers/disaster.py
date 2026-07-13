"""Consumer for disaster declarations — the matching trigger.

The declare API only persists the aggregate and emits
`volunteer.disaster.declared` through the outbox; THIS consumer runs the
actual matching fan-out. Consuming our own event keeps the HTTP path
fast and makes the pipeline uniform: any producer (e.g. logistics
declaring `logistics.disaster.declared`) triggers the exact same logic.

Reliability contract mirrors the iam consumer: quorum queue + DLX,
ack-after-commit, processed_events idempotency. run_matching itself is
also idempotent per (event, volunteer), so a crash between commit and
ack cannot double-notify.
"""

import json
import logging
import threading
import time
import uuid

import pika

from app.core.config import settings
from app.db.database import SessionLocal
from app.models import ProcessedEvent
from app.services.matching import run_matching

log = logging.getLogger("volunteer.disaster-consumer")

BINDINGS = ["volunteer.disaster.declared"]
RECONNECT_SLEEP_S = 2.0


def _handle(envelope: dict) -> None:
    event_id = uuid.UUID(envelope["event_id"])
    with SessionLocal() as db:
        if db.get(ProcessedEvent, event_id) is not None:
            return
        db.add(ProcessedEvent(event_id=event_id))
        # run_matching commits (mappings + notifications + processed marker
        # ride the same transaction as the event status flip)
        run_matching(db, uuid.UUID(envelope["data"]["event_id"]))
        # no-op if run_matching committed; persists the idempotency marker
        # on its skip/early-return paths
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
        settings.DISASTER_EVENTS_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-dead-letter-exchange": settings.DLX_EXCHANGE,
        },
    )
    channel.queue_declare(settings.DISASTER_EVENTS_DLQ, durable=True)
    channel.queue_bind(settings.DISASTER_EVENTS_DLQ, settings.DLX_EXCHANGE, routing_key="#")
    for binding in BINDINGS:
        channel.queue_bind(
            settings.DISASTER_EVENTS_QUEUE, settings.EVENTS_EXCHANGE, routing_key=binding
        )


def _consume_loop(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            connection = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
            channel = connection.channel()
            _declare_topology(channel)
            channel.basic_qos(prefetch_count=8)
            channel.basic_consume(settings.DISASTER_EVENTS_QUEUE, _on_message)
            log.info("consuming %s", settings.DISASTER_EVENTS_QUEUE)
            channel.start_consuming()
        except Exception:
            log.exception("consumer disconnected; retrying")
            time.sleep(RECONNECT_SLEEP_S)


def start_consumer() -> threading.Event:
    stop = threading.Event()
    threading.Thread(
        target=_consume_loop, args=(stop,), daemon=True, name="disaster-consumer"
    ).start()
    return stop
