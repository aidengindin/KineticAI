from functools import lru_cache
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["*"]
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/dbname"
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
    DATABASE_URL: str = None  # must be set via environment variable
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