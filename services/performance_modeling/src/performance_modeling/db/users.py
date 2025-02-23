from datetime import datetime
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import class_mapper
import logging

from kinetic_common.models import (
    User,
    PydanticUser,
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

class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_user(self, user_id: str) -> User:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalars().first()
        return PydanticUser.model_validate(model_to_dict(user))

    async def update_cycling_cp(
        self,
        user_id: str,
        cp: int,
        wp: int,
        k: int,
    ) -> None:
        stmt = (
            User.update()
            .where(User.id == user_id)
            .values(
                cycling_cp=cp,
                cycling_w_prime=wp,
                cycling_k=k,
            )
        )
        await self.db.execute(stmt)

    async def update_running_cp(
        self,
        user_id: str,
        cp: int,
        wp: int,
        k: int,
    ) -> None:
        stmt = (
            User.update()
            .where(User.id == user_id)
            .values(
                running_cp=cp,
                running_w_prime=wp,
                running_k=k,
            )
        )
        await self.db.execute(stmt)
