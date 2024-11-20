from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class UploadStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Gear(BaseModel):
    id: str
    name: str
    distance: float


class Activity(BaseModel):
    id: str
    start_date: datetime
    name: str
    description: Optional[str] = None
    sport_type: str
    duration: float
    total_elevation_gain: Optional[float] = None
    distance: Optional[float] = None
    average_speed: Optional[float] = None
    average_heartrate: Optional[int] = None
    average_cadence: Optional[float] = None
    average_power: Optional[float] = None
    calories: Optional[int] = None
    average_lr_balance: Optional[float] = None
    gear: Optional[Gear] = None
    average_gap: Optional[float] = None
    perceived_exertion: Optional[int] = None
    polarization_index: Optional[float] = None
    decoupling: Optional[float] = None
    carbs_ingested: Optional[float] = None
    normalized_power: Optional[int] = None
    training_load: Optional[int] = None


class UploadRequest(BaseModel):
    user_id: str
    activities: list[Activity]
    fit_files: list[bytearray]


class UploadStatusResponse(BaseModel):
    status: UploadStatus
    total_activities: int = 0
    processed_activities: int = 0
    failed_activities: int = 0
    error_message: Optional[str] = None
    last_updated: datetime
