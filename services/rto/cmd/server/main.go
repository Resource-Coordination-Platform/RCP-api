package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
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
	// structured JSON logging, matching the Python services
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)).With("service", "rto-service"))

	cfg := config.Load()
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	//Database connection
	st, err := store.New(ctx, cfg.DatabaseURL)
	if err != nil {
		slog.Error("database", "err", err)
		os.Exit(1)
	}
	if err := st.EnsureSchema(ctx); err != nil {
		slog.Error("schema", "err", err)
		os.Exit(1)
	}

	//JWT Authentication/IAM
	verifier := auth.NewVerifier(cfg.JWKSURL, cfg.JWTIssuer, cfg.JWTAudience)
	if err := verifier.Warm(); err != nil {
		// non-fatal: IAM may still be booting; the cache refreshes on demand
		slog.Warn("jwks warm-up failed (will retry on demand)", "err", err)
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

	slog.Info("rto listening", "addr", cfg.ListenAddr)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		slog.Error("server", "err", err)
		os.Exit(1)
	}
}
