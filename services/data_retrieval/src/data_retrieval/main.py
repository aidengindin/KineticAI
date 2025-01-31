import argparse
import logging
from typing import List, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from sqlalchemy.ext.asyncio import AsyncSession

from data_retrieval.config import get_settings
from data_retrieval.db.database import get_db
from data_retrieval.db.activities import ActivityRepository
from data_retrieval.db.gear import GearRepository
from kinetic_common.models import (
    PydanticActivity,
    PydanticActivityLap,
    PydanticActivityStream,
    PydanticGear,
)
# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def get_activity_repository(db: AsyncSession = Depends(get_db)) -> ActivityRepository:
    return ActivityRepository(db)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Startup
    logger.info("Starting data retrieval service...")
    yield
    # Shutdown
    logger.info("Shutting down data retrieval service...")

def create_app() -> FastAPI:
    settings = get_settings()
    
    # Initialize FastAPI app
    app = FastAPI(title="Data Retrieval Service", lifespan=lifespan)

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

    @app.get("/activities/{activity_id}", response_model=PydanticActivity)
    async def get_activity(
        activity_id: str,
        repository: ActivityRepository = Depends(get_activity_repository)
    ) -> PydanticActivity:
        """Get an activity by ID."""
        activity = await repository.get_activity(activity_id)
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        return activity

    @app.get("/activities", response_model=List[PydanticActivity])
    async def get_activities(
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sport_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        repository: ActivityRepository = Depends(get_activity_repository)
    ) -> List[PydanticActivity]:
        """Get activities for a user with optional filters."""
        return await repository.get_activities(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            sport_type=sport_type,
            limit=limit,
            offset=offset,
        )

    @app.get("/activities/{activity_id}/laps", response_model=List[PydanticActivityLap])
    async def get_activity_laps(
        activity_id: str,
        repository: ActivityRepository = Depends(get_activity_repository)
    ) -> List[PydanticActivityLap]:
        """Get all laps for an activity."""
        return await repository.get_activity_laps(activity_id)

    @app.get("/activities/{activity_id}/streams", response_model=List[PydanticActivityStream])
    async def get_activity_streams(
        activity_id: str,
        fields: Optional[List[str]] = None,
        repository: ActivityRepository = Depends(get_activity_repository)
    ) -> List[PydanticActivityStream]:
        """Get activity streams with optional field filtering."""
        return await repository.get_activity_streams(activity_id, fields)

    return app

    @app.get("/gear", response_model=List[PydanticGear])
    async def get_gear(
        user_id: str,
        gear_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        repository: GearRepository = Depends(get_gear_repository)
    ) -> List[PydanticGear]:
        """Get gear for a user with optional filters."""
        return await repository.get_gear(user_id, gear_type, limit, offset)
    

# Create the app at module level
app = create_app()

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the server on")
    parser.add_argument("--port", type=int, default=8001, help="Port to run the server on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", type=str, default="info", help="Logging level")

    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "data_retrieval.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )

if __name__ == "__main__":
    main() 
