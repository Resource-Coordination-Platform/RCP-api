// Package ws implements the per-tenant WebSocket hub. Connections are
// grouped tenant -> user -> sockets so a frame can never cross tenants.
package ws

import (
	"encoding/json"
	"sync"

	"github.com/google/uuid"
)

type Hub struct {
	mu    sync.RWMutex
	conns map[uuid.UUID]map[uuid.UUID]map[*Client]struct{}
}

func NewHub() *Hub {
	return &Hub{conns: map[uuid.UUID]map[uuid.UUID]map[*Client]struct{}{}}
}

func (h *Hub) Register(c *Client) {
	h.mu.Lock()
	defer h.mu.Unlock()
	tenants, ok := h.conns[c.TenantID]
	if !ok {
		tenants = map[uuid.UUID]map[*Client]struct{}{}
		h.conns[c.TenantID] = tenants
	}
	users, ok := tenants[c.UserID]
	if !ok {
		users = map[*Client]struct{}{}
		tenants[c.UserID] = users
	}
	users[c] = struct{}{}
}

func (h *Hub) Unregister(c *Client) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if users, ok := h.conns[c.TenantID]; ok {
		if sockets, ok := users[c.UserID]; ok {
			delete(sockets, c)
			if len(sockets) == 0 {
				delete(users, c.UserID)
			}
		}
		if len(users) == 0 {
			delete(h.conns, c.TenantID)
		}
	}
}

// SendToUser returns true if at least one live socket received the frame.
func (h *Hub) SendToUser(tenantID, userID uuid.UUID, message []byte) bool {
	h.mu.RLock()
	defer h.mu.RUnlock()
	delivered := false
	if users, ok := h.conns[tenantID]; ok {
		for c := range users[userID] {
			if c.TrySend(message) {
				delivered = true
			}
		}
	}
	return delivered
}

func (h *Hub) BroadcastTenant(tenantID uuid.UUID, message []byte) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	for _, sockets := range h.conns[tenantID] {
		for c := range sockets {
			c.TrySend(message)
		}
	}
}

// DropUser force-closes every socket of a user (deactivation/revocation).
func (h *Hub) DropUser(tenantID, userID uuid.UUID) {
	h.mu.RLock()
	var victims []*Client
	if users, ok := h.conns[tenantID]; ok {
		for c := range users[userID] {
			victims = append(victims, c)
		}
	}
	h.mu.RUnlock()

	logoutMsg, _ := json.Marshal(map[string]any{
		"type":   "force_logout",
		"reason": "account_disabled",
	})

	for _, c := range victims {
		c.TrySend(logoutMsg)
		c.Close()
	}
}

// DropTenant force-closes every socket of all users in a tenant (tenant suspension/deactivation).
func (h *Hub) DropTenant(tenantID uuid.UUID) {
	h.mu.RLock()
	var victims []*Client
	if users, ok := h.conns[tenantID]; ok {
		for _, sockets := range users {
			for c := range sockets {
				victims = append(victims, c)
			}
		}
	}
	h.mu.RUnlock()

	logoutMsg, _ := json.Marshal(map[string]any{
		"type":   "force_logout",
		"reason": "tenant_suspended",
	})

	for _, c := range victims {
		c.TrySend(logoutMsg)
		c.Close()
	}
}
