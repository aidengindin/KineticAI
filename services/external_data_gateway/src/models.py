from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class SyncStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class Activity(BaseModel):
    id: str
    start_date: datetime
    name: str
    sport_type: str
    duration: float
    distance: Optional[float] = None

class SyncRequest(BaseModel):
    user_id: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class SyncStatusResponse(BaseModel):
    status: SyncStatus
    total_activities: int = 0
    processed_activities: int = 0
    failed_activities: int = 0
    error_message: Optional[str] = None
    last_updated: datetime
