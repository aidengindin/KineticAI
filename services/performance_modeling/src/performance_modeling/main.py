from contextlib import asynccontextmanager
from datetime import datetime
import logging
from typing import Optional
from fastapi import BackgroundTasks, FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from performance_modeling.config import get_settings

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Startup
    logger.info("Starting race prediction service...")
    yield
    # Shutdown
    logger.info("Shutting down race prediction service...")

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Race Prediction Service")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    @app.get("/races/${athlete_id}")
    async def get_races(
        athlete_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> None:
        pass

    @app.get("/predictions/user/{user_id}/race/{race_id}")
    async def predict_race(
        user_id: str,
        race_id: str,
        cp: Optional[int],
        running_effectiveness: Optional[float],
        riegel_exponent: Optional[float],
        w_prime: Optional[int],
    ) -> None:
        pass

    return app
