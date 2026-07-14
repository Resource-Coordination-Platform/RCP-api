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

-- lock it down. Analytics is fed by logistics events over RabbitMQ into its
-- own projection tables — it holds NO grants on schema_logistics. The
-- revokes below also clean up the read-model grant that earlier versions
-- of this script created (safe to re-run either way).
REVOKE ALL ON SCHEMA public FROM svc_analytics;
REVOKE ALL ON SCHEMA schema_iam FROM svc_analytics;
REVOKE ALL ON SCHEMA schema_rto FROM svc_analytics;
REVOKE SELECT ON ALL TABLES IN SCHEMA schema_logistics FROM svc_analytics;
REVOKE ALL ON SCHEMA schema_logistics FROM svc_analytics;
REVOKE ALL ON SCHEMA schema_analytics FROM svc_iam, svc_logistics, svc_rto;

ALTER ROLE svc_analytics SET search_path = schema_analytics;

-- Verify:
-- select nspname from pg_namespace where nspname = 'schema_analytics';
-- select rolname from pg_roles where rolname = 'svc_analytics';
-- select has_schema_privilege('svc_analytics', 'schema_logistics', 'USAGE');  -- must be false
