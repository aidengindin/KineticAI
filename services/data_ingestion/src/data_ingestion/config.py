from functools import lru_cache
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_PERIOD: int = 60
    SYNC_BATCH_SIZE: int = 50
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 1
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["*"]
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/dbname"  # TODO: fill in the correct database URL
    SQL_ECHO: bool = False

    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{os.getenv('ENV_NAME', 'development')}"),
        env_file_encoding="utf-8",
        extra="allow",
    )

class DevelopmentSettings(Settings):
    DATABASE_URL: str = "postgresql+asyncpg://dev_user:password@localhost:5432/dev_db"
    SQL_ECHO: bool = True
    LOG_LEVEL: str = "DEBUG"

class ProductionSettings(Settings):
    DATABASE_URL: str = None  # must be set in via environment variable
    SQL_ECHO: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = []  # must be set via environment variable

class TestSettings(Settings):
    DATABASE_URL: str = "postgresql+asyncpg://test_user:password@localhost:5432/test_db"
    SQL_ECHO: bool = True
    LOG_LEVEL: str = "DEBUG"

ENV_SETTINGS_MAP = {
    "development": DevelopmentSettings,
    "production": ProductionSettings,
    "test": TestSettings,
}

@lru_cache
def get_settings() -> Settings:
    env_name = os.getenv("ENV_NAME", "development")
    settings_class = ENV_SETTINGS_MAP.get(env_name, Settings)
    return settings_class()
