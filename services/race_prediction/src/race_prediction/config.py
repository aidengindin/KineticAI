from functools import lru_cache
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["*"]

class DevelopmentSettings(Settings):
    LOG_LEVEL: str = "DEBUG"

class ProductionSettings(Settings):
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = []

class TestSettings(Settings):
    LOG_LEVEL: str = "DEBUG"

@lru_cache
def get_settings() -> Settings:
    env_name = os.getenv("ENV_NAME", "development")
    settings_class = {
        "development": DevelopmentSettings,
        "production": ProductionSettings,
        "test": TestSettings,
    }.get(env_name, Settings)
    return settings_class()
