from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

from data_ingestion.config import get_settings

Base = declarative_base()
engine = None
AsyncSessionLocal = None

def get_engine():
    global engine
    if engine is None:
        settings = get_settings()
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.SQL_ECHO,
            pool_pre_ping=True,
        )
    return engine

def get_session_maker():
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        AsyncSessionLocal = sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
