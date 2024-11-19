from functools import cached_property
from typing import Optional

from pydantic_settings import BaseSettings
from src.secrets import get_secrets_manager


class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    INTERVALS_API_BASE_URL: str = "https://intervals.icu/api/v1"
    INTERVALS_API_KEY: Optional[str] = None
    DATA_INGESTION_SERVICE_URL: str = "http://data-ingestion-service:8080"
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_PERIOD: int = 60
    SYNC_BATCH_SIZE: int = 50
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 1
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {"env_file": ".env"}

    @cached_property
    def get_intervals_api_key(self) -> str:
        """
        Get the intervals.icu API key from Vault or environment variable.
        Vault takes precedence over environment variable.
        """
        secrets_manager = get_secrets_manager()
        vault_key = secrets_manager.get_secret("intervals_api_key")

        if vault_key:
            return vault_key

        if self.INTERVALS_API_KEY:
            # Store the environment variable in Vault for future use
            secrets_manager.set_secret("intervals_api_key", self.INTERVALS_API_KEY)
            return self.INTERVALS_API_KEY

        raise ValueError(
            "No intervals.icu API key found in Vault or environment variables"
        )


settings = Settings()
