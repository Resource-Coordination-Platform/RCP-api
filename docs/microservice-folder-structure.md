# Microservice Folder Structure for Resource Coordination Platform

This repository follows a full microservice split. The legacy
`RCP-api/backend` prototype has been deleted (see
[migration-summary.md](migration-summary.md)); the service boundaries are:

- `gateway/` — API gateway: routing, auth forwarding, rate limiting, CORS.
- `services/iam` — authentication, tenants, users, RBAC, JWT/JWKS.
- `services/logistics` — requests, inventory, offers, volunteers, dispatch.
- `services/analytics` — read-only reporting and dashboard aggregates.
- `services/rto` — WebSockets, notifications, and offline sync.
- `packages/contracts` — AsyncAPI and event schemas.
- `packages/common` — shared Python utilities (logging, middleware, auth, config).
- `packages/clients` — HTTP clients for service-to-service calls.
- `infra/` — compose, docker conventions, monitoring, terraform.

## Top-level layout

```text
resource-coordination-platform/
├── gateway/
├── services/
│   ├── iam/
│   ├── logistics/
│   ├── rto/
│   └── analytics/
├── packages/
│   ├── contracts/
│   ├── common/
│   └── clients/
├── infra/
│   ├── compose/
│   ├── docker/
│   ├── monitoring/
│   └── terraform/
├── docs/
└── README.md
```

## Standard service structure

### Python services: IAM, Logistics, Analytics (and the Gateway)

```text
services/<service-name>/
├── app/
│   ├── api/          # FastAPI routers and request/response handlers
│   ├── core/         # settings, auth binding, keys, security helpers
│   ├── db/           # engine, session, and declarative base setup
│   ├── events/       # outbox publisher, broker relay, consumers (where used)
│   ├── models/       # SQLAlchemy ORM models owned by the service
│   ├── schemas/      # Pydantic DTOs
│   └── services/     # application use-cases and business logic
├── migrations/       # Alembic environment and versioned migrations
├── tests/
├── Dockerfile        # built from the repo root (installs packages/common)
├── requirements.txt
├── alembic.ini
└── .env.example
```

The gateway follows the same shape minus `db/`, `models/`, `schemas/`,
`events/`, and `migrations/` — it owns no data and no business logic.

Analytics owns only `schema_analytics` (projections, idempotency ledger);
its dashboard queries read `schema_logistics` through a SELECT-only role.

### Go service: RTO

```text
services/rto/
├── cmd/server/       # entrypoint, slog JSON logging, /health
├── internal/
│   ├── auth/         # JWT/JWKS verification
│   ├── config/
│   ├── consumer/     # RabbitMQ consumers
│   ├── push/         # push notification adapters
│   ├── store/        # database access
│   └── ws/           # WebSocket hub and delivery
├── migrations/
├── Dockerfile
├── go.mod
└── go.sum
```

## Practical rule of thumb

If a file contains business rules for a single bounded context, it belongs
inside that service. If a file is shared across multiple services, it
belongs in `packages/`. If a file only wires environments, deployment, or
local bootstrapping, it belongs in `infra/`. The gateway routes; it never
implements domain behaviour.
