package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os/signal"
	"syscall"

	"github.com/rcp-platform/services/rto/internal/auth"
	"github.com/rcp-platform/services/rto/internal/config"
	"github.com/rcp-platform/services/rto/internal/consumer"
	"github.com/rcp-platform/services/rto/internal/push"
	"github.com/rcp-platform/services/rto/internal/store"
	"github.com/rcp-platform/services/rto/internal/ws"
)

func main() {
	cfg := config.Load()
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
    
	//Database connection
	st, err := store.New(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("database: %v", err)
	}
	if err := st.EnsureSchema(ctx); err != nil {
		log.Fatalf("schema: %v", err)
	}

	//JWT Authentication/IAM
	verifier := auth.NewVerifier(cfg.JWKSURL, cfg.JWTIssuer, cfg.JWTAudience)
	if err := verifier.Warm(); err != nil {
		// non-fatal: IAM may still be booting; the cache refreshes on demand
		log.Printf("jwks warm-up failed (will retry on demand): %v", err)
	}
    
	//Real time engine (websocker and rabbitMQ activation)
	hub := ws.NewHub()

	go consumer.New(cfg, st, hub, verifier, push.LogSender{}).Run(ctx)
	
	//HTTP Api (Routing)
	mux := http.NewServeMux()
	mux.HandleFunc("/ws", ws.Handler(hub, verifier, st))
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok", "service": "rto-service"})
	})

	//start web server
	server := &http.Server{Addr: cfg.ListenAddr, Handler: mux}
	go func() {
		<-ctx.Done()
		server.Shutdown(context.Background())
	}()

	log.Printf("rto listening on %s", cfg.ListenAddr)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("server: %v", err)
	}
}
