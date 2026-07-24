# Resource Coordination Platform — Production Architecture Blueprint

**Version:** 1.0 · **Date:** 2026-07-07 · **Status:** Approved for implementation
**Architecture style:** Polyglot microservices in a single monorepo, event-driven via RabbitMQ, schema-per-service on Supabase/PostgreSQL.

---

## 1. Service Boundaries & Responsibilities

Three deployable backend services. Each owns exactly one PostgreSQL schema, one RabbitMQ
consumer identity, and one bounded context. Nothing else reads its tables — ever.

### 1.1 IAM Service — `services/iam` (FastAPI, `schema_iam`, DB role `svc_iam`)

The identity, tenancy, and authorization authority.

| Owns | Details |
|---|---|
| Tenants | Onboarding of community organizations (CBOs); tenant lifecycle (active/suspended) |
| Users & credentials | Registration, password hashing (argon2), account status |
| RBAC | Role assignments (`super_admin`, `tenant_admin`, `coordinator`, `volunteer`, `member`); permission catalog |
| Token issuance | **RS256** access tokens (15 min TTL) + refresh tokens (rotating, 14 days); `kid`-versioned signing keys |
| JWKS | Serves `GET /.well-known/jwks.json` — the public keys every other service uses to verify JWTs locally |

**Publishes:** `iam.tenant.created`, `iam.tenant.suspended`, `iam.user.registered`,
`iam.user.updated`, `iam.user.deactivated`, `iam.token.revoked`
**Consumes:** nothing (IAM is upstream of everything; it must never depend on downstream services).

### 1.2 Logistics Service — `services/logistics` (FastAPI, `schema_logistics`, DB role `svc_logistics`)

The core business-domain service: everything a coordinator does.

| Owns | Details |
|---|---|
| Resource categories | The **customizable workflow engine** — admin-defined categories carrying a JSONB form definition *and* a JSONB approval flow, both validated on write and enforced on every request (`app/services/form_schema.py`, `app/services/workflow.py`) |
| Inventory | Donated-goods stock, atomic reservation (`SELECT … FOR UPDATE`), expiry tracking |
| Help requests | Lifecycle state machine, per category. Platform default: `pending → verified → approved → in_progress → fulfilled`; a category may define its own subset/ordering of those states |
| Offers | Donation pledges that convert into inventory on receipt |
| Volunteer operational profiles | Skills, availability, coarse location (identity itself lives in IAM — see §3.3) |
| Dispatch | Task assignment to volunteers; matching by skill/area |
| Reporting read-models | "Need vs. Fulfillment" aggregations for the admin dashboard |

**Publishes:** `logistics.task.assigned`, `logistics.task.status-changed`,
`logistics.request.submitted`, `logistics.request.status-changed`,
`logistics.resource-category.created`, `logistics.resource-category.updated`,
`logistics.inventory.low-stock`, `logistics.offer.status-changed`
**Consumes:** `iam.user.*`, `iam.tenant.*` (to maintain its local user replica, §3.3).

### 1.3 RTO Service — Real-Time Operations — `services/rto` (Go, `schema_rto`, DB role `svc_rto`)

The high-concurrency delivery engine for the volunteer client. Deliberately thin on
business logic: it *delivers state*, it does not *decide state*.

| Owns | Details |
|---|---|
| WebSocket gateway | Tens of thousands of persistent connections; per-tenant connection registry; heartbeat/backpressure |
| Notification store | Durable per-user notification rows (`schema_rto.notifications`) so offline users catch up |
| Offline-first sync feed | Monotonic per-tenant change log (`sync_events` + per-device cursors); volunteers in low-connectivity areas replay everything missed since their last cursor |
| Push notifications | FCM/APNs fan-out for the Flutter client when no socket is connected |
| Delivery receipts | Publishes `rto.delivery.acknowledged` so Logistics can display "volunteer has seen the task" |

**Consumes:** `logistics.#`, `iam.user.deactivated`, `iam.token.revoked`
**Publishes:** `rto.delivery.acknowledged`, `rto.device.registered`

### 1.4 Why exactly three (and the growth path)

Crisis-scale traffic is asymmetric: reads/notifications spike 100× while coordinator
writes stay modest. This split lets you scale the Go RTO tier horizontally without
touching Python, and keeps IAM small, stable, and rarely deployed. When reporting
queries start hurting Logistics, extract `services/analytics` as a fourth consumer that
builds read-models from the same event stream — zero changes to producers.

---

## 2. Monorepo Directory Structure

```
rcp-platform/
├── apps/
│   ├── web-admin/                      # Next.js — coordinator/admin dashboard
│   │   ├── src/
│   │   │   ├── app/                    # App Router pages
│   │   │   ├── components/
│   │   │   ├── lib/api/                # typed API clients (generated from OpenAPI)
│   │   │   └── lib/ws/                 # WebSocket client for live dashboard tiles
│   │   ├── Dockerfile
│   │   └── package.json
│   └── mobile-volunteer/               # Flutter — volunteer client (mobile + web build)
│       ├── lib/
│       │   ├── features/               # tasks/, notifications/, offline_sync/
│       │   ├── core/                   # api client, jwt storage, ws client
│       │   └── data/local/             # drift/sqlite outbox for offline-first writes
│       └── pubspec.yaml
│
├── services/
│   ├── iam/                            # FastAPI — identity, tenants, RBAC, JWT/JWKS
│   │   ├── app/
│   │   │   ├── api/                    # routes: auth, tenants, users, jwks
│   │   │   ├── core/                   # config, key management (kid rotation)
│   │   │   ├── db/                     # engine bound to role svc_iam
│   │   │   ├── models/                 # SQLAlchemy models → schema_iam
│   │   │   ├── schemas/
│   │   │   ├── services/
│   │   │   └── events/publisher.py     # outbox writer (§4.5)
│   │   ├── migrations/                 # Alembic, version_table_schema=schema_iam
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── logistics/                      # FastAPI — inventory, requests, dispatch
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── models/                 # → schema_logistics (incl. user_replicas)
│   │   │   ├── services/
│   │   │   ├── events/
│   │   │   │   ├── publisher.py        # outbox writer
│   │   │   │   └── consumers/iam.py    # maintains user_replicas
│   │   │   └── ...
│   │   ├── migrations/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── rto/                            # Go — WebSockets, sync, push
│       ├── cmd/server/main.go
│       ├── internal/
│       │   ├── ws/                     # hub, per-tenant rooms, backpressure
│       │   ├── auth/                   # JWKS cache + JWT verification (§5)
│       │   ├── consumer/               # RabbitMQ consumers (amqp091-go)
│       │   ├── sync/                   # offline cursor feed
│       │   ├── push/                   # FCM adapter
│       │   └── store/                  # pgx → schema_rto
│       ├── migrations/                 # golang-migrate SQL files
│       ├── Dockerfile
│       └── go.mod
│
├── packages/
│   ├── contracts/                      # ★ THE shared source of truth
│   │   ├── asyncapi.yaml               # broker topology + all event definitions
│   │   ├── events/
│   │   │   ├── envelope.schema.json
│   │   │   ├── iam/user-registered.v1.schema.json
│   │   │   ├── logistics/task-assigned.v1.schema.json
│   │   │   └── ...                     # one file per event, versioned in the name
│   │   └── codegen/                    # generates Pydantic models + Go structs in CI
│   ├── common/                         # pip-installable rcp-common: logging, auth, config
│   ├── clients/                        # pip-installable rcp-clients: service HTTP clients
│   └── ts-shared/                      # shared TS types for web-admin
│
├── infra/
│   ├── compose/
│   │   ├── docker-compose.yml
│   │   ├── db-init/                    # 00-schemas.sql, 01-roles.sql (§3.1)
│   │   └── rabbitmq/definitions.json   # pre-declared exchanges/queues (§4)
│   └── terraform/                      # §6
│       ├── modules/
│       └── envs/{dev,staging,prod}/
│
├── .github/workflows/                  # path-filtered CI per service
│   ├── ci-iam.yml
│   ├── ci-logistics.yml
│   ├── ci-rto.yml
│   ├── ci-frontends.yml
│   └── contracts-check.yml             # breaking-change detection on packages/contracts
├── Makefile                            # make up / make migrate / make test
└── README.md
```

**Monorepo rules:**
1. Services may import `packages/*`; services may **never** import each other.
2. `packages/contracts` changes require a version bump in the schema filename; CI fails on
   in-place edits to a published version.
3. CI is path-filtered: a change under `services/rto/**` builds and deploys only RTO.

### 2.1 `infra/compose/docker-compose.yml`

```yaml
name: rcp

x-common-env: &common-env
  RABBITMQ_URL: amqp://rcp:rcp_local_pw@rabbitmq:5672/rcp
  JWT_JWKS_URL: http://iam:8000/.well-known/jwks.json
  ENVIRONMENT: local

services:
  db:
    # Plain Postgres is sufficient locally because services speak pure SQL.
    # For full Supabase parity (RLS dashboard, storage), run `supabase start`
    # instead and point DATABASE_URLs at its exposed port.
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: rcp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres_local_pw
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db-init:/docker-entrypoint-initdb.d:ro   # creates schemas + roles
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d rcp"]
      interval: 5s
      timeout: 3s
      retries: 10

  rabbitmq:
    image: rabbitmq:3.13-management
    hostname: rcp-rabbit                 # stable hostname => stable mnesia dir
    environment:
      RABBITMQ_DEFAULT_USER: rcp
      RABBITMQ_DEFAULT_PASS: rcp_local_pw
      RABBITMQ_DEFAULT_VHOST: rcp
    ports:
      - "5672:5672"                      # AMQP
      - "15672:15672"                    # management UI
    volumes:
      - rabbitdata:/var/lib/rabbitmq     # durability across restarts
      - ./rabbitmq/definitions.json:/etc/rabbitmq/definitions.json:ro
    command: >
      rabbitmq-server
      --load-definitions /etc/rabbitmq/definitions.json
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10

  iam:
    build: { context: ../../, dockerfile: services/iam/Dockerfile }
    environment:
      <<: *common-env
      DATABASE_URL: postgresql+psycopg2://svc_iam:iam_local_pw@db:5432/rcp
      JWT_PRIVATE_KEY_PATH: /run/secrets/jwt_signing_key
    ports: ["8001:8000"]
    depends_on:
      db: { condition: service_healthy }
      rabbitmq: { condition: service_healthy }
    secrets: [jwt_signing_key]

  logistics:
    build: { context: ../../, dockerfile: services/logistics/Dockerfile }
    environment:
      <<: *common-env
      DATABASE_URL: postgresql+psycopg2://svc_logistics:logistics_local_pw@db:5432/rcp
    ports: ["8002:8000"]
    depends_on:
      db: { condition: service_healthy }
      rabbitmq: { condition: service_healthy }
      iam: { condition: service_started }

  rto:
    build: { context: ../../, dockerfile: services/rto/Dockerfile }
    environment:
      <<: *common-env
      DATABASE_URL: postgres://svc_rto:rto_local_pw@db:5432/rcp
    ports: ["8080:8080"]                 # ws://localhost:8080/ws
    depends_on:
      db: { condition: service_healthy }
      rabbitmq: { condition: service_healthy }

  web-admin:
    build: { context: ../../apps/web-admin }
    environment:
      NEXT_PUBLIC_API_BASE: http://localhost:8002
      NEXT_PUBLIC_IAM_BASE: http://localhost:8001
      NEXT_PUBLIC_WS_URL: ws://localhost:8080/ws
    ports: ["3000:3000"]
    depends_on: [iam, logistics, rto]

secrets:
  jwt_signing_key:
    file: ./secrets/jwt_dev_key.pem      # dev-only key, never committed for prod

volumes:
  pgdata:
  rabbitdata:
```

---

## 3. Database Schema Blueprint (Supabase / PostgreSQL)

### 3.1 Schemas, roles, and the isolation contract

One Supabase project, one database, three schemas. **Isolation is enforced by GRANTs,
not by discipline.** `infra/compose/db-init/01-roles.sql` (mirrored in production by a
Terraform-invoked migration):

```sql
-- Schemas
CREATE SCHEMA IF NOT EXISTS schema_iam;
CREATE SCHEMA IF NOT EXISTS schema_logistics;
CREATE SCHEMA IF NOT EXISTS schema_rto;

-- One login role per service; passwords injected from secrets manager in prod
CREATE ROLE svc_iam       LOGIN PASSWORD 'iam_local_pw';
CREATE ROLE svc_logistics LOGIN PASSWORD 'logistics_local_pw';
CREATE ROLE svc_rto       LOGIN PASSWORD 'rto_local_pw';

-- Each role: full rights on its own schema, no visibility of the others
GRANT USAGE, CREATE ON SCHEMA schema_iam       TO svc_iam;
GRANT USAGE, CREATE ON SCHEMA schema_logistics TO svc_logistics;
GRANT USAGE, CREATE ON SCHEMA schema_rto       TO svc_rto;

ALTER DEFAULT PRIVILEGES IN SCHEMA schema_iam
  GRANT ALL ON TABLES TO svc_iam;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_logistics
  GRANT ALL ON TABLES TO svc_logistics;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_rto
  GRANT ALL ON TABLES TO svc_rto;

-- Belt and braces: revoke public schema creation and cross-schema access
REVOKE ALL ON SCHEMA public FROM svc_iam, svc_logistics, svc_rto;
REVOKE ALL ON SCHEMA schema_iam       FROM svc_logistics, svc_rto;
REVOKE ALL ON SCHEMA schema_logistics FROM svc_iam, svc_rto;
REVOKE ALL ON SCHEMA schema_rto       FROM svc_iam, svc_logistics;

ALTER ROLE svc_iam       SET search_path = schema_iam;
ALTER ROLE svc_logistics SET search_path = schema_logistics;
ALTER ROLE svc_rto       SET search_path = schema_rto;
```

A cross-schema foreign key is now not merely forbidden by convention — it is
**impossible**, because `svc_logistics` cannot even see `schema_iam.users`.

Multi-tenancy: every table carries `tenant_id UUID NOT NULL` with a composite index
leading on it. On Supabase, additionally enable RLS per table with a
`tenant_id = current_setting('app.tenant_id')::uuid` policy as defense-in-depth; each
service sets `app.tenant_id` per transaction from the JWT claim.

### 3.2 Tables per schema

**`schema_iam`** (owner: IAM)

```sql
tenants        (id PK, name, slug UNIQUE, status, created_at, updated_at)
users          (id PK, tenant_id, email, password_hash, full_name, phone,
                status, created_at, updated_at,
                UNIQUE (tenant_id, email))
role_assignments (id PK, tenant_id, user_id → users.id, role, granted_by, granted_at)
refresh_tokens (id PK, user_id → users.id, token_hash, expires_at, rotated_from, revoked_at)
signing_keys   (kid PK, public_pem, private_ref, active, created_at, retired_at)
outbox         (see §4.5)
```

**`schema_logistics`** (owner: Logistics)

```sql
user_replicas       (user_id PK, tenant_id, full_name, phone, roles TEXT[],
                     is_active, source_updated_at, synced_at)      -- ★ no FK anywhere
resource_categories (id PK, tenant_id, name, unit, form_schema JSONB,
                     workflow JSONB,             -- NULL = platform default flow
                     is_active, ...)             -- retirement is a soft delete
inventory_items     (id PK, tenant_id, category_id → resource_categories.id,
                     name, quantity_total, quantity_reserved, status, expiry_date, ...)
help_requests       (id PK, tenant_id, category_id → resource_categories.id,
                     requester_user_id UUID,          -- logical ref to IAM, NO FK
                     description, quantity_needed, urgency, status,
                     is_sensitive, verified_by_user_id UUID, verified_at, fulfilled_at, ...)
resource_offers     (id PK, tenant_id, donor_user_id UUID, category_id, status, ...)
volunteer_profiles  (id PK, tenant_id, user_id UUID UNIQUE,        -- logical ref, NO FK
                     availability, area, lat, lng)
volunteer_skills    (volunteer_id → volunteer_profiles.id, skill TEXT)
dispatch_tasks      (id PK, tenant_id, request_id → help_requests.id,
                     volunteer_user_id UUID, assigned_by_user_id UUID,
                     title, instructions, status, accepted_at, completed_at, ...)
outbox              (see §4.5)
processed_events    (event_id PK, processed_at)                    -- consumer idempotency
```

Note the pattern: FKs are used *freely inside* a schema (request → category) and
*never across* schemas (task → user is a bare UUID).

**`schema_rto`** (owner: RTO)

```sql
devices          (id PK, tenant_id, user_id UUID, platform, push_token,
                  last_seen_at, sync_cursor BIGINT)
notifications    (id PK, tenant_id, user_id UUID, type, title, body JSONB,
                  created_at, read_at, delivered_at)
sync_events      (seq BIGSERIAL PK, tenant_id, entity_type, entity_id,
                  op, payload JSONB, occurred_at)   -- append-only change feed
processed_events (event_id PK, processed_at)
```

Offline-first mechanics: every consumed domain event appends a row to `sync_events`.
A reconnecting Flutter client sends its device's `sync_cursor`; RTO streams
`WHERE tenant_id = $1 AND seq > $2 ORDER BY seq`, then updates the cursor. Low-bandwidth
clients get exactly the delta, in order, idempotently replayable.

### 3.3 Relations without foreign keys — the three patterns

**Problem:** `dispatch_tasks.volunteer_user_id` refers to a user that lives in
`schema_iam.users`, which Logistics cannot read.

1. **Logical reference (always):** store the bare UUID. The ID is minted by IAM and is
   globally unique; referential *identity* needs no FK.
2. **Event-carried state replication (for read-path data):** Logistics consumes
   `iam.user.registered` / `iam.user.updated` / `iam.user.deactivated` and upserts
   `user_replicas`. Rendering "assigned to *Nimal Perera*" is a local join to the
   replica — no runtime call to IAM, which matters when a crisis takes services down
   intermittently. Staleness is bounded by broker lag (normally < 1 s).
   Upserts are guarded by `source_updated_at` comparison so out-of-order events can't
   regress data, and `processed_events` makes redelivery a no-op.
3. **Fat events (for cross-service workflows):** events carry every field the consumer
   needs (names, titles, locations), so RTO can notify a volunteer without owning any
   user data beyond what arrived in the event (§4.4).

**Integrity without FK cascades:** deletion becomes a domain event, not a cascade.
`iam.user.deactivated` → Logistics marks the replica inactive and un-assigns open
tasks → publishes `logistics.task.status-changed` → RTO notifies coordinators.
A nightly reconciliation job compares replica counts/checksums per tenant against an
IAM-exposed digest endpoint and re-syncs drift.

---

## 4. RabbitMQ Event Contracts

### 4.1 Topology

| Object | Name | Type / Settings |
|---|---|---|
| Exchange | `rcp.events` | **topic**, durable |
| Dead-letter exchange | `rcp.dlx` | topic, durable |
| Queue | `logistics.iam-events.q` | **quorum**, durable, DLX → `rcp.dlx` |
| Queue | `rto.domain-events.q` | quorum, durable, DLX → `rcp.dlx` |
| Queue | `dlq.logistics.iam-events` | classic, durable (bound to `rcp.dlx`) |
| Queue | `dlq.rto.domain-events` | classic, durable (bound to `rcp.dlx`) |

Routing-key grammar: `<producer-service>.<entity>.<action>` — e.g.
`logistics.task.assigned`, `iam.user.updated`.

Bindings:

```
logistics.iam-events.q   ← rcp.events : iam.user.*        , iam.tenant.*
rto.domain-events.q      ← rcp.events : logistics.#       , iam.user.deactivated
                                        , iam.token.revoked
```

### 4.2 The no-message-loss contract (each layer is mandatory)

| Layer | Mechanism |
|---|---|
| Broker | Durable topic exchange; **quorum queues** (Raft-replicated in a cluster, survive node loss) |
| Message | `delivery_mode=2` (persistent) on every publish |
| Producer | **Publisher confirms** + **transactional outbox** (§4.5) — an event is only "sent" once the broker confirms, and it can't be lost before that because it's committed in the producer's own DB transaction |
| Consumer | Manual `ack` only after the DB transaction commits; `nack(requeue=false)` after N retries → DLQ; `prefetch=32` for flow control |
| Idempotency | Consumers upsert into `processed_events(event_id)` inside the same transaction as the side effect — at-least-once delivery becomes effectively-once processing |
| Ops | DLQ depth alerting; shovel from DLQ back to the exchange after fixes |

### 4.3 Envelope (all events, `packages/contracts/events/envelope.schema.json`)

```json
{
  "event_id":       "uuid — producer-generated, the idempotency key",
  "event_type":     "logistics.task.assigned",
  "schema_version": 1,
  "occurred_at":    "RFC3339 UTC",
  "tenant_id":      "uuid",
  "producer":       "logistics-service",
  "trace_id":       "W3C traceparent for cross-service tracing",
  "data":           { "…event-specific payload…" }
}
```

Versioning rules: additive changes bump nothing; breaking changes create
`task-assigned.v2.schema.json` and a new `schema_version`. Consumers tolerate unknown
fields (Go: no `DisallowUnknownFields`; Pydantic: `extra="ignore"`).

### 4.4 Concrete example — `logistics.task.assigned` (FastAPI → Go)

Published by Logistics when a coordinator dispatches a volunteer. Routing key
`logistics.task.assigned`, exchange `rcp.events`, persistent, confirmed.

```json
{
  "event_id": "7f3b9c1e-2d4a-4f6b-9e8d-1a2b3c4d5e6f",
  "event_type": "logistics.task.assigned",
  "schema_version": 1,
  "occurred_at": "2026-07-07T09:41:22.318Z",
  "tenant_id": "c2a7e5d0-8b91-4c3f-a6d2-0f9e8d7c6b5a",
  "producer": "logistics-service",
  "trace_id": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
  "data": {
    "task_id": "a1b2c3d4-e5f6-4a5b-8c7d-9e0f1a2b3c4d",
    "request_id": "d4c3b2a1-f6e5-4b5a-7d8c-0f9e2b1a4c3d",
    "title": "Deliver 20 water containers to Ward 12 shelter",
    "instructions": "Collect from the Nugegoda hub. Ask for the shelter lead, Ms. Silva.",
    "priority": "high",
    "category": { "id": "9e8d7c6b-...", "name": "Drinking Water" },
    "location": { "area": "Ward 12, Kolonnawa", "lat": 6.9271, "lng": 79.8912 },
    "volunteer": { "user_id": "5a4b3c2d-...", "full_name": "Nimal Perera" },
    "assigned_by": { "user_id": "1f2e3d4c-...", "full_name": "Coordinator Fernando" },
    "assigned_at": "2026-07-07T09:41:22.001Z",
    "expires_at": "2026-07-07T13:41:22.001Z"
  }
}
```

This is a deliberately **fat event**: RTO can (1) push "New task: Deliver 20 water
containers" to the volunteer's device, (2) persist the notification row, and
(3) append to the sync feed — all without calling any other service. Go consumer flow:

```
deserialize → validate envelope → SELECT 1 FROM processed_events WHERE event_id=$1
  (hit → ack, done)
BEGIN; INSERT notification; INSERT sync_event; INSERT processed_events; COMMIT;
push via FCM (best-effort, outside tx); ack
```

### 4.5 Transactional outbox (producer side)

State change and event must be atomic, and a broker outage must not lose events:

```
BEGIN;
  UPDATE dispatch_tasks SET status='assigned' ...;
  INSERT INTO outbox(event_id, routing_key, payload, created_at);
COMMIT;
-- relay worker (same service, background loop):
--   SELECT ... FROM outbox WHERE published_at IS NULL ORDER BY created_at
--     FOR UPDATE SKIP LOCKED LIMIT 100;
--   publish with publisher-confirms → set published_at
```

If RabbitMQ is down for an hour during a flood response, events queue in the outbox
and drain when it returns. Nothing is lost; ordering per aggregate is preserved.

---

## 5. Security: JWT Authentication Flow (FastAPI-issued, Go-verified)

The Go service **never** queries `schema_iam` and never calls IAM synchronously on the
hot path. Verification is purely cryptographic.

**Key design:** IAM signs with **RS256** (asymmetric). Only IAM holds the private key
(from the secrets manager). Every verifier needs only the public key, fetched from
IAM's JWKS endpoint and cached.

### Step-by-step

1. **Key provisioning (boot/rotation).** IAM loads its private key; publishes public keys
   at `GET /.well-known/jwks.json`, each with a `kid`. Rotation = add new key, sign with
   it, keep the old public key published until all tokens signed by it have expired.
2. **Login.** Flutter client → `POST /api/auth/login` (IAM). IAM verifies credentials
   against `schema_iam`, then issues:
   - **Access token** (JWT, 15 min): claims `sub` (user id), `tenant_id`, `roles`,
     `iss=rcp-iam`, `aud=rcp-services`, `exp`, `iat`, `jti`, header `kid`.
   - **Refresh token** (opaque, rotating, 14 d) — exchanged only with IAM.
3. **JWKS warm-up.** The Go RTO service fetched the JWKS at startup and caches it in
   memory (TTL ~10 min, plus refresh-on-unknown-`kid` with a singleflight guard so a
   rotation doesn't stampede IAM).
4. **WebSocket connect.** Client opens
   `wss://rto.example.org/ws` and presents the access token in the
   `Sec-WebSocket-Protocol` header (`bearer, <jwt>`) — never in the query string, which
   leaks into proxy/access logs. (Browser fallback: first-frame auth message with a 5 s
   deadline before the socket is dropped.)
5. **Local verification in Go (no I/O).** RTO: parses header → picks public key by
   `kid` from cache → verifies RS256 signature, `exp`/`nbf` (±60 s skew), `iss`, `aud`,
   and **algorithm allow-list = {RS256}** (rejects `none`/`HS256` confusion attacks).
6. **Authorization context.** From the verified claims RTO builds
   `{user_id, tenant_id, roles}` and registers the connection in the per-tenant hub.
   Every outbound frame is filtered by `tenant_id` — a socket can only ever join its
   own tenant's rooms. `roles` gates channels (e.g. only `coordinator` may subscribe to
   the dashboard firehose).
7. **Session lifetime.** The socket outlives the 15-min token. Client sends a
   `refresh_auth` frame with a new access token before expiry (obtained from IAM via
   refresh token); RTO re-verifies and extends the session, else closes with code
   `4401` at `exp` + grace.
8. **Revocation without DB lookups.** IAM publishes `iam.token.revoked` /
   `iam.user.deactivated`; RTO consumes and (a) drops matching live connections,
   (b) holds a small in-memory denylist of `jti`/`sub` until those tokens' `exp`
   passes. Bounded memory, zero hot-path I/O.
9. **Service-to-service calls** (rare, e.g. reconciliation) use client-credentials
   JWTs from IAM with `aud=rcp-internal` — same verification path.

Failure isolation: if IAM is down, existing sockets keep working and new connections
with valid unexpired JWTs still verify (JWKS is cached). Only fresh logins are blocked
— exactly the right degradation for a crisis platform.

---

## 6. Terraform IaC Strategy

### 6.1 Repository layout

```
infra/terraform/
├── modules/
│   ├── network/              # VPC, subnets, NAT, security groups
│   ├── database/             # Supabase project (supabase/supabase provider):
│   │                         #   project, connection pooler settings; runs the
│   │                         #   schema/role bootstrap (§3.1) as a post-provision step
│   ├── message-broker/       # CloudAMQP (cloudamqp provider) or Amazon MQ RabbitMQ,
│   │                         #   3-node cluster in prod; vhost, users, permissions,
│   │                         #   exchanges/queues via definitions import
│   ├── container-registry/   # ECR repos: iam, logistics, rto, web-admin
│   ├── app-runtime/          # ECS Fargate services + ALB; per-service CPU/mem,
│   │                         #   autoscaling policies (RTO scales on connection count)
│   ├── secrets/              # Secrets Manager: DB role passwords, JWT private key,
│   │                         #   broker creds; IAM task-role policies scoped per service
│   ├── observability/        # CloudWatch/Grafana, alarms: DLQ depth, outbox lag,
│   │                         #   WS connection saturation, p99 publish confirm time
│   └── frontend/             # web-admin: Vercel (vercel provider) or S3+CloudFront;
│                             #   Flutter web build → CDN bucket
├── envs/
│   ├── dev/      { backend.tf, main.tf, variables.tf, terraform.tfvars }
│   ├── staging/  { … }
│   └── prod/     { … }
└── globals/                  # one-time: state bucket + lock table, org DNS zone
```

Principles:
- **Modules are generic; envs are thin.** An env `main.tf` only wires modules with
  sizes/counts. Dev: single-node RabbitMQ, `db.small`; prod: 3-node quorum cluster,
  HA pooler, multi-AZ.
- **Remote state** per env (S3 + DynamoDB lock, encrypted); never shared between envs.
- **No secrets in state inputs where avoidable** — passwords generated with
  `random_password`, written straight to Secrets Manager, read by tasks at runtime.
- **CI/CD:** PR → `terraform plan` posted as comment; merge to `main` → auto-apply dev;
  tag → plan+manual-approve apply for prod. App deploys are *not* Terraform — CI pushes
  images to ECR and updates the ECS task definition (faster, decoupled from infra).

### 6.2 Example: `envs/prod/main.tf` (module wiring)

```hcl
terraform {
  backend "s3" {
    bucket         = "rcp-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "rcp-terraform-locks"
    encrypt        = true
  }
  required_providers {
    aws       = { source = "hashicorp/aws" }
    cloudamqp = { source = "cloudamqp/cloudamqp" }
    supabase  = { source = "supabase/supabase" }
  }
}

module "network" {
  source   = "../../modules/network"
  env      = "prod"
  az_count = 3
}

module "database" {
  source            = "../../modules/database"
  env               = "prod"
  organization_slug = var.supabase_org
  db_region         = "ap-south-1"
  # runs db-init bootstrap (schemas + svc_* roles) after provisioning
  bootstrap_sql     = file("${path.module}/../../../compose/db-init/01-roles.sql")
}

module "broker" {
  source  = "../../modules/message-broker"
  env     = "prod"
  plan    = "penguin-3"            # 3-node HA cluster
  vhost   = "rcp"
  # exchanges/queues/DLX from the same definitions file used locally
  definitions = file("${path.module}/../../compose/rabbitmq/definitions.json")
}

module "registry" {
  source = "../../modules/container-registry"
  repos  = ["iam", "logistics", "rto", "web-admin"]
}

module "runtime" {
  source     = "../../modules/app-runtime"
  env        = "prod"
  vpc_id     = module.network.vpc_id
  subnets    = module.network.private_subnets
  services = {
    iam       = { image = "${module.registry.urls["iam"]}:${var.release}",       cpu = 512,  memory = 1024, min = 2, max = 4 }
    logistics = { image = "${module.registry.urls["logistics"]}:${var.release}", cpu = 1024, memory = 2048, min = 2, max = 8 }
    rto       = { image = "${module.registry.urls["rto"]}:${var.release}",       cpu = 1024, memory = 2048, min = 3, max = 20,
                  scale_metric = "ActiveConnectionCount" }   # crisis-spike scaling
  }
  secrets_arns = module.secrets.arns
}
```

### 6.3 Crisis-readiness checklist (what "reliable under load" means here)

- RTO autoscales on **live WebSocket connections**, not CPU — connection storms precede CPU load.
- Quorum queues + publisher confirms + outbox ⇒ a full broker-node loss during a flood response loses zero events.
- JWKS caching ⇒ IAM outage does not sever existing volunteer connections (§5).
- Offline sync cursors ⇒ volunteers in dead zones reconcile deterministically on reconnect (§3.2).
- DLQ depth and outbox-lag alarms page *before* coordinators notice missing updates.

---

## Appendix A — Migration note from the current codebase

The legacy `RCP-api/backend` (single FastAPI app, since deleted) mapped onto this blueprint as:
- `app/models/tenant.py`, `user.py`, `core/security.py` → `services/iam`
- `app/models/{resource,request,offer,task,volunteer}.py`, `services/*` → `services/logistics`
- `app/websockets/*`, `app/models/notification.py` → rewritten in Go under `services/rto`

Migrate incrementally: extract IAM first (it has no upstream dependencies), introduce
the broker + outbox second, and split RTO last — the WebSocket manager keeps working
inside the monolith until then.
