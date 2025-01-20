from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

from kinetic_common.models import Base
from data_retrieval.config import get_settings

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
    """Get a database session.
    
    Yields:
        AsyncSession: The database session
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session 