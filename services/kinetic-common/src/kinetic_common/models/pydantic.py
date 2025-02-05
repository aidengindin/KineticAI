from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class User(BaseModel):
    """User model for request/response data."""
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    weight: Optional[float] = None
    running_cp: Optional[int] = None
    running_tte: Optional[int] = None
    running_w_prime: Optional[int] = None
    cycling_cp: Optional[int] = None
    cycling_tte: Optional[int] = None
    cycling_w_prime: Optional[int] = None

class Activity(BaseModel):
    """Activity model for request/response data."""
    id: str
    user_id: Optional[str] = None
    start_date: datetime
    name: str
    sport_type: str
    duration: float
    distance: float
    average_speed: float
    average_heartrate: float
    gear: Optional[str] = None

class ActivityLap(BaseModel):
    """Activity lap model for request/response data."""
    activity_id: str
    sequence: int
    start_date: datetime
    duration: float
    distance: float
    average_speed: float
    average_heartrate: float
    average_cadence: Optional[float] = None
    average_power: Optional[float] = None
    average_lr_balance: Optional[float] = None
    intensity: Optional[str] = None

class ActivityStream(BaseModel):
    """Activity stream model for request/response data."""
    activity_id: str
    sequence: int
    time: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    heart_rate: Optional[int] = None
    cadence: Optional[int] = None
    power: Optional[int] = None
    speed: Optional[float] = None
    temperature: Optional[float] = None
    dfa_a1: Optional[float] = None 

class Gear(BaseModel):
    id: str
    user_id: str
    name: str
    distance: float
    time: float
    type: str

class Race(BaseModel):
    id: str
    user_id: str
    start_date: datetime
    name: Optional[str] = None
    distance: int
    elevation_gain: Optional[int] = None
    gear: Optional[Gear] = None
    predicted_duration: Optional[int] = None
    predicted_power: Optional[int] = None
    predicted_running_effectiveness: Optional[float] = None
    predicted_riegel_exponent: Optional[float] = None

class PowerCurve(BaseModel):
    user_id: str
    sport: str
    duration: int
    power: float
