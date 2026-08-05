# Resource Coordination Platform (RCP) — Backend

SaaS platform for community-based organizations to coordinate relief during
localized crises: resource requests, inventory tracking, and volunteer
dispatch — multi-tenant, event-driven, offline-first.

**This repository is backend-only.** The frontend clients (Next.js admin
dashboard, Flutter volunteer app) live in a separate repository and consume
the APIs and WebSocket endpoints documented here.

Full design: [docs/architecture-blueprint.md](docs/architecture-blueprint.md) ·
Migration record: [docs/migration-summary.md](docs/migration-summary.md)

## Architecture at a glance

| Service | Stack | Schema | Role |
|---|---|---|---|
| `gateway` | FastAPI | — | API gateway: routing, auth forwarding, rate limiting, CORS |
| `services/iam` | FastAPI | `schema_iam` | Tenants, users, RBAC, RS256 JWT + JWKS |
| `services/logistics` | FastAPI | `schema_logistics` | Categories, inventory, requests, offers, volunteers, dispatch |
| `services/analytics` | FastAPI | `schema_analytics` | Dashboards, KPIs, reports — read-only projections |
| `services/rto` | Go | `schema_rto` | WebSockets, notifications, offline sync, push |

Communication: RabbitMQ topic exchange `rcp.events` (quorum queues,
transactional outbox, idempotent consumers — no message loss). Analytics
additionally reads the logistics schema through a SELECT-only role (read
model); it owns no transactional business logic.
Contracts: `packages/contracts` (versioned JSON Schemas, AsyncAPI) — the
frontend repository should consume these + each service's OpenAPI docs
(`/docs` on every HTTP service).

## Quickstart (local)

```bash
# 1. bring up everything: Postgres (schemas+roles auto-created), RabbitMQ,
#    Gateway :8000, IAM :8001, Logistics :8002, Analytics :8003, RTO :8080 (ws)
make up            # or: docker compose -f infra/compose/docker-compose.yml up -d --build
# optional: make up-monitoring   # + Prometheus :9090, Grafana :3001

# 2. onboard a tenant + admin (through the gateway)
curl -X POST http://localhost:8000/api/auth/tenants -H 'Content-Type: application/json' -d '{
  "name": "Kolonnawa Mutual Aid", "slug": "kolonnawa",
  "admin_email": "admin@example.org", "admin_password": "change-me-now",
  "admin_full_name": "Coordinator Fernando"
}'

# 3. login -> use access_token as Bearer against any /api/* route on :8000
curl -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{
  "tenant_slug": "kolonnawa", "email": "admin@example.org", "password": "change-me-now"
}'
```

Services remain individually reachable on :8001–:8003 for debugging; clients
should only talk to the gateway (:8000) and the RTO WebSocket (:8080).

RabbitMQ management UI: http://localhost:15672 (rcp / rcp_local_pw).

WebSocket (volunteer client): connect to `ws://localhost:8080/ws` with
subprotocols `["bearer", <access_token>]`; send
`{"type":"sync","cursor":0,"device_id":"dev-1"}` to replay missed events.

## Repository layout

```
gateway/            API gateway (FastAPI) — routing, rate limiting, CORS
services/           iam, logistics, analytics (FastAPI) · rto (Go)
packages/contracts/ event schemas + AsyncAPI — the source of truth
packages/common/    rcp-common: logging, middleware, exceptions, config, JWKS auth
packages/clients/   rcp-clients: HTTP clients for service-to-service calls
infra/compose/      local stack, db-init SQL, rabbitmq definitions, monitoring overlay
infra/docker/       image build conventions
infra/monitoring/   prometheus + grafana configuration
infra/terraform/    modules + envs (dev/staging/prod) + globals
.github/workflows/  path-filtered CI per service + contracts guard
```

Local Python dev: `make install-packages` (editable installs of
`packages/common` and `packages/clients`) before running services outside
Docker.

CORS for the separate frontend repo is handled at the gateway
(`CORS_ORIGINS` in `gateway/app/core/config.py`; defaults to
`http://localhost:3000`).

For the folder structure conventions per service, see
[docs/microservice-folder-structure.md](docs/microservice-folder-structure.md).


ok now containers running smoothly




If you need to create another Super Admin in the future:
Install argon2-cffi (if running in a new environment):
powershell


pip install argon2-cffi
Run the script:
powershell


cd "d:\Resource Coordination Platform\services\iam"
$env:PYTHONPATH=".;..\..\packages\common"
python -m scripts.bootstrap_superadmin --email newadmin@example.com --password "your-password-here-10chars"