# Configure logging
import logging

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import UploadRequest, UploadStatusResponse
from src.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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


@app.post("/activities", response_model=UploadStatusResponse)
async def start_upload(request: UploadRequest, background_tasks: BackgroundTasks, fit_file: UploadFile = File(...)):
    pass

@app.get("/activities/{activity_id}/status", response_model=UploadStatusResponse)
async def get_upload_status(activity_id: str):
    status_key = f"status:{activity_id}"
    status = await redis_client.hgetall(status_key)

    if not status:
        raise HTTPException(status_code=404, detail="Activity not found")

    return UploadStatusResponse(
        activity_id=activity_id,
        status=status["status"],
        error_message=status.get("error_message", ""),
        # TODO: fill in the rest of the fields
    )
