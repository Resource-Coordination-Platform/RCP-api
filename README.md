# Resource Coordination Platform (RCP) — Backend

SaaS platform for community-based organizations to coordinate relief during
localized crises: resource requests, inventory tracking, and volunteer
dispatch — multi-tenant, event-driven, offline-first.

**This repository is backend-only.** The frontend clients (Next.js admin
dashboard, Flutter volunteer app) live in a separate repository and consume
the APIs and WebSocket endpoints documented here.

Full design: [docs/architecture-blueprint.md](docs/architecture-blueprint.md)

## Architecture at a glance

| Service | Stack | Schema | Role |
|---|---|---|---|
| `services/iam` | FastAPI | `schema_iam` | Tenants, users, RBAC, RS256 JWT + JWKS |
| `services/logistics` | FastAPI | `schema_logistics` | Categories, inventory, requests, dispatch |
| `services/rto` | Go | `schema_rto` | WebSockets, notifications, offline sync, push |

Communication: RabbitMQ topic exchange `rcp.events` (quorum queues,
transactional outbox, idempotent consumers — no message loss).
Contracts: `packages/contracts` (versioned JSON Schemas, AsyncAPI) — the
frontend repository should consume these + each service's OpenAPI docs
(`/docs` on IAM :8001 and Logistics :8002).

## Quickstart (local)

```bash
# 1. bring up everything: Postgres (schemas+roles auto-created), RabbitMQ,
#    IAM :8001, Logistics :8002, RTO :8080 (ws)
make up            # or: docker compose -f infra/compose/docker-compose.yml up -d --build

# 2. onboard a tenant + admin
curl -X POST http://localhost:8001/api/auth/tenants -H 'Content-Type: application/json' -d '{
  "name": "Kolonnawa Mutual Aid", "slug": "kolonnawa",
  "admin_email": "admin@example.org", "admin_password": "change-me-now",
  "admin_full_name": "Coordinator Fernando"
}'

# 3. login -> use access_token as Bearer against Logistics :8002
curl -X POST http://localhost:8001/api/auth/login -H 'Content-Type: application/json' -d '{
  "tenant_slug": "kolonnawa", "email": "admin@example.org", "password": "change-me-now"
}'
```

RabbitMQ management UI: http://localhost:15672 (rcp / rcp_local_pw).

WebSocket (volunteer client): connect to `ws://localhost:8080/ws` with
subprotocols `["bearer", <access_token>]`; send
`{"type":"sync","cursor":0,"device_id":"dev-1"}` to replay missed events.

## Repository layout

```
services/           iam, logistics (FastAPI) · rto (Go)
packages/contracts/ event schemas + AsyncAPI — the source of truth
infra/compose/      local stack, db-init SQL, rabbitmq definitions
infra/terraform/    modules + envs (dev/staging/prod) + globals
.github/workflows/  path-filtered CI per service + contracts guard
```

CORS for the separate frontend repo: Logistics allows `http://localhost:3000`
by default (`CORS_ORIGINS` in `services/logistics/app/core/config.py`).

## Migration note

`RCP-api/` is the superseded single-service prototype (kept for reference;
its code was split into `services/iam` + `services/logistics`, and its
WebSocket layer was rewritten in Go as `services/rto`). Delete it once the
team is comfortable with the new layout.
