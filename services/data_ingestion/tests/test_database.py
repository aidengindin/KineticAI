import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import greenlet

from data_ingestion.db.database import get_engine, get_session_maker, get_db
from data_ingestion.config import get_settings

@pytest.mark.asyncio
async def test_get_engine():
    """Test get_engine creates and caches engine."""
    # First call should create engine
    engine1 = get_engine()
    assert engine1 is not None
    
    # Second call should return cached engine
    engine2 = get_engine()
    assert engine2 is engine1

@pytest.mark.asyncio
async def test_get_session_maker():
    """Test get_session_maker creates and caches session maker."""
    # First call should create session maker
    session_maker1 = get_session_maker()
    assert session_maker1 is not None
    
    # Second call should return cached session maker
    session_maker2 = get_session_maker()
    assert session_maker2 is session_maker1

@pytest.mark.asyncio
async def test_get_db():
    """Test get_db yields session and closes it."""
    async for session in get_db():
        assert isinstance(session, AsyncSession)
        assert session.is_active is True
        break
