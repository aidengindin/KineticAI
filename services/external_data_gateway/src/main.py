from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from prometheus_client import make_asgi_app
import logging
import aiohttp
from src.config import settings
from src.models import SyncRequest, SyncStatus, SyncStatusResponse
from src.sync import SyncManager
from src.rate_limiter import RateLimiter
import argparse
import uvicorn

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="External Data Gateway")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Initialize Redis client
redis_client = Redis.from_url(settings.REDIS_URL)

# Initialize rate limiter
rate_limiter = RateLimiter(redis_client)

@app.post("/sync/intervals/user", response_model=SyncStatusResponse)
async def start_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks
):
    """Start a synchronization process for external data.
    This function initiates a background synchronization task for a specific user
    within a given date range. It implements rate limiting to prevent excessive
    synchronization requests from the same user.
    Args:
        request (SyncRequest): The synchronization request containing user_id,
            start_date, and end_date.
        background_tasks (BackgroundTasks): FastAPI background tasks handler for
            running the sync process asynchronously.
    Returns:
        dict: The initial sync status information.
    Raises:
        HTTPException: If the rate limit for the user has been exceeded (status 429).
    Note:
        The actual synchronization runs as a background task while the function
        returns immediately with the initial sync status.
    """
    if not await rate_limiter.acquire(f"sync:{request.user_id}"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    async def run_sync():
        async with SyncManager(redis_client) as sync_manager:
            await sync_manager.start_sync(
                request.user_id,
                request.start_date,
                request.end_date
            )

    # Initialize status with new manager
    async with SyncManager(redis_client) as sync_manager:
        status = await sync_manager.update_status(
            request.user_id,
            SyncStatus.PENDING
        )
        background_tasks.add_task(run_sync)
        return status


@app.get("/sync/status/{user_id}", response_model=SyncStatusResponse)
async def get_sync_status(user_id: str):
    async with SyncManager(redis_client) as sync_manager:
        return await sync_manager.get_status(user_id)

@app.get("/health")
async def health_check():
    try:
        redis_client.ping()
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Run the External Data Gateway API")
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    parser.add_argument('--log-level', type=str, default='debug', help='Log level for the server')

    args = parser.parse_args()

    uvicorn.run(
        "src.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level
    )
