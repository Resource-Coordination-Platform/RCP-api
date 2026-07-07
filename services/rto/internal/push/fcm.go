// Package push abstracts mobile push delivery (FCM for the Flutter app).
package push

import (
	"context"
	"log"

	"github.com/google/uuid"
)

type Sender interface {
	Send(ctx context.Context, tenantID, userID uuid.UUID, title string, data []byte)
}

// LogSender is the local/dev implementation. Production wires an FCM
// client (firebase.google.com/go/v4/messaging) behind the same interface,
// looking up device push tokens from schema_rto.devices.
type LogSender struct{}

func (LogSender) Send(_ context.Context, tenantID, userID uuid.UUID, title string, _ []byte) {
	log.Printf("push (dev log only): tenant=%s user=%s title=%q", tenantID, userID, title)
}
