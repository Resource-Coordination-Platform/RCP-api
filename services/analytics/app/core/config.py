from rcp_common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "analytics-service"

    # svc_analytics owns schema_analytics and holds SELECT-only grants on
    # schema_logistics (the read model) — see infra/compose/db-init.
    DATABASE_URL: str = (
        "postgresql+psycopg2://svc_analytics:analytics_local_pw@localhost:5432/rcp"
    )
    RABBITMQ_URL: str = "amqp://rcp:rcp_local_pw@localhost:5672/rcp"

    # JWT verification (issued by IAM; verified locally via cached JWKS)
    JWT_JWKS_URL: str = "http://localhost:8001/.well-known/jwks.json"
    JWT_ISSUER: str = "rcp-iam"
    JWT_AUDIENCE: str = "rcp-services"
    JWKS_CACHE_TTL_SECONDS: int = 600

    LOGISTICS_SCHEMA: str = "schema_logistics"

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
