from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
    user_id: Optional[str] = None
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
    fit_file: Optional[bytes] = None

class ActivityStream(BaseModel):
    time: datetime
    activity_id: str
    sequence: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    power: Optional[int] = None
    heart_rate: Optional[int] = None
    cadence: Optional[int] = None
    distance: Optional[float] = None
    altitude: Optional[float] = None
    speed: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    vertical_oscillation: Optional[float] = None
    ground_contact_time: Optional[float] = None
    left_right_balance: Optional[float] = None
    form_power: Optional[int] = None
    leg_spring_stiffness: Optional[float] = None
    air_power: Optional[int] = None
    dfa_a1: Optional[float] = None
    artifacts: Optional[float] = None
    respiration_rate: Optional[float] = None
    front_gear: Optional[int] = None
    rear_gear: Optional[int] = None


class ActivityLap(BaseModel):
    activity_id: str
    sequence: int
    start_date: datetime
    duration: Optional[float]
    distance: Optional[float]
    average_speed: Optional[float]
    average_heartrate: Optional[int]
    average_cadence: Optional[float]
    average_power: Optional[float]
    average_lr_balance: Optional[float]
    intensity: Optional[str]


class UploadRequest(BaseModel):
    user_id: str
    activities: list[Activity]


class UploadStatusResponse(BaseModel):
    batch_id: str
    status: UploadStatus
    total_activities: int = 0
    processed_activities: int = 0
    failed_activities: int = 0
    error_message: Optional[str] = None
    last_updated: datetime

class ActivityStatusResponse(BaseModel):
    activity_id: str
    status: UploadStatus
    error_message: Optional[str] = None
    last_updated: datetime
    completed_tasks: int = 0
