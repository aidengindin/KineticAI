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
from performance_modeling.models import CPUpdateResponse, PredictionResponse
from performance_modeling.db.database import get_db
from performance_modeling.db.power_curve import PowerCurveRepository
from performance_modeling.db.users import UserRepository
from performance_modeling.db.races import RaceRepository

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def get_power_curve_repository(db: AsyncSession = Depends(get_db)) -> PowerCurveRepository:
    return PowerCurveRepository(db)

async def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)

async def get_race_repository(db: AsyncSession = Depends(get_db)) -> RaceRepository:
    return RaceRepository(db)

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

    @app.get("/predictions/user/{user_id}/race/{race_id}", response_model=PredictionResponse)
    async def predict_race(
        user_id: str,
        race_id: str,
        running_effectiveness: Optional[float],
        riegel_exponent: Optional[float],
        user_repository: UserRepository = Depends(get_user_repository),
        race_repository: RaceRepository = Depends(get_race_repository),
    ) -> PredictionResponse:
        user = await user_repository.get_user(user_id)
        # TODO: handle case where user doesn't have a CP
        # TODO: determine running effectiveness and riegel exponent automatically if not provided
        race = await race_repository.get_race(race_id)
        time, power = predict(
            distance=race.distance,
            cp=user.cp,
            tte=50,
            w_prime=user.wp,
            k=user.k,
            running_effectiveness=running_effectiveness,
            riegel_exponent=riegel_exponent,
            athlete_weight=0,
        )
        return PredictionResponse(predicted_time=time, predicted_power=power)


    @app.post("/cp/${sport}/user/{user_id}")
    async def update_cp(
        user_id: str,
        sport: str,
        power_curve_repository: PowerCurveRepository = Depends(get_power_curve_repository),
        user_repository: UserRepository = Depends(get_user_repository),
    ) -> CPUpdateResponse:
        cp, wp, k = await estimate_cp_wp(power_curve_repository, user_id, sport)
        match sport:
            case "cycling":
                await user_repository.update_cycling_cp(user_id, cp, wp, k)
            case "running":
                await user_repository.update_running_cp(user_id, cp, wp, k)
            case _:
                raise ValueError(f"Unsupported sport: {sport}")
        return CPUpdateResponse(cp=cp, wp=wp, k=k)

    return app
