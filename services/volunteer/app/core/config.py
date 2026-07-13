from rcp_common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "volunteer-service"

    DATABASE_URL: str = (
        "postgresql+psycopg2://svc_volunteer:volunteer_local_pw@localhost:5432/rcp"
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
    # replication of global users out of IAM
    IAM_EVENTS_QUEUE: str = "volunteer.iam-events.q"
    IAM_EVENTS_DLQ: str = "dlq.volunteer.iam-events"
    # disaster declarations (own events consumed asynchronously + any other
    # producer, e.g. logistics, declaring a disaster)
    DISASTER_EVENTS_QUEUE: str = "volunteer.disaster-events.q"
    DISASTER_EVENTS_DLQ: str = "dlq.volunteer.disaster-events"

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
