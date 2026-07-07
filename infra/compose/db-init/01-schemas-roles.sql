-- Schema-per-service bootstrap. Isolation is enforced by GRANTs, not
-- discipline: a cross-schema foreign key is impossible because each
-- service role cannot even see the other schemas.
-- Local passwords only — production injects them from the secrets manager
-- (see infra/terraform/modules/database).

CREATE SCHEMA IF NOT EXISTS schema_iam;
CREATE SCHEMA IF NOT EXISTS schema_logistics;
CREATE SCHEMA IF NOT EXISTS schema_rto;

CREATE ROLE svc_iam       LOGIN PASSWORD 'iam_local_pw';
CREATE ROLE svc_logistics LOGIN PASSWORD 'logistics_local_pw';
CREATE ROLE svc_rto       LOGIN PASSWORD 'rto_local_pw';

GRANT USAGE, CREATE ON SCHEMA schema_iam       TO svc_iam;
GRANT USAGE, CREATE ON SCHEMA schema_logistics TO svc_logistics;
GRANT USAGE, CREATE ON SCHEMA schema_rto       TO svc_rto;

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

-- Belt and braces: no public schema, no cross-schema visibility
REVOKE ALL ON SCHEMA public FROM svc_iam, svc_logistics, svc_rto;
REVOKE ALL ON SCHEMA schema_iam       FROM svc_logistics, svc_rto;
REVOKE ALL ON SCHEMA schema_logistics FROM svc_iam, svc_rto;
REVOKE ALL ON SCHEMA schema_rto       FROM svc_iam, svc_logistics;

ALTER ROLE svc_iam       SET search_path = schema_iam;
ALTER ROLE svc_logistics SET search_path = schema_logistics;
ALTER ROLE svc_rto       SET search_path = schema_rto;
