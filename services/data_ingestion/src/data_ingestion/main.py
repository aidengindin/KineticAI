# Configure logging
import argparse
from datetime import datetime
import json
import logging
from typing import Optional
import uuid

from data_ingestion.db.activities import ActivityRepository
from data_ingestion.db.database import get_db
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fitparse import FitFile
from prometheus_client import make_asgi_app
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from data_ingestion.models import ActivityStatusResponse, UploadRequest, UploadStatus, UploadStatusResponse
from data_ingestion.config import get_settings
import uvicorn

settings = get_settings()

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Data Ingestion Service")

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


async def get_activity_repository(db: AsyncSession = Depends(get_db)) -> ActivityRepository:
    return ActivityRepository(db)

@app.post("/activities", response_model=UploadStatusResponse)
async def start_upload(
    request: UploadRequest,
    background_tasks: BackgroundTasks,
    repository: ActivityRepository = Depends(get_activity_repository),
    fit_files: list[UploadFile] = File(...)
) -> UploadStatusResponse:
    num_tasks = 3
    batch_id = str(uuid.uuid4())

    batch_status = UploadStatusResponse(
        batch_id=batch_id,
        status=UploadStatus.PENDING,
        total_activities=len(request.activities),
        processed_activities=0,
        failed_activities=0,
        last_updated=datetime.now(),
    )
    await redis_client.set(f"batch:{batch_id}", json.dumps(batch_status.model_dump()))

    for activity, file in zip(request.activities, fit_files):
        activity_status = ActivityStatusResponse(
            activity_id=activity.id,
            status=UploadStatus.PENDING,
            last_updated=datetime.now(),
            completed_tasks=0,
        )
        await redis_client.set(f"activity:{activity.id}", json.dumps(activity_status.model_dump()))

        file_content = await file.read()
        fit_file = FitFile(file_content)

        await update_activity_status(activity.id, UploadStatus.IN_PROGRESS)

        background_tasks.add_task(
            process_with_status,
            repository.create_activity,
            activity.id,
            num_tasks,
            activity,
            file_content,
        )
        background_tasks.add_task(
            process_with_status,
            repository.store_laps,
            activity.id,
            num_tasks,
            activity.id,
            fit_file,
        )
        background_tasks.add_task(
            process_with_status,
            repository.store_streams,
            activity.id,
            num_tasks,
            activity.id,
            fit_file,
        )

    return batch_status

async def update_activity_status(
    activity_id: str,
    status: UploadStatus,
    error: Optional[str] = None
) -> None:
    key = f"activity:{activity_id}"
    current = await redis_client.get(key)
    if current:
        current_status = json.loads(current)
        current_status["status"] = status.value
        if error:
            current_status["error"] = error
        current_status["last_updated"] = datetime.now().isoformat()
        await redis_client.set(key, json.dumps(current_status))

# TODO: handle batch status updates
async def increment_completed_tasks(activity_id: str, num_tasks: int):
    key = f"activity:{activity_id}"
    current = await redis_client.get(key)
    if current:
        current_status = json.loads(current)
        pipe = redis_client.pipeline()
        pipe.hincrby(key, "completed_tasks", 1)
        pipe.hget(key, "completed_tasks")
        completed = (await pipe.execute())[1]
        if int(completed) == num_tasks:
            current_status["status"] = UploadStatus.COMPLETED.value
        current_status["last_updated"] = datetime.now().isoformat()
        await redis_client.set(key, json.dumps(current_status))

async def process_with_status(task_func, activity_id: str, num_tasks: int, *args, **kwargs):
    try:
        await task_func(*args, **kwargs)
        await increment_completed_tasks(activity_id, num_tasks)
    except Exception as e:
        await update_activity_status(
            activity_id,
            UploadStatus.FAILED,
            str(e),
        )
        logging.error(f"Failed to process activity {activity_id}: {str(e)}")
        raise

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
