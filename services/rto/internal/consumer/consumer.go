// Package consumer drains rto.domain-events.q (quorum queue) and turns
// domain events into notifications, sync-feed rows, live WS frames, and
// push fan-out. Manual ack after commit; failures dead-letter to the DLQ.
package consumer

import (
	"context"
	"encoding/json"
	"log/slog"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	amqp "github.com/rabbitmq/amqp091-go"

	"github.com/rcp-platform/services/rto/internal/auth"
	"github.com/rcp-platform/services/rto/internal/config"
	"github.com/rcp-platform/services/rto/internal/push"
	"github.com/rcp-platform/services/rto/internal/store"
	"github.com/rcp-platform/services/rto/internal/ws"
)

const (
	prefetch       = 32
	reconnectSleep = 2 * time.Second
)

var bindings = []string{"logistics.#", "iam.user.deactivated", "iam.token.revoked", "iam.tenant.deactivated", "iam.tenant.status_changed"}

type envelope struct {
	EventID       string          `json:"event_id"`
	EventType     string          `json:"event_type"`
	SchemaVersion int             `json:"schema_version"`
	OccurredAt    time.Time       `json:"occurred_at"`
	TenantID      string          `json:"tenant_id"`
	Producer      string          `json:"producer"`
	TraceID       string          `json:"trace_id"`
	Data          json.RawMessage `json:"data"`
}

type Consumer struct {
	cfg      config.Config
	store    *store.Store
	hub      *ws.Hub
	verifier *auth.Verifier
	pusher   push.Sender
}

func New(cfg config.Config, st *store.Store, hub *ws.Hub, verifier *auth.Verifier, pusher push.Sender) *Consumer {
	return &Consumer{cfg: cfg, store: st, hub: hub, verifier: verifier, pusher: pusher}
}

func (c *Consumer) declareTopology(ch *amqp.Channel) error {
	if err := ch.ExchangeDeclare(c.cfg.EventsExchange, "topic", true, false, false, false, nil); err != nil {
		return err
	}
	if err := ch.ExchangeDeclare(c.cfg.DLXExchange, "topic", true, false, false, false, nil); err != nil {
		return err
	}
	if _, err := ch.QueueDeclare(c.cfg.Queue, true, false, false, false, amqp.Table{
		"x-queue-type":           "quorum",
		"x-dead-letter-exchange": c.cfg.DLXExchange,
	}); err != nil {
		return err
	}
	if _, err := ch.QueueDeclare(c.cfg.DLQ, true, false, false, false, nil); err != nil {
		return err
	}
	if err := ch.QueueBind(c.cfg.DLQ, "#", c.cfg.DLXExchange, false, nil); err != nil {
		return err
	}
	for _, binding := range bindings {
		if err := ch.QueueBind(c.cfg.Queue, binding, c.cfg.EventsExchange, false, nil); err != nil {
			return err
		}
	}
	return nil
}

// Run blocks, reconnecting forever until ctx is cancelled.
func (c *Consumer) Run(ctx context.Context) {
	for ctx.Err() == nil {
		if err := c.consumeOnce(ctx); err != nil {
			slog.Warn("consumer disconnected; retrying", "err", err)
		}
		select {
		case <-ctx.Done():
		case <-time.After(reconnectSleep):
		}
	}
}

func (c *Consumer) consumeOnce(ctx context.Context) error {
	conn, err := amqp.Dial(c.cfg.RabbitMQURL)
	if err != nil {
		return err
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		return err
	}
	defer ch.Close()

	if err := c.declareTopology(ch); err != nil {
		return err
	}
	if err := ch.Qos(prefetch, 0, false); err != nil {
		return err
	}
	deliveries, err := ch.Consume(c.cfg.Queue, "rto", false, false, false, false, nil)
	if err != nil {
		return err
	}
	slog.Info("consuming", "queue", c.cfg.Queue)

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case delivery, ok := <-deliveries:
			if !ok {
				return amqp.ErrClosed
			}
			if err := c.handle(ctx, delivery.Body); err != nil {
				slog.Error("event failed, dead-lettering", "err", err)
				delivery.Nack(false, false) // -> DLQ via the queue's DLX
			} else {
				delivery.Ack(false)
			}
		}
	}
}

func (c *Consumer) handle(ctx context.Context, body []byte) error {
	var env envelope
	if err := json.Unmarshal(body, &env); err != nil {
		return err
	}
	eventID, err := uuid.Parse(env.EventID)
	if err != nil {
		return err
	}
	var tenantID uuid.UUID
	if env.TenantID != "" && env.TenantID != "null" {
		tenantID, _ = uuid.Parse(env.TenantID)
	}

	switch env.EventType {
	case "logistics.task.assigned":
		return c.onTaskAssigned(ctx, eventID, tenantID, env)
	case "iam.user.deactivated", "iam.token.revoked":
		return c.onRevocation(tenantID, env)
	case "iam.tenant.deactivated", "iam.tenant.status_changed":
		return c.onTenantDeactivated(tenantID, env)
	default:
		// every other logistics event feeds the offline sync log
		return c.onGenericDomainEvent(ctx, eventID, tenantID, env)
	}
}

func (c *Consumer) onTaskAssigned(ctx context.Context, eventID, tenantID uuid.UUID, env envelope) error {
	var data struct {
		TaskID    string `json:"task_id"`
		Title     string `json:"title"`
		Volunteer struct {
			UserID string `json:"user_id"`
		} `json:"volunteer"`
	}
	if err := json.Unmarshal(env.Data, &data); err != nil {
		return err
	}
	volunteerID, err := uuid.Parse(data.Volunteer.UserID)
	if err != nil {
		return err
	}

	notification := &store.Notification{
		TenantID: tenantID,
		UserID:   volunteerID,
		Type:     "task_assigned",
		Title:    "New task: " + data.Title,
		Body:     env.Data,
	}
	fresh, err := c.store.ProcessEvent(ctx, eventID, func(tx pgx.Tx) error {
		if err := c.store.InsertNotification(ctx, tx, notification); err != nil {
			return err
		}
		return c.store.AppendSyncEvent(ctx, tx, &store.SyncEvent{
			TenantID:   tenantID,
			EntityType: "task",
			EntityID:   data.TaskID,
			Op:         "assigned",
			Payload:    env.Data,
		})
	})
	if err != nil || !fresh {
		return err
	}

	// live delivery (best-effort, outside the transaction)
	frame, _ := json.Marshal(map[string]any{
		"type":            "notification",
		"notification_id": notification.ID,
		"event_type":      env.EventType,
		"title":           notification.Title,
		"data":            json.RawMessage(env.Data),
	})
	delivered := c.hub.SendToUser(tenantID, volunteerID, frame)
	if !delivered {
		// no live socket -> push notification for the Flutter client
		c.pusher.Send(ctx, tenantID, volunteerID, notification.Title, env.Data)
	}
	return nil
}

func (c *Consumer) onGenericDomainEvent(ctx context.Context, eventID, tenantID uuid.UUID, env envelope) error {
	var probe struct {
		TaskID    string `json:"task_id"`
		RequestID string `json:"request_id"`
	}
	_ = json.Unmarshal(env.Data, &probe)
	entityType, entityID := "event", env.EventID
	if probe.TaskID != "" {
		entityType, entityID = "task", probe.TaskID
	} else if probe.RequestID != "" {
		entityType, entityID = "request", probe.RequestID
	}

	fresh, err := c.store.ProcessEvent(ctx, eventID, func(tx pgx.Tx) error {
		return c.store.AppendSyncEvent(ctx, tx, &store.SyncEvent{
			TenantID:   tenantID,
			EntityType: entityType,
			EntityID:   entityID,
			Op:         env.EventType,
			Payload:    env.Data,
		})
	})
	if err != nil || !fresh {
		return err
	}

	frame, _ := json.Marshal(map[string]any{
		"type":       "domain_event",
		"event_type": env.EventType,
		"data":       json.RawMessage(env.Data),
	})
	c.hub.BroadcastTenant(tenantID, frame)
	return nil
}

func (c *Consumer) onRevocation(tenantID uuid.UUID, env envelope) error {
	var data struct {
		UserID string `json:"user_id"`
		JTI    string `json:"jti"`
	}
	if err := json.Unmarshal(env.Data, &data); err != nil {
		return err
	}
	// deny until any token issued before now has certainly expired
	until := time.Now().Add(30 * time.Minute)
	if data.UserID != "" {
		if userID, err := uuid.Parse(data.UserID); err == nil {
			c.verifier.DenyUser(userID, until)
			c.hub.DropUser(tenantID, userID)
		}
	}
	if data.JTI != "" {
		c.verifier.DenyJTI(data.JTI, until)
	}
	return nil
}

func (c *Consumer) onTenantDeactivated(tenantID uuid.UUID, env envelope) error {
	var data struct {
		Status string `json:"status"`
	}
	_ = json.Unmarshal(env.Data, &data)
	if data.Status != "active" {
		c.hub.DropTenant(tenantID)
	}
	return nil
}
