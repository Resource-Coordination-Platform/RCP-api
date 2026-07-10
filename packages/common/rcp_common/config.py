"""Config helpers: common settings every RCP service must expose."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "rcp-service"
    ENVIRONMENT: str = "local"
    LOG_LEVEL: str = "INFO"
