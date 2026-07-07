# Migrating to Supabase with Alembic — Runbook

Applies to `services/iam` and `services/logistics` (SQLAlchemy + Alembic)
and `services/rto` (plain SQL migrations). Schema-per-service is preserved:
`schema_iam`, `schema_logistics`, `schema_rto`, each owned by its `svc_*` role.

---

## Step 0 — Create the Supabase project

1. https://supabase.com → New project.
2. Note three things:
   - **Project ref** (e.g. `abcdefghijklm` — visible in the URL and Settings → General)
   - **Region** (e.g. `ap-south-1`)
   - **Database password** (the `postgres` superuser-ish role's password)

### Which connection string to use (important)

| Purpose | Host | Port | Username format |
|---|---|---|---|
| **Migrations** (Alembic, psql) | `aws-0-<region>.pooler.supabase.com` (session mode) | **5432** | `svc_iam.<ref>` |
| App runtime | same session pooler | 5432 | `svc_logistics.<ref>` |
| Never for Alembic | transaction pooler | 6543 | — |

- The **direct** host `db.<ref>.supabase.co:5432` is IPv6-only — on most home/office
  (IPv4) networks it won't connect; the **session pooler** on port 5432 works everywhere.
- The **transaction pooler (port 6543)** breaks Alembic and SQLAlchemy pooling
  (no prepared statements, no session state). Do not use it for this stack.
- On the pooler, the username is `role.projectref` (e.g. `svc_iam.abcdefghijklm`).
- Always append `?sslmode=require`.

---

## Step 1 — Bootstrap schemas + roles (one time, as postgres)

Open **Supabase Dashboard → SQL Editor**, paste
`infra/compose/db-init/01-schemas-roles.sql`, and **change the three local
passwords to strong ones first** (`iam_local_pw` etc. are for docker only).

Supabase notes:
- The SQL Editor runs as `postgres`, which has `CREATEROLE` — the script works as-is.
- Keep `REVOKE ALL ON SCHEMA public FROM svc_*` — your services must not touch
  `public` (Supabase puts its own extensions there).
- Do **not** expose these schemas via Supabase's Data API (PostgREST): Settings →
  API → Exposed schemas should stay `public` only. Your FastAPI/Go services are
  the only path to the data.

Verify:

```sql
select nspname from pg_namespace where nspname like 'schema_%';
select rolname from pg_roles where rolname like 'svc_%';
```

## Step 2 — Point Alembic at Supabase

Alembic reads `DATABASE_URL` from the environment (see `migrations/env.py` —
it overrides `alembic.ini`). Per service:

```bash
# Git Bash / Linux                                (replace <ref>, <region>, <PW>)
export DATABASE_URL='postgresql+psycopg2://svc_iam.<ref>:<PW>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require'

# PowerShell
$env:DATABASE_URL = 'postgresql+psycopg2://svc_iam.<ref>:<PW>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require'
```

Note the database name on Supabase is `postgres` (not `rcp`).

## Step 3 — Generate + apply the initial IAM migration

```bash
cd services/iam
pip install -r requirements.txt        # if not already

# 1. generate: diffs models (schema_iam.*) against the empty schema
alembic revision --autogenerate -m "initial iam schema"

# 2. REVIEW migrations/versions/xxxx_initial_iam_schema.py
#    expect: create_table for tenants, users, role_assignments,
#    refresh_tokens, signing_keys, outbox — all with schema='schema_iam'

# 3. apply
alembic upgrade head

# 4. confirm
alembic current            # shows the revision id
```

The `alembic_version` table is created inside `schema_iam` itself
(`version_table_schema` in env.py), so each service tracks its own history
independently — no clashes between services.

## Step 4 — Same for Logistics

```bash
cd services/logistics
export DATABASE_URL='postgresql+psycopg2://svc_logistics.<ref>:<PW>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require'

alembic revision --autogenerate -m "initial logistics schema"
# review: user_replicas, resource_categories, inventory_items, help_requests,
# resource_offers, volunteer_profiles, volunteer_skills, dispatch_tasks,
# outbox, processed_events + the 5 enum types, all in schema_logistics
alembic upgrade head
```

## Step 5 — RTO (Go — no Alembic)

Either let the service bootstrap itself once (it runs the embedded,
idempotent `internal/store/schema.sql` on startup), or apply explicitly:

```bash
psql 'postgresql://svc_rto.<ref>:<PW>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require' \
  -f services/rto/migrations/0001_init.up.sql
```

## Step 6 — Switch the services over

In each service's `.env` (or compose/ECS environment):

```env
DATABASE_URL=<the Supabase URL for that service's role>
AUTO_CREATE_TABLES=false        # migrations own the schema now
```

`AUTO_CREATE_TABLES=false` matters: `create_all` must never race Alembic in a
migration-managed database.

Smoke test:

```bash
uvicorn app.main:app --port 8001   # in services/iam
curl -X POST localhost:8001/api/auth/tenants -H 'Content-Type: application/json' \
  -d '{"name":"Test CBO","slug":"test-cbo","admin_email":"a@b.org","admin_password":"change-me-now","admin_full_name":"Admin"}'
# then check Supabase Table Editor → schema_iam → tenants
```

## Step 7 — Ongoing workflow (every model change)

```bash
cd services/<service>
# 1. edit app/models/*.py
# 2. generate the diff
alembic revision --autogenerate -m "add expiry alerts to inventory"
# 3. ALWAYS review the generated file — autogenerate is a draft, not a decision:
#    - it can't detect table/column renames (sees drop+add)
#    - enum VALUE changes need manual op.execute("ALTER TYPE ... ADD VALUE ...")
# 4. apply locally, run tests
alembic upgrade head
# 5. commit the version file with the model change in the same PR
```

Useful commands:

```bash
alembic history          # list revisions
alembic current          # where the DB is
alembic downgrade -1     # roll back one revision
alembic upgrade head --sql   # print SQL without executing (review/DBA mode)
```

In deploys, CI runs `alembic upgrade head` per changed service before the new
image goes live (add it as a step in `.github/workflows/ci-<service>.yml`,
with the Supabase URL from repository secrets).

---

## Gotchas checklist

- [ ] Session pooler (5432), never the transaction pooler (6543), for Alembic.
- [ ] Username is `svc_x.<project-ref>` on the pooler.
- [ ] Database name is `postgres`, `sslmode=require`.
- [ ] Bootstrap SQL run once as `postgres` with strong passwords.
- [ ] `AUTO_CREATE_TABLES=false` everywhere once migrations own the schema.
- [ ] Each service migrates **only its own schema** (enforced by both the role's
      permissions and `include_name` in env.py — a wrong-schema migration fails).
- [ ] Enum changes: autogenerate won't produce `ALTER TYPE`; write it by hand
      (or adopt the `alembic-postgresql-enum` package later).
- [ ] Never edit an applied migration — add a new revision instead.
