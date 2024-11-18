import time
from typing import Optional

from redis import Redis
from src.config import settings


class RateLimiter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.requests = settings.RATE_LIMIT_REQUESTS
        self.period = settings.RATE_LIMIT_PERIOD

    async def acquire(self, key: str) -> bool:
        pipe = self.redis.pipeline()
        now = time.time()
        window_key = f"{key}:{int(now)}"

        pipe.incr(window_key)
        pipe.expire(window_key, self.period)
        current_requests = pipe.execute()[0]

        if current_requests <= self.requests:
            return True
        return False
