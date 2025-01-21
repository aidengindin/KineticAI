import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession

from data_retrieval.db.activities import ActivityRepository
from kinetic_common.models import Activity, ActivityLap, ActivityStream

@pytest.fixture(autouse=True)
def test_env():
    """Ensure we're using test settings."""
    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("ENV_NAME", "test")
        yield

@pytest.fixture
def mock_db():
    """Create a mock async session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session

@pytest.fixture
def repository(mock_db):
    """Create an ActivityRepository instance with a mock db."""
    return ActivityRepository(mock_db)

@pytest.fixture
def sample_activity():
    """Create a sample activity."""
    return Activity(
        id="test123",
        user_id="user123",
        start_date=datetime.now(),
        name="Morning Run",
        sport_type="running",
        duration=3600.0,
        distance=10000.0,
        average_speed=2.78,
        average_heartrate=150.0,
        fit_file=b"mock fit file",
    )

@pytest.fixture
def sample_activities():
    """Create a list of sample activities."""
    base_date = datetime.now()
    return [
        Activity(
            id=f"test{i}",
            user_id="user123",
            start_date=base_date - timedelta(days=i),
            name=f"Activity {i}",
            sport_type="running" if i % 2 == 0 else "cycling",
            duration=3600.0,
            distance=10000.0,
            average_speed=2.78,
            average_heartrate=150.0,
            fit_file=b"mock fit file",
        )
        for i in range(5)
    ]

@pytest.fixture
def sample_laps():
    """Create sample activity laps."""
    return [
        ActivityLap(
            activity_id="test123",
            sequence=i,
            start_date=datetime.now() + timedelta(minutes=5*i),
            duration=300.0,
            distance=1000.0,
            average_speed=3.33,
            average_heartrate=155.0,
            average_cadence=85.0,
            average_power=200.0,
            average_lr_balance=50.0,
            intensity="active",
        )
        for i in range(3)
    ]

@pytest.fixture
def sample_streams():
    """Create sample activity streams."""
    base_time = datetime.now()
    return [
        ActivityStream(
            activity_id="test123",
            sequence=i,
            time=base_time + timedelta(seconds=i),
            latitude=45.5 + (i * 0.001),
            longitude=-73.5 + (i * 0.001),
            altitude=100.0 + i,
            heart_rate=150 + i,
            cadence=85,
            power=200,
            speed=3.0,
            temperature=20.0,
            dfa_a1=0.75,
        )
        for i in range(10)
    ] 