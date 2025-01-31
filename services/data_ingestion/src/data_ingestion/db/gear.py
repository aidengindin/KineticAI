from sqlalchemy.ext.asyncio import AsyncSession

from kinetic_common.models import Gear, PydanticGear

class GearRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def update_gear(self, gear_data: PydanticGear) -> None:
        gear = Gear(**gear_data.model_dump())
        await self.db.merge(gear)
        await self.db.commit()

