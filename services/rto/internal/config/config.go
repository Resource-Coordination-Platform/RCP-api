package config

import (
	"log/slog"
	"os"
	"strings"

	"github.com/joho/godotenv"
)

type Config struct {
	ListenAddr  string
	DatabaseURL string
	RabbitMQURL string

	JWKSURL     string
	JWTIssuer   string
	JWTAudience string

	EventsExchange string
	DLXExchange    string
	Queue          string
	DLQ            string

	// Origins allowed to open WebSocket connections (comma-separated).
	// Empty = allow any origin, acceptable for local development only;
	// production must list the web-admin / app origins.
	WSAllowedOrigins []string
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func Load() Config {
	if err := godotenv.Load(); err != nil {
		slog.Info("no .env file found; using process environment", "err", err)
	}
	return Config{
		ListenAddr:  getenv("LISTEN_ADDR", ":8080"),
		DatabaseURL: getenv("DATABASE_URL", "postgres://svc_rto:rto_local_pw@localhost:5432/rcp"),
		RabbitMQURL: getenv("RABBITMQ_URL", "amqp://rcp:rcp_local_pw@localhost:5672/rcp"),

		JWKSURL:     getenv("JWT_JWKS_URL", "http://localhost:8001/.well-known/jwks.json"),
		JWTIssuer:   getenv("JWT_ISSUER", "rcp-iam"),
		JWTAudience: getenv("JWT_AUDIENCE", "rcp-services"),

		EventsExchange: getenv("EVENTS_EXCHANGE", "rcp.events"),
		DLXExchange:    getenv("DLX_EXCHANGE", "rcp.dlx"),
		Queue:          getenv("EVENTS_QUEUE", "rto.domain-events.q"),
		DLQ:            getenv("EVENTS_DLQ", "dlq.rto.domain-events"),

		WSAllowedOrigins: splitCSV(os.Getenv("WS_ALLOWED_ORIGINS")),
	}
}

func splitCSV(v string) []string {
	if v == "" {
		return nil
	}
	var out []string
	for _, part := range strings.Split(v, ",") {
		if trimmed := strings.TrimSpace(part); trimmed != "" {
			out = append(out, trimmed)
		}
	}
	return out
}
