from datetime import datetime
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import class_mapper
import logging

from kinetic_common.models import (
    Race,
    PydanticRace,
)

logger = logging.getLogger(__name__)

def model_to_dict(obj):
    """Convert SQLAlchemy model instance to dictionary."""
    mapper = class_mapper(obj.__class__)
    return {
        column.key: getattr(obj, column.key)
        for column in mapper.columns
        if hasattr(obj, column.key) and getattr(obj, column.key) is not None
    }

class RaceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_user_upcoming_races(self, user_id: str) -> List[PydanticRace]:
        """Get all planned upcoming races for a user."""

        stmt = select(Race).where(Race.id == user_id)
        stmt = stmt.where(Race.start_date > datetime.now())
        result = await self.db.execute(stmt)
        races = result.scalars().all()

        return [PydanticRace.model_validate(model_to_dict(race)) for race in races]
