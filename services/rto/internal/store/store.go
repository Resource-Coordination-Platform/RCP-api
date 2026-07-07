// Package store owns schema_rto: notifications, devices, the offline
// sync feed, and consumer idempotency.
package store

import (
	"context"
	_ "embed"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

//go:embed schema.sql
var schemaSQL string

type Store struct {
	Pool *pgxpool.Pool
}

func New(ctx context.Context, dsn string) (*Store, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, err
	}
	return &Store{Pool: pool}, nil
}

// EnsureSchema applies the idempotent DDL (local/dev convenience;
// production runs migrations/ via golang-migrate in CI).
func (s *Store) EnsureSchema(ctx context.Context) error {
	_, err := s.Pool.Exec(ctx, schemaSQL)
	return err
}

type Notification struct {
	ID        uuid.UUID `json:"id"`
	TenantID  uuid.UUID `json:"tenant_id"`
	UserID    uuid.UUID `json:"user_id"`
	Type      string    `json:"type"`
	Title     string    `json:"title"`
	Body      []byte    `json:"body"`
	CreatedAt time.Time `json:"created_at"`
}

type SyncEvent struct {
	Seq        int64     `json:"seq"`
	TenantID   uuid.UUID `json:"tenant_id"`
	EntityType string    `json:"entity_type"`
	EntityID   string    `json:"entity_id"`
	Op         string    `json:"op"`
	Payload    []byte    `json:"payload"`
	OccurredAt time.Time `json:"occurred_at"`
}

// ProcessEvent runs fn inside a transaction that also records the
// event_id in processed_events. Returns (false, nil) without calling fn
// if the event was already processed — effectively-once processing.
func (s *Store) ProcessEvent(ctx context.Context, eventID uuid.UUID, fn func(tx pgx.Tx) error) (bool, error) {
	tx, err := s.Pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer tx.Rollback(ctx)

	tag, err := tx.Exec(ctx,
		`INSERT INTO schema_rto.processed_events (event_id) VALUES ($1)
		 ON CONFLICT (event_id) DO NOTHING`, eventID)
	if err != nil {
		return false, err
	}
	if tag.RowsAffected() == 0 {
		return false, tx.Commit(ctx) // duplicate delivery: ack, no side effects
	}
	if err := fn(tx); err != nil {
		return false, err
	}
	return true, tx.Commit(ctx)
}

func (s *Store) InsertNotification(ctx context.Context, tx pgx.Tx, n *Notification) error {
	n.ID = uuid.New()
	n.CreatedAt = time.Now().UTC()
	_, err := tx.Exec(ctx,
		`INSERT INTO schema_rto.notifications (id, tenant_id, user_id, type, title, body, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		n.ID, n.TenantID, n.UserID, n.Type, n.Title, n.Body, n.CreatedAt)
	return err
}

func (s *Store) AppendSyncEvent(ctx context.Context, tx pgx.Tx, e *SyncEvent) error {
	e.OccurredAt = time.Now().UTC()
	return tx.QueryRow(ctx,
		`INSERT INTO schema_rto.sync_events (tenant_id, entity_type, entity_id, op, payload, occurred_at)
		 VALUES ($1, $2, $3, $4, $5, $6) RETURNING seq`,
		e.TenantID, e.EntityType, e.EntityID, e.Op, e.Payload, e.OccurredAt,
	).Scan(&e.Seq)
}

// SyncSince streams the change feed for a reconnecting offline client.
func (s *Store) SyncSince(ctx context.Context, tenantID uuid.UUID, cursor int64, limit int) ([]SyncEvent, error) {
	rows, err := s.Pool.Query(ctx,
		`SELECT seq, tenant_id, entity_type, entity_id, op, payload, occurred_at
		 FROM schema_rto.sync_events
		 WHERE tenant_id = $1 AND seq > $2
		 ORDER BY seq
		 LIMIT $3`, tenantID, cursor, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var events []SyncEvent
	for rows.Next() {
		var e SyncEvent
		if err := rows.Scan(&e.Seq, &e.TenantID, &e.EntityType, &e.EntityID, &e.Op, &e.Payload, &e.OccurredAt); err != nil {
			return nil, err
		}
		events = append(events, e)
	}
	return events, rows.Err()
}

func (s *Store) UpsertDeviceCursor(ctx context.Context, tenantID, userID uuid.UUID, deviceID string, cursor int64) error {
	_, err := s.Pool.Exec(ctx,
		`INSERT INTO schema_rto.devices (id, tenant_id, user_id, sync_cursor, last_seen_at)
		 VALUES ($1, $2, $3, $4, now())
		 ON CONFLICT (id) DO UPDATE
		 SET sync_cursor = GREATEST(schema_rto.devices.sync_cursor, EXCLUDED.sync_cursor),
		     last_seen_at = now()`,
		deviceID, tenantID, userID, cursor)
	return err
}

func (s *Store) MarkNotificationRead(ctx context.Context, tenantID, userID, notificationID uuid.UUID) error {
	_, err := s.Pool.Exec(ctx,
		`UPDATE schema_rto.notifications SET read_at = now()
		 WHERE id = $1 AND tenant_id = $2 AND user_id = $3 AND read_at IS NULL`,
		notificationID, tenantID, userID)
	return err
}
