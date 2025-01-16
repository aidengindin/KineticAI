import argparse
from datetime import datetime
import json
import logging
from typing import Optional, Any
import uuid
import uvicorn

from data_ingestion.db.activities import ActivityRepository
from data_ingestion.db.database import get_db
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fitparse import FitFile
from prometheus_client import make_asgi_app
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

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
        try:
            # Parse the request JSON string
            request = UploadRequest.model_validate_json(request)
            
            # Validate number of files matches number of activities
            if len(fit_files) != len(request.activities):
                raise HTTPException(
                    status_code=422,
                    detail=f"Number of files ({len(fit_files)}) does not match number of activities ({len(request.activities)})"
                )
            
            # Validate file types
            for file in fit_files:
                if not file.filename.lower().endswith('.fit'):
                    raise HTTPException(
                        status_code=422,
                        detail=f"Invalid file type for {file.filename}. Only .fit files are supported."
                    )
            
            num_tasks = 3  # create_activity, store_laps, store_streams
            batch_id = str(uuid.uuid4())

            batch_status = UploadStatusResponse(
                batch_id=batch_id,
                status=UploadStatus.PENDING,
                total_activities=len(request.activities),
                processed_activities=0,
                failed_activities=0,
                last_updated=datetime.now(),
            )
            
            # Initialize batch status in Redis
            try:
                await app.state.redis_client.set(f"batch:{batch_id}", json_dumps(batch_status.model_dump()))
            except Exception as e:
                logger.error(f"Failed to initialize batch status: {str(e)}")
                # Don't wrap this in another try-except since we want this specific error to propagate
                raise HTTPException(
                    status_code=500,
                    detail="Failed to initialize batch status"
                ) from e

            for activity, file in zip(request.activities, fit_files):
                try:
                    # Read file content first
                    file_content = await file.read()
                    
                    # Try to validate FIT file before initializing status
                    try:
                        fit_file = FitFile(file_content)
                        # Access messages to verify file is readable
                        next(fit_file.messages)
                    except Exception as e:
                        logger.error(f"Invalid FIT file for activity {activity.id}: {str(e)}")
                        # Initialize activity with FAILED status
                        activity_status = ActivityStatusResponse(
                            activity_id=activity.id,
                            status=UploadStatus.FAILED,
                            error_message=f"Invalid FIT file: {str(e)}",
                            last_updated=datetime.now(),
                            completed_tasks=0,
                        )
                        try:
                            await app.state.redis_client.set(
                                f"activity:{activity.id}",
                                json_dumps(activity_status.model_dump())
                            )
                        except Exception as redis_err:
                            logger.error(f"Failed to update activity status: {str(redis_err)}")
                            raise HTTPException(
                                status_code=500,
                                detail="Failed to update activity status"
                            ) from redis_err
                        continue

                    # Initialize activity with PENDING status only if validation passed
                    activity_status = ActivityStatusResponse(
                        activity_id=activity.id,
                        status=UploadStatus.PENDING,
                        last_updated=datetime.now(),
                        completed_tasks=0,
                    )
                    try:
                        await app.state.redis_client.set(
                            f"activity:{activity.id}",
                            json_dumps(activity_status.model_dump())
                        )
                    except Exception as redis_err:
                        logger.error(f"Failed to update activity status: {str(redis_err)}")
                        raise HTTPException(
                            status_code=500,
                            detail="Failed to update activity status"
                        ) from redis_err

                    await update_activity_status(activity.id, UploadStatus.IN_PROGRESS)

                    # Add background tasks for processing
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
                    
                except HTTPException:
                    # Re-raise HTTP exceptions without wrapping
                    raise
                except Exception as e:
                    logger.error(f"Failed to process activity {activity.id}: {str(e)}")
                    try:
                        await update_activity_status(
                            activity.id,
                            UploadStatus.FAILED,
                            str(e)
                        )
                    except Exception as redis_err:
                        logger.error(f"Failed to update activity status: {str(redis_err)}")
                        raise HTTPException(
                            status_code=500,
                            detail="Failed to update activity status"
                        ) from redis_err
                    continue

            return batch_status
            
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except HTTPException:
            # Re-raise HTTP exceptions without wrapping
            raise
        except Exception as e:
            logger.error(f"Unexpected error in start_upload: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    @app.get("/activities/{activity_id}/status", response_model=UploadStatusResponse)
    async def get_upload_status(activity_id: str):
        status_key = f"status:{activity_id}"
        try:
            status = await app.state.redis_client.hgetall(status_key)
        except Exception as e:
            logger.error(f"Failed to get status for activity {activity_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Redis connection error: {str(e)}"
            )

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
        """Process a task with status updates.
        
        Args:
            task_func: The async function to execute
            activity_id: The ID of the activity being processed
            num_tasks: Total number of tasks for this activity
            *args: Arguments to pass to task_func
            **kwargs: Keyword arguments to pass to task_func
        """
        try:
            # Get current status
            key = f"activity:{activity_id}"
            current = await app.state.redis_client.get(key)
            if current:
                current_status = json.loads(current)
                # Only update to in_progress if currently pending
                if current_status["status"] == UploadStatus.PENDING.value:
                    await update_activity_status(activity_id, UploadStatus.IN_PROGRESS)
                # Don't proceed if already failed
                elif current_status["status"] == UploadStatus.FAILED.value:
                    logging.info(f"Skipping {task_func.__name__} for activity {activity_id} as it's already failed")
                    return
            
            # Execute the task
            await task_func(*args, **kwargs)
            
            try:
                # Try to increment completed tasks
                await increment_completed_tasks(activity_id, num_tasks)
            except Exception as e:
                # Log Redis error but don't fail the task
                logging.error(f"Failed to increment completed tasks for activity {activity_id}: {str(e)}")
                # Still consider the task successful since the main operation completed
                return
            
        except Exception as e:
            error_message = f"Error in {task_func.__name__}: {str(e)}"
            logging.error(f"Failed to process activity {activity_id}: {error_message}")
            
            try:
                # Try to update status to failed
                await update_activity_status(
                    activity_id,
                    UploadStatus.FAILED,
                    error_message,
                )
            except Exception as redis_err:
                # Log Redis error but don't mask the original error
                logging.error(f"Failed to update error status for activity {activity_id}: {str(redis_err)}")
            
            # Don't re-raise the error since this is a background task
            # Just log it and let the task complete
            return

    return app

# Create the app at module level
app = create_app()

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the server on")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", type=str, default="info", help="Logging level")

    args = parser.parse_args()

    uvicorn.run(
        "data_ingestion.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )

if __name__ == "__main__":
    main()
