from datetime import datetime
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import class_mapper
import logging

from kinetic_common.models import (
    PowerCurve,
    PydanticPowerCurve,
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

class PowerCurveRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_user_power_curve(self, user_id: str, sport: str) -> List[PydanticPowerCurve]:
        """Get power curve for a user."""
        stmt = select(PowerCurve).where(PowerCurve.user_id == user_id and PowerCurve.sport == sport)
        result = await self.db.execute(stmt)
        power_curves = result.scalars().all()

        return [PydanticPowerCurve.model_validate(model_to_dict(power_curve)) for power_curve in power_curves]
