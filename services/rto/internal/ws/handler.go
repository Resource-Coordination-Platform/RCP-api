package ws

import (
	"net/http"
	"strings"

	"github.com/gorilla/websocket"

	"github.com/rcp-platform/services/rto/internal/auth"
	"github.com/rcp-platform/services/rto/internal/store"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	// tighten in production to the web-admin / app origins
	CheckOrigin: func(r *http.Request) bool { return true },
}

// tokenFromSubprotocol extracts the JWT from Sec-WebSocket-Protocol:
// the client requests protocols ["bearer", "<jwt>"]. The token never
// appears in the URL, so it can't leak into proxy or access logs.
func tokenFromSubprotocol(r *http.Request) string {
	header := r.Header.Get("Sec-WebSocket-Protocol")
	parts := strings.Split(header, ",")
	if len(parts) >= 2 && strings.TrimSpace(parts[0]) == "bearer" {
		return strings.TrimSpace(parts[1])
	}
	return ""
}

func Handler(hub *Hub, verifier *auth.Verifier, st *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token := tokenFromSubprotocol(r)
		if token == "" {
			http.Error(w, "missing bearer subprotocol", http.StatusUnauthorized)
			return
		}
		claims, err := verifier.Verify(token)
		if err != nil {
			http.Error(w, "invalid token", http.StatusUnauthorized)
			return
		}

		// echo the accepted subprotocol back, as RFC 6455 requires
		responseHeader := http.Header{"Sec-WebSocket-Protocol": {"bearer"}}
		conn, err := upgrader.Upgrade(w, r, responseHeader)
		if err != nil {
			return
		}
		NewClient(hub, conn, st, claims.TenantID, claims.UserID).Run()
	}
}
