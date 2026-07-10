package ws

import (
	"context"
	"encoding/json"
	"log/slog"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/websocket"

	"github.com/rcp-platform/services/rto/internal/store"
)

const (
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = 50 * time.Second
	maxMessageSize = 4 << 10 // volunteers send tiny control frames only
	sendBuffer     = 64
	syncBatchLimit = 500
)

type Client struct {
	TenantID uuid.UUID
	UserID   uuid.UUID

	hub   *Hub
	conn  *websocket.Conn
	store *store.Store
	send  chan []byte
}

func NewClient(hub *Hub, conn *websocket.Conn, st *store.Store, tenantID, userID uuid.UUID) *Client {
	return &Client{
		TenantID: tenantID,
		UserID:   userID,
		hub:      hub,
		conn:     conn,
		store:    st,
		send:     make(chan []byte, sendBuffer),
	}
}

// TrySend enqueues without blocking; a slow/stalled consumer gets
// disconnected rather than exerting backpressure on the hub.
func (c *Client) TrySend(message []byte) bool {
	select {
	case c.send <- message:
		return true
	default:
		c.Close()
		return false
	}
}

func (c *Client) Close() {
	c.conn.Close()
}

func (c *Client) Run() {
	c.hub.Register(c)
	go c.writePump()
	c.readPump()
}

type inboundFrame struct {
	Type           string `json:"type"`
	Cursor         int64  `json:"cursor,omitempty"`
	DeviceID       string `json:"device_id,omitempty"`
	NotificationID string `json:"notification_id,omitempty"`
}

func (c *Client) readPump() {
	defer func() {
		c.hub.Unregister(c)
		c.conn.Close()
	}()
	c.conn.SetReadLimit(maxMessageSize)
	c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	for {
		_, raw, err := c.conn.ReadMessage()
		if err != nil {
			return
		}
		var frame inboundFrame
		if err := json.Unmarshal(raw, &frame); err != nil {
			continue
		}
		switch frame.Type {
		case "sync":
			c.handleSync(frame)
		case "ack":
			c.handleAck(frame)
		}
	}
}

// handleSync serves the offline-first catch-up: stream every change the
// device missed since its cursor, then persist the new cursor.
func (c *Client) handleSync(frame inboundFrame) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	events, err := c.store.SyncSince(ctx, c.TenantID, frame.Cursor, syncBatchLimit)
	if err != nil {
		slog.Error("sync query failed", "err", err)
		return
	}
	cursor := frame.Cursor
	for _, e := range events {
		cursor = e.Seq
		payload, _ := json.Marshal(map[string]any{
			"type":        "sync_event",
			"seq":         e.Seq,
			"entity_type": e.EntityType,
			"entity_id":   e.EntityID,
			"op":          e.Op,
			"payload":     json.RawMessage(e.Payload),
			"occurred_at": e.OccurredAt,
		})
		c.TrySend(payload)
	}
	done, _ := json.Marshal(map[string]any{
		"type": "sync_complete", "cursor": cursor, "count": len(events),
	})
	c.TrySend(done)

	if frame.DeviceID != "" {
		if err := c.store.UpsertDeviceCursor(ctx, c.TenantID, c.UserID, frame.DeviceID, cursor); err != nil {
			slog.Error("cursor upsert failed", "err", err)
		}
	}
}

func (c *Client) handleAck(frame inboundFrame) {
	id, err := uuid.Parse(frame.NotificationID)
	if err != nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := c.store.MarkNotificationRead(ctx, c.TenantID, c.UserID, id); err != nil {
		slog.Error("ack failed", "err", err)
	}
}

func (c *Client) writePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()
	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, nil)
				return
			}
			if err := c.conn.WriteMessage(websocket.TextMessage, message); err != nil {
				return
			}
		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}
