package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/rcp-platform/services/rto/internal/auth"
	"github.com/rcp-platform/services/rto/internal/config"
	"github.com/rcp-platform/services/rto/internal/consumer"
	"github.com/rcp-platform/services/rto/internal/push"
	"github.com/rcp-platform/services/rto/internal/store"
	"github.com/rcp-platform/services/rto/internal/ws"
)

var (
	requestTotal         atomic.Int64
	requestDurationNanos atomic.Int64
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
	mux.HandleFunc("/ws", observe("/ws", func(w http.ResponseWriter, r *http.Request) {
		ws.Handler(hub, verifier, st)(w, r)
	}))
	mux.HandleFunc("/health", observe("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok", "service": "rto-service"})
	}))
	mux.HandleFunc("/liveness", observe("/liveness", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok", "service": "rto-service"})
	}))
	mux.HandleFunc("/readiness", observe("/readiness", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		w.Header().Set("Content-Type", "application/json")
		if err := st.Pool.Ping(ctx); err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]any{
				"status": "degraded",
				"service": "rto-service",
				"checks":  map[string]string{"database": "unavailable"},
			})
			return
		}
		json.NewEncoder(w).Encode(map[string]any{
			"status": "ok",
			"service": "rto-service",
			"checks":  map[string]string{"database": "ok"},
		})
	}))
	mux.HandleFunc("/metrics", func(w http.ResponseWriter, _ *http.Request) {
		stat := st.Pool.Stat()
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		fmt.Fprintf(w, "# HELP rcp_requests_total Total HTTP requests handled.\n")
		fmt.Fprintf(w, "# TYPE rcp_requests_total counter\n")
		fmt.Fprintf(w, "rcp_requests_total{service=\"rto-service\"} %d\n", requestTotal.Load())
		fmt.Fprintf(w, "# HELP rcp_request_duration_seconds_total Total request duration in seconds.\n")
		fmt.Fprintf(w, "# TYPE rcp_request_duration_seconds_total counter\n")
		fmt.Fprintf(w, "rcp_request_duration_seconds_total{service=\"rto-service\"} %.6f\n", float64(requestDurationNanos.Load())/1e9)
		fmt.Fprintf(w, "# HELP rcp_database_connections Number of currently checked-out DB connections.\n")
		fmt.Fprintf(w, "# TYPE rcp_database_connections gauge\n")
		fmt.Fprintf(w, "rcp_database_connections{service=\"rto-service\"} %d\n", stat.AcquiredConns())
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

func observe(path string, handler http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		recorder := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		handler(recorder, r)
		requestTotal.Add(1)
		requestDurationNanos.Add(time.Since(started).Nanoseconds())
	}
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(status int) {
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}
