-- Delta bootstrap for projects created before the analytics service existed:
-- adds schema_analytics + svc_analytics to a database already initialized
-- with the pre-analytics 01-schemas-roles.sql.
-- Supabase Dashboard -> SQL Editor (as postgres). Safe to re-run.
-- CHANGE THE PASSWORD before running (analytics_local_pw is for docker only).

-- ============================================================
-- PART 1 — required for `alembic upgrade head` and the service
-- ============================================================

CREATE SCHEMA IF NOT EXISTS schema_analytics;

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'svc_analytics') THEN
    CREATE ROLE svc_analytics LOGIN PASSWORD 'analytics_local_pw';
  END IF;
END $$;

GRANT USAGE, CREATE ON SCHEMA schema_analytics TO svc_analytics;

-- read model: SELECT-only access to today's logistics tables
GRANT USAGE ON SCHEMA schema_logistics TO svc_analytics;
GRANT SELECT ON ALL TABLES IN SCHEMA schema_logistics TO svc_analytics;

-- lock it down
REVOKE ALL ON SCHEMA public FROM svc_analytics;
REVOKE ALL ON SCHEMA schema_iam FROM svc_analytics;
REVOKE ALL ON SCHEMA schema_rto FROM svc_analytics;
REVOKE ALL ON SCHEMA schema_analytics FROM svc_iam, svc_logistics, svc_rto;

ALTER ROLE svc_analytics SET search_path = schema_analytics;

-- ============================================================
-- PART 2 — optional: auto-grant SELECT on *future* logistics tables.
-- Supabase's postgres is not a superuser, so ALTER DEFAULT PRIVILEGES
-- for/as another role needs temporary membership + SET ROLE. If this
-- part still errors on your project, skip it — the fallback is simply
-- re-running the GRANT SELECT ON ALL TABLES statement above after any
-- logistics migration that adds a table.
-- ============================================================

GRANT svc_logistics TO postgres;
SET ROLE svc_logistics;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_logistics
  GRANT SELECT ON TABLES TO svc_analytics;
RESET ROLE;
REVOKE svc_logistics FROM postgres;

-- Also cover tables created by postgres itself (e.g. via SQL editor or
-- migrations run as postgres):
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_logistics
  GRANT SELECT ON TABLES TO svc_analytics;

-- Verify:
-- select nspname from pg_namespace where nspname = 'schema_analytics';
-- select rolname from pg_roles where rolname = 'svc_analytics';
-- select has_schema_privilege('svc_analytics', 'schema_logistics', 'USAGE');
