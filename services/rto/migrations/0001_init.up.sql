-- schema_rto DDL (idempotent). The schema itself and the svc_rto role are
-- created by infra/compose/db-init; this only manages objects inside it.

CREATE TABLE IF NOT EXISTS schema_rto.devices (
    id           TEXT PRIMARY KEY,           -- client-generated stable device id
    tenant_id    UUID NOT NULL,
    user_id      UUID NOT NULL,
    platform     TEXT,
    push_token   TEXT,
    sync_cursor  BIGINT NOT NULL DEFAULT 0,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_devices_tenant_user ON schema_rto.devices (tenant_id, user_id);

CREATE TABLE IF NOT EXISTS schema_rto.notifications (
    id           UUID PRIMARY KEY,
    tenant_id    UUID NOT NULL,
    user_id      UUID NOT NULL,
    type         TEXT NOT NULL,
    title        TEXT NOT NULL,
    body         JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at TIMESTAMPTZ,
    read_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_notifications_tenant_user
    ON schema_rto.notifications (tenant_id, user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS schema_rto.sync_events (
    seq         BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    op          TEXT NOT NULL,
    payload     JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sync_events_tenant_seq
    ON schema_rto.sync_events (tenant_id, seq);

CREATE TABLE IF NOT EXISTS schema_rto.processed_events (
    event_id     UUID PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);