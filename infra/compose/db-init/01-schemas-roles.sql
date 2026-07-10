-- Schema-per-service bootstrap. Isolation is enforced by GRANTs, not
-- discipline: a cross-schema foreign key is impossible because each
-- service role cannot even see the other schemas.
-- Local passwords only — production injects them from the secrets manager
-- (see infra/terraform/modules/database).

CREATE SCHEMA IF NOT EXISTS schema_iam;
CREATE SCHEMA IF NOT EXISTS schema_logistics;
CREATE SCHEMA IF NOT EXISTS schema_rto;
CREATE SCHEMA IF NOT EXISTS schema_analytics;

CREATE ROLE svc_iam       LOGIN PASSWORD 'iam_local_pw';
CREATE ROLE svc_logistics LOGIN PASSWORD 'logistics_local_pw';
CREATE ROLE svc_rto       LOGIN PASSWORD 'rto_local_pw';
CREATE ROLE svc_analytics LOGIN PASSWORD 'analytics_local_pw';

GRANT USAGE, CREATE ON SCHEMA schema_iam       TO svc_iam;
GRANT USAGE, CREATE ON SCHEMA schema_logistics TO svc_logistics;
GRANT USAGE, CREATE ON SCHEMA schema_rto       TO svc_rto;
GRANT USAGE, CREATE ON SCHEMA schema_analytics TO svc_analytics;

ALTER DEFAULT PRIVILEGES IN SCHEMA schema_iam
  GRANT ALL ON TABLES TO svc_iam;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_iam
  GRANT ALL ON SEQUENCES TO svc_iam;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_logistics
  GRANT ALL ON TABLES TO svc_logistics;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_logistics
  GRANT ALL ON SEQUENCES TO svc_logistics;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_rto
  GRANT ALL ON TABLES TO svc_rto;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_rto
  GRANT ALL ON SEQUENCES TO svc_rto;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_analytics
  GRANT ALL ON TABLES TO svc_analytics;
ALTER DEFAULT PRIVILEGES IN SCHEMA schema_analytics
  GRANT ALL ON SEQUENCES TO svc_analytics;

-- Analytics is the one sanctioned exception to full isolation: it reads
-- the logistics schema as a *read model* — SELECT only, never write.
GRANT USAGE ON SCHEMA schema_logistics TO svc_analytics;
GRANT SELECT ON ALL TABLES IN SCHEMA schema_logistics TO svc_analytics;
-- On Supabase, postgres is not a true superuser: wrap the next statement in
-- GRANT svc_logistics TO postgres; ... REVOKE svc_logistics FROM postgres;
-- (see infra/supabase/add-analytics-schema.sql)
ALTER DEFAULT PRIVILEGES FOR ROLE svc_logistics IN SCHEMA schema_logistics
  GRANT SELECT ON TABLES TO svc_analytics;

-- Belt and braces: no public schema, no cross-schema visibility
REVOKE ALL ON SCHEMA public FROM svc_iam, svc_logistics, svc_rto, svc_analytics;
REVOKE ALL ON SCHEMA schema_iam       FROM svc_logistics, svc_rto, svc_analytics;
REVOKE ALL ON SCHEMA schema_logistics FROM svc_iam, svc_rto;
REVOKE ALL ON SCHEMA schema_rto       FROM svc_iam, svc_logistics, svc_analytics;
REVOKE ALL ON SCHEMA schema_analytics FROM svc_iam, svc_logistics, svc_rto;

ALTER ROLE svc_iam       SET search_path = schema_iam;
ALTER ROLE svc_logistics SET search_path = schema_logistics;
ALTER ROLE svc_rto       SET search_path = schema_rto;
ALTER ROLE svc_analytics SET search_path = schema_analytics;
