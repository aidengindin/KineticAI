from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from kinetic_common.models import Gear, PydanticGear

def model_to_dict(obj):
    """Convert SQLAlchemy model instance to dictionary."""
    mapper = class_mapper(obj.__class__)
    return {
        column.key: getattr(obj, column.key)
        for column in mapper.columns
        if hasattr(obj, column.key) and getattr(obj, column.key) is not None
    }

class GearRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_gear(
        self,
        user_id: str,
        gear_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[PydanticGear]:
        stmt = select(Gear).where(Gear.user_id == user_id)
        if gear_type:
            stmt = stmt.where(Gear.type == gear_type)
        if limit:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)
        result = await self.db.execute(stmt)
        return [PydanticGear.model_validate(model_to_dict(gear)) for gear in result.scalars().all()]
