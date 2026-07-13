-- Delta bootstrap: actor decoupling for schema_iam on a database that
-- predates it (mirror of services/iam/migrations/versions/
-- a4c9d1e0b2f7_decouple_global_users.py).
-- Supabase Dashboard -> SQL Editor (as postgres). Safe to re-run:
-- every step is guarded.
--
-- Supabase's postgres is NOT a superuser and ALTER TABLE requires the
-- table owner. If schema_iam tables are owned by svc_iam (they are when
-- the service created them), run this first:
--   GRANT svc_iam TO postgres;
--   SET ROLE svc_iam;
-- ...then this whole script, then:
--   RESET ROLE;
--   REVOKE svc_iam FROM postgres;

-- 1) the user_type enum
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE t.typname = 'user_type' AND n.nspname = 'schema_iam'
  ) THEN
    CREATE TYPE schema_iam.user_type AS ENUM
      ('VOLUNTEER', 'VICTIM', 'DONATOR', 'TENANT_ADMIN', 'COORDINATOR');
  END IF;
END $$;

-- 2) users.user_type: add nullable, backfill from legacy roles, tighten
ALTER TABLE schema_iam.users
  ADD COLUMN IF NOT EXISTS user_type schema_iam.user_type;

UPDATE schema_iam.users u SET user_type = CASE
    WHEN EXISTS (SELECT 1 FROM schema_iam.role_assignments ra
                 WHERE ra.user_id = u.id AND ra.role = 'tenant_admin')
        THEN 'TENANT_ADMIN'::schema_iam.user_type
    ELSE 'COORDINATOR'::schema_iam.user_type  -- legacy tenant users stay staff;
                                              -- true volunteers re-register
                                              -- via the mobile app
  END
WHERE u.user_type IS NULL;

ALTER TABLE schema_iam.users ALTER COLUMN user_type SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_schema_iam_users_user_type
  ON schema_iam.users (user_type);

-- 3) tenant_id becomes nullable (NULL == global mobile-app user)
ALTER TABLE schema_iam.users ALTER COLUMN tenant_id DROP NOT NULL;
ALTER TABLE schema_iam.role_assignments ALTER COLUMN tenant_id DROP NOT NULL;

-- 4) global pool uniqueness (NULL tenant_id escapes uq_users_tenant_email)
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_global_email
  ON schema_iam.users (email) WHERE tenant_id IS NULL;

-- 5) the decoupling invariant
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT FROM pg_constraint
    WHERE conname = 'ck_users_type_tenancy'
      AND conrelid = 'schema_iam.users'::regclass
  ) THEN
    ALTER TABLE schema_iam.users ADD CONSTRAINT ck_users_type_tenancy
      CHECK ((user_type IN ('TENANT_ADMIN', 'COORDINATOR')) = (tenant_id IS NOT NULL));
  END IF;
END $$;

-- 6) record the migration so `alembic upgrade head` agrees with reality
CREATE TABLE IF NOT EXISTS schema_iam.alembic_version (
  version_num varchar(32) NOT NULL,
  CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO schema_iam.alembic_version (version_num)
  VALUES ('a4c9d1e0b2f7') ON CONFLICT DO NOTHING;
-- If the row '91e8fdce8367' (init) is present instead, replace it:
UPDATE schema_iam.alembic_version
  SET version_num = 'a4c9d1e0b2f7' WHERE version_num = '91e8fdce8367';

-- Verify:
-- \d schema_iam.users  -- should show user_type, nullable tenant_id,
--                         uq_users_global_email, ck_users_type_tenancy
