from rcp_common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "analytics-service"

    # svc_analytics owns schema_analytics; its read models are fed by
    # logistics events over RabbitMQ (no cross-schema access).
    DATABASE_URL: str = (
        "postgresql+psycopg2://svc_analytics:analytics_local_pw@localhost:5432/rcp"
    )
    RABBITMQ_URL: str = "amqp://rcp:rcp_local_pw@localhost:5672/rcp"
    EVENTS_EXCHANGE: str = "rcp.events"
    DLX_EXCHANGE: str = "rcp.dlx"

    # JWT verification (issued by IAM; verified locally via cached JWKS)
    JWT_JWKS_URL: str = "http://localhost:8001/.well-known/jwks.json"
    JWT_ISSUER: str = "rcp-iam"
    JWT_AUDIENCE: str = "rcp-services"
    JWKS_CACHE_TTL_SECONDS: int = 600

settings = Settings()
