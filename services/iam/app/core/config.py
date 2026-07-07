from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "iam-service"
    ENVIRONMENT: str = "local"

    DATABASE_URL: str = "postgresql+psycopg2://svc_iam:iam_local_pw@localhost:5432/rcp"
    RABBITMQ_URL: str = "amqp://rcp:rcp_local_pw@localhost:5672/rcp"

    JWT_PRIVATE_KEY_PATH: str = "../../infra/compose/secrets/jwt_dev_key.pem"
    JWT_ISSUER: str = "rcp-iam"
    JWT_AUDIENCE: str = "rcp-services"
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 14

    # local convenience: create tables on boot; prod uses Alembic migrations
    AUTO_CREATE_TABLES: bool = True

    EVENTS_EXCHANGE: str = "rcp.events"


settings = Settings()
