from rcp_common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "logistics-service"

    DATABASE_URL: str = (
        "postgresql+psycopg2://svc_logistics:logistics_local_pw@localhost:5432/rcp"
    )
    RABBITMQ_URL: str = "amqp://rcp:rcp_local_pw@localhost:5672/rcp"

    # JWT verification (issued by IAM; verified locally via cached JWKS)
    JWT_JWKS_URL: str = "http://localhost:8001/.well-known/jwks.json"
    JWT_ISSUER: str = "rcp-iam"
    JWT_AUDIENCE: str = "rcp-services"
    JWKS_CACHE_TTL_SECONDS: int = 600

    AUTO_CREATE_TABLES: bool = True

    EVENTS_EXCHANGE: str = "rcp.events"
    DLX_EXCHANGE: str = "rcp.dlx"
    IAM_EVENTS_QUEUE: str = "logistics.iam-events.q"
    IAM_EVENTS_DLQ: str = "dlq.logistics.iam-events"

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
