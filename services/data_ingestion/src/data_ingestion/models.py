from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class UploadStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class ActivityStatusResponse(BaseModel):
    activity_id: str
    status: UploadStatus
    error_message: Optional[str] = None
    completed_tasks: int = 0
    last_updated: datetime

class UploadStatusResponse(BaseModel):
    batch_id: str
    status: UploadStatus
    total_activities: int
    processed_activities: int
    failed_activities: int
    error_message: Optional[str] = None
    last_updated: datetime

class UploadRequest(BaseModel):
    user_id: str
    activities: List[dict] 