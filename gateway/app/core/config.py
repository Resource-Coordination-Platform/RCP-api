from rcp_common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "api-gateway"

    IAM_URL: str = "http://localhost:8001"
    LOGISTICS_URL: str = "http://localhost:8002"
    ANALYTICS_URL: str = "http://localhost:8003"
    VOLUNTEER_URL: str = "http://localhost:8004"
    # WebSocket clients connect to RTO directly (ws:// upgrade is not proxied here)
    RTO_URL: str = "http://localhost:8080"

    # simple in-memory token bucket, per client IP
    RATE_LIMIT_RPS: float = 20.0
    RATE_LIMIT_BURST: int = 60
    REDIS_URL: str = ""

    PROXY_TIMEOUT_SECONDS: float = 30.0

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()

# Longest-prefix-wins routing table. The gateway owns *routing only*:
# no business rules, no data access, no token minting.
ROUTE_TABLE: dict[str, str] = {
    "/api/auth": settings.IAM_URL,
    "/.well-known": settings.IAM_URL,
    "/api/requests": settings.LOGISTICS_URL,
    "/api/inventory": settings.LOGISTICS_URL,
    "/api/volunteers": settings.LOGISTICS_URL,
    "/api/reports": settings.ANALYTICS_URL,
    # volunteer-service (longest prefix wins, so /api/volunteers above
    # still routes to logistics' legacy operational profiles)
    "/api/volunteer": settings.VOLUNTEER_URL,
}
