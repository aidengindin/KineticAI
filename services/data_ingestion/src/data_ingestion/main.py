# Configure logging
import argparse
import logging

from data_ingestion.db.database import get_db
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from data_ingestion.models import UploadRequest, UploadStatusResponse
from data_ingestion.config import settings
import uvicorn

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
async def start_upload(
    request: UploadRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    fit_file: UploadFile = File(...)
):
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the server on")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", type=str, default="info", help="Logging level")

    args = parser.parse_args()

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
