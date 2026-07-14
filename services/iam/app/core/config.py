from rcp_common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "iam-service"

    DATABASE_URL: str = "postgresql+psycopg2://svc_iam:iam_local_pw@localhost:5432/rcp"
    RABBITMQ_URL: str = "amqp://rcp:rcp_local_pw@localhost:5672/rcp"

    JWT_PRIVATE_KEY_PATH: str = "../../infra/compose/secrets/jwt_dev_key.pem"
    JWT_ISSUER: str = "rcp-iam"
    JWT_AUDIENCE: str = "rcp-services"
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 14

    # Alembic migrations are the source of truth for the schema. create_all
    # on boot is a local-only convenience — opt in via the environment
    # (docker-compose sets it) so a missing migration can never hide.
    AUTO_CREATE_TABLES: bool = False

    EVENTS_EXCHANGE: str = "rcp.events"


settings = Settings()
