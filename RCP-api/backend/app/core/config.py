from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Resource Coordination Platform"
    DEBUG: bool = False

    DATABASE_URL: str = (
        "postgresql+psycopg2://rcp_user:rcp_password@localhost:5432/rcp_db"
    )

    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
