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

async def get_sync_manager() -> SyncManager:
    return SyncManager(
        redis_client,
        aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {settings.get_intervals_api_key}"}
        )
    )

@app.post("/sync/intervals/user", response_model=SyncStatusResponse)
async def start_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks
):
    if not await rate_limiter.acquire(f"sync:{request.user_id}"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    sync_manager = await get_sync_manager()
    try:
        # Initialize sync status
        status = await sync_manager.update_status(
            request.user_id,
            SyncStatus.PENDING
        )
        
        # Start sync in background
        background_tasks.add_task(
            sync_manager.start_sync,
            request.user_id,
            request.start_date,
            request.end_date
        )
        
        return status
    finally:
        await sync_manager.session.close()

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
