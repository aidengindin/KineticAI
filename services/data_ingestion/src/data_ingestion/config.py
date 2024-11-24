from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_PERIOD: int = 60
    SYNC_BATCH_SIZE: int = 50
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 1
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {"env_file": ".env"}
