from contextlib import asynccontextmanager
from datetime import datetime
import logging
from typing import Optional
from fastapi import BackgroundTasks, Depends, FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from sqlalchemy.ext.asyncio import AsyncSession

from performance_modeling.config import get_settings
from performance_modeling.cp_estimator import estimate_cp_wp
from performance_modeling.race_prediction import predict
from performance_modeling.models import PredictionResponse
from performance_modeling.db.database import get_db
from performance_modeling.db.power_curve import PowerCurveRepository

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def get_power_curve_repository(db: AsyncSession = Depends(get_db)) -> PowerCurveRepository:
    return PowerCurveRepository(db)

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

    # TODO: this should probably be removed
    @app.get("/races/${athlete_id}")
    async def get_races(
        athlete_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> None:
        pass

    @app.get("/predictions/user/{user_id}/race/{race_id}", response_model=PredictionResponse)
    async def predict_race(
        user_id: str,
        race_id: str,
        cp: Optional[int],
        running_effectiveness: Optional[float],
        riegel_exponent: Optional[float],
        w_prime: Optional[int],
    ) -> PredictionResponse:
        # get user cp, wp, and k from data retrieval service
        cp, wp, k = 0, 0, 0
        distance = 0
        time, power = predict(
            distance=distance,
            cp=cp,
            tte=50,
            w_prime=wp,
            k=k,
            running_effectiveness=running_effectiveness,
            riegel_exponent=riegel_exponent,
            athlete_weight=0,
        )
        return PredictionResponse(time=time, power=power)


    @app.post("/cp/${sport}/user/{user_id}")
    async def update_cp(
        user_id: str,
        sport: str,
        power_curve_repository: PowerCurveRepository = Depends(get_power_curve_repository),
    ) -> None:
        cp, wp, k = await estimate_cp_wp(power_curve_repository, user_id, sport)

    return app
