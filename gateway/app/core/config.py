from rcp_common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "api-gateway"

    IAM_URL: str = "http://localhost:8001"
    LOGISTICS_URL: str = "http://localhost:8002"
    ANALYTICS_URL: str = "http://localhost:8003"
    VOLUNTEER_URL: str = "http://localhost:8004"
    # WebSocket clients connect through the gateway's /ws endpoint, which
    # proxies the upgrade to RTO (see app/ws_proxy.py); RTO still verifies
    # the bearer subprotocol itself.
    RTO_URL: str = "http://localhost:8080"

    # token bucket per client (Redis-backed when REDIS_URL is set)
    RATE_LIMIT_RPS: float = 20.0
    RATE_LIMIT_BURST: int = 60
    REDIS_URL: str = ""
    # When the gateway sits behind a load balancer / edge proxy, every
    # connection carries the LB's IP — set this to true so the limiter keys
    # on the client address the trusted hop wrote into X-Forwarded-For.
    RATE_LIMIT_TRUST_FORWARDED: bool = False

    PROXY_TIMEOUT_SECONDS: float = 30.0

    # 3000 = tenant-admin portal, 3001 = super-admin (platform operator) console
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3002"]


settings = Settings()

# Longest-prefix-wins routing table. The gateway owns *routing only*:
# no business rules, no data access, no token minting.
ROUTE_TABLE: dict[str, str] = {
    "/api/auth": settings.IAM_URL,
    "/api/admin": settings.IAM_URL,
    "/.well-known": settings.IAM_URL,
    "/api/requests": settings.LOGISTICS_URL,
    "/api/inventory": settings.LOGISTICS_URL,
    "/api/volunteers": settings.LOGISTICS_URL,
    "/api/reports": settings.ANALYTICS_URL,
    # volunteer-service (longest prefix wins, so /api/volunteers above
    # still routes to logistics' legacy operational profiles)
    "/api/volunteer": settings.VOLUNTEER_URL,
}
