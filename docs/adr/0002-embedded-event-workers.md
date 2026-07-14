# ADR 0002 — Outbox relays and event consumers run inside the API process

Status: **Accepted** (2026-07-14)

## Context

Each Python service starts its outbox relay and RabbitMQ consumers as daemon
threads from the FastAPI lifespan hook, inside the same uvicorn process that
serves HTTP. The alternative is separate worker containers per service.

## Decision

Keep the workers embedded at the current scale. One container per service
keeps the local compose file, CI, and deployment story simple, and the
correctness guarantees do not depend on process placement:

- **Crash / abrupt shutdown is safe by design.** Consumers ack only after the
  DB transaction commits, and every consumer is idempotent via
  `processed_events` — a message in flight during shutdown is simply
  redelivered. The relay marks outbox rows published only after broker
  confirms, so at-least-once holds.
- **Horizontal scaling is safe.** Replicated relays coordinate through
  `FOR UPDATE SKIP LOCKED`; replicated consumers share quorum queues.

## Known trade-offs (accepted, not overlooked)

1. **Readiness does not cover the broker.** `/readiness` checks the database
   only; a service that lost its RabbitMQ connection still reports ready.
   The relay/consumer loops reconnect with backoff and log every failure, and
   queue depth + connection alarms are the RabbitMQ-side signal
   (see infra/compose/docker-compose.monitoring.yml).
2. **Shutdown is abrupt.** `stop.set()` is not observed by a blocking
   `start_consuming()`; daemon threads die with the process. Safe per the
   ack-after-commit contract above, but not graceful.
3. **Scaling is coupled.** Scaling API replicas also scales consumers. At the
   point where HTTP load and event load need independent scaling, the workers
   move to a separate entrypoint.

## Migration path (when the trade-offs stop being acceptable)

The workers already live behind `start_relay()` / `start_consumer()`
functions with no dependency on FastAPI. Extraction is mechanical: add a
`worker.py` entrypoint that starts the same functions under a signal handler,
run it as a second container from the same image, and drop the lifespan
hooks. No code inside the relays or consumers changes.
