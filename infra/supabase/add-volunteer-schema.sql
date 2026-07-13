-- Delta bootstrap for projects created before the volunteer service existed:
-- adds schema_volunteer + svc_volunteer to a database already initialized
-- with an earlier 01-schemas-roles.sql.
-- Supabase Dashboard -> SQL Editor (as postgres). Safe to re-run.
-- CHANGE THE PASSWORD before running (volunteer_local_pw is for docker only).

-- ============================================================
-- PART 1 — schema + role (required before the service can connect)
-- ============================================================

CREATE SCHEMA IF NOT EXISTS schema_volunteer;

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'svc_volunteer') THEN
    CREATE ROLE svc_volunteer LOGIN PASSWORD 'volunteer_local_pw';
  END IF;
END $$;

GRANT USAGE, CREATE ON SCHEMA schema_volunteer TO svc_volunteer;

ALTER DEFAULT PRIVILEGES IN SCHEMA schema_volunteer
  GRANT ALL ON TABLES TO svc_volunteer;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_volunteer
  GRANT ALL ON SEQUENCES TO svc_volunteer;

-- lock it down: same isolation rules as every other service role
REVOKE ALL ON SCHEMA public FROM svc_volunteer;
REVOKE ALL ON SCHEMA schema_iam       FROM svc_volunteer;
REVOKE ALL ON SCHEMA schema_logistics FROM svc_volunteer;
REVOKE ALL ON SCHEMA schema_rto       FROM svc_volunteer;
REVOKE ALL ON SCHEMA schema_analytics FROM svc_volunteer;
REVOKE ALL ON SCHEMA schema_volunteer FROM svc_iam, svc_logistics, svc_rto, svc_analytics;

ALTER ROLE svc_volunteer SET search_path = schema_volunteer;

-- ============================================================
-- PART 2 — tables. Two options, pick ONE:
--
-- (a) Point the volunteer service's DATABASE_URL at this project and let
--     it boot once with AUTO_CREATE_TABLES=true (local default) — it
--     creates all six tables as svc_volunteer.
--
-- (b) Run Alembic as svc_volunteer once a baseline revision exists:
--       cd services/volunteer
--       $env:DATABASE_URL = "postgresql+psycopg2://svc_volunteer:<pw>@<host>:5432/postgres"
--       alembic upgrade head
-- ============================================================

-- Verify:
-- select nspname from pg_namespace where nspname = 'schema_volunteer';
-- select rolname from pg_roles where rolname = 'svc_volunteer';
-- select has_schema_privilege('svc_volunteer', 'schema_volunteer', 'CREATE');
