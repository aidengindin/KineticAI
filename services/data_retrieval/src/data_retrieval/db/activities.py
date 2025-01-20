from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kinetic_common.models import (
    Activity,
    ActivityLap,
    ActivityStream,
    PydanticActivity,
    PydanticActivityLap,
    PydanticActivityStream,
)

class ActivityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_activity(self, activity_id: str) -> Optional[PydanticActivity]:
        """Get an activity by ID.
        
        Args:
            activity_id: The ID of the activity to get
            
        Returns:
            The activity if found, None otherwise
        """
        stmt = select(Activity).where(Activity.id == activity_id)
        result = await self.db.execute(stmt)
        activity = result.scalar_one_or_none()
        
        if activity is None:
            return None
            
        return PydanticActivity.model_validate(activity)

    async def get_activities(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sport_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PydanticActivity]:
        """Get activities for a user with optional filters.
        
        Args:
            user_id: The ID of the user to get activities for
            start_date: Optional start date filter
            end_date: Optional end date filter
            sport_type: Optional sport type filter
            limit: Maximum number of activities to return
            offset: Number of activities to skip
            
        Returns:
            List of activities matching the filters
        """
        stmt = select(Activity).where(Activity.user_id == user_id)
        
        if start_date:
            stmt = stmt.where(Activity.start_date >= start_date)
        if end_date:
            stmt = stmt.where(Activity.start_date <= end_date)
        if sport_type:
            stmt = stmt.where(Activity.sport_type == sport_type)
            
        stmt = stmt.order_by(Activity.start_date.desc())
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self.db.execute(stmt)
        activities = result.scalars().all()
        
        return [PydanticActivity.model_validate(activity) for activity in activities]

    async def get_activity_laps(self, activity_id: str) -> List[PydanticActivityLap]:
        """Get all laps for an activity.
        
        Args:
            activity_id: The ID of the activity to get laps for
            
        Returns:
            List of laps for the activity
        """
        stmt = select(ActivityLap).where(ActivityLap.activity_id == activity_id)
        stmt = stmt.order_by(ActivityLap.sequence)
        
        result = await self.db.execute(stmt)
        laps = result.scalars().all()
        
        return [PydanticActivityLap.model_validate(lap) for lap in laps]

    async def get_activity_streams(
        self,
        activity_id: str,
        fields: Optional[List[str]] = None,
    ) -> List[PydanticActivityStream]:
        """Get activity streams with optional field filtering.
        
        Args:
            activity_id: The ID of the activity to get streams for
            fields: Optional list of fields to include. If None, includes all fields.
            
        Returns:
            List of activity streams
        """
        if fields:
            # Always include required fields
            required_fields = {'activity_id', 'sequence', 'time'}
            fields = list(set(fields) | required_fields)
            stmt = select(ActivityStream).with_only_columns(
                *[getattr(ActivityStream, field) for field in fields]
            )
        else:
            stmt = select(ActivityStream)
            
        stmt = stmt.where(ActivityStream.activity_id == activity_id)
        stmt = stmt.order_by(ActivityStream.sequence)
        
        result = await self.db.execute(stmt)
        streams = result.scalars().all()
        
        return [PydanticActivityStream.model_validate(stream) for stream in streams] 