import argparse
from datetime import datetime
import json
import logging
from typing import Optional, Any
import uuid

from data_ingestion.db.activities import ActivityRepository
from data_ingestion.db.database import get_db
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fitparse import FitFile
from prometheus_client import make_asgi_app
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from data_ingestion.models import ActivityStatusResponse, UploadRequest, UploadStatus, UploadStatusResponse
from data_ingestion.config import get_settings

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def json_dumps(obj: Any) -> str:
    """Helper function to serialize objects with datetime support."""
    return json.dumps(obj, cls=DateTimeEncoder)

async def get_activity_repository(db: AsyncSession = Depends(get_db)) -> ActivityRepository:
    return ActivityRepository(db)

def create_app(redis_client: Optional[Redis] = None) -> FastAPI:
    settings = get_settings()
    
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

    # Initialize Redis client if not provided
    if redis_client is None:
        redis_client = Redis.from_url(settings.REDIS_URL)
    app.state.redis_client = redis_client

    # Configure logging after app is created
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    @app.post("/activities", response_model=UploadStatusResponse)
    async def start_upload(
        request: str = Form(...),
        fit_files: list[UploadFile] = File(...),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        repository: ActivityRepository = Depends(get_activity_repository)
    ) -> UploadStatusResponse:
        # Parse the request JSON string
        request = UploadRequest.model_validate_json(request)
        
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
        await app.state.redis_client.set(f"batch:{batch_id}", json_dumps(batch_status.model_dump()))

        for activity, file in zip(request.activities, fit_files):
            activity_status = ActivityStatusResponse(
                activity_id=activity.id,
                status=UploadStatus.PENDING,
                last_updated=datetime.now(),
                completed_tasks=0,
            )
            await app.state.redis_client.set(f"activity:{activity.id}", json_dumps(activity_status.model_dump()))

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

    @app.get("/activities/{activity_id}/status", response_model=UploadStatusResponse)
    async def get_upload_status(activity_id: str):
        status_key = f"status:{activity_id}"
        status = await app.state.redis_client.hgetall(status_key)

        if not status:
            raise HTTPException(status_code=404, detail="Activity not found")

        return UploadStatusResponse(
            batch_id=status["batch_id"],
            status=status["status"],
            error_message=status.get("error_message", ""),
            last_updated=datetime.fromisoformat(status["last_updated"]),
            total_activities=status.get("total_activities", 1),
            processed_activities=status.get("processed_activities", 0),
            failed_activities=status.get("failed_activities", 0),
        )

    async def update_activity_status(
        activity_id: str,
        status: UploadStatus,
        error: Optional[str] = None
    ) -> None:
        key = f"activity:{activity_id}"
        current = await app.state.redis_client.get(key)
        if current:
            current_status = json.loads(current)
            current_status["status"] = status.value
            if error:
                current_status["error"] = error
            current_status["last_updated"] = datetime.now().isoformat()
            await app.state.redis_client.set(key, json_dumps(current_status))

    async def increment_completed_tasks(activity_id: str, num_tasks: int):
        key = f"activity:{activity_id}"
        current = await app.state.redis_client.get(key)
        if current:
            current_status = json.loads(current)
            pipe = app.state.redis_client.pipeline()
            await pipe.hincrby(key, "completed_tasks", 1)
            await pipe.hget(key, "completed_tasks")
            completed = (await pipe.execute())[1]
            if int(completed) == num_tasks:
                current_status["status"] = UploadStatus.COMPLETED.value
            current_status["last_updated"] = datetime.now().isoformat()
            await app.state.redis_client.set(key, json_dumps(current_status))

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

    return app

if __name__ == "__main__":
    app = create_app()

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
