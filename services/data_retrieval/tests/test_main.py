import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
from fastapi.testclient import TestClient
from sqlalchemy.orm import class_mapper
from fastapi import FastAPI

from data_retrieval.main import app, create_app, get_activity_repository, get_db
from data_retrieval.db.activities import ActivityRepository
from kinetic_common.models import PydanticActivity, PydanticActivityLap, PydanticActivityStream

def model_to_dict(obj):
    """Convert SQLAlchemy model instance to dictionary."""
    mapper = class_mapper(obj.__class__)
    return {
        column.key: getattr(obj, column.key)
        for column in mapper.columns
        if hasattr(obj, column.key) and getattr(obj, column.key) is not None
    }

@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    repository = Mock()
    
    # Create async methods that return awaitable values
    async def mock_get_activity(*args, **kwargs):
        return repository.get_activity.return_value
        
    async def mock_get_activities(*args, **kwargs):
        return repository.get_activities.return_value
        
    async def mock_get_activity_laps(*args, **kwargs):
        return repository.get_activity_laps.return_value
        
    async def mock_get_activity_streams(*args, **kwargs):
        return repository.get_activity_streams.return_value
    
    # Replace the mock methods with our async functions
    repository.get_activity = Mock(side_effect=mock_get_activity)
    repository.get_activities = Mock(side_effect=mock_get_activities)
    repository.get_activity_laps = Mock(side_effect=mock_get_activity_laps)
    repository.get_activity_streams = Mock(side_effect=mock_get_activity_streams)
    
    return repository

@pytest.fixture
def mock_db():
    """Create a mock async session."""
    session = AsyncMock()
    
    # Create a mock result that mimics SQLAlchemy's Result object
    mock_result = Mock()
    mock_result.scalars = Mock(return_value=mock_result)
    mock_result.all = Mock(return_value=[])
    mock_result.scalar_one_or_none = Mock(return_value=None)
    
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    return session

@pytest.fixture
def test_app(mock_repository, mock_db):
    """Create a test app instance with mocked dependencies."""
    app = create_app()
    
    # Override the repository dependency
    async def get_mock_repository():
        return mock_repository
    
    # Override the database dependency
    async def get_test_db():
        yield mock_db
    
    app.dependency_overrides[get_activity_repository] = get_mock_repository
    app.dependency_overrides[get_db] = get_test_db
    return app

@pytest.fixture
def test_client(test_app):
    """Create a test client."""
    return TestClient(test_app)

def test_get_activity(test_client, mock_repository, sample_activity):
    """Test getting a single activity."""
    # Mock repository response
    mock_repository.get_activity.return_value = PydanticActivity.model_validate({
        "id": sample_activity.id,
        "user_id": sample_activity.user_id,
        "start_date": sample_activity.start_date,
        "name": sample_activity.name,
        "sport_type": sample_activity.sport_type,
        "duration": sample_activity.duration,
        "distance": sample_activity.distance,
        "average_speed": sample_activity.average_speed,
        "average_heartrate": sample_activity.average_heartrate,
    })

    # Make request
    response = test_client.get("/activities/test123")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test123"
    assert data["name"] == "Morning Run"
    assert data["sport_type"] == "running"

def test_get_activity_not_found(test_client, mock_repository):
    """Test getting a non-existent activity."""
    # Mock repository response
    mock_repository.get_activity.return_value = None

    # Make request
    response = test_client.get("/activities/nonexistent")

    # Verify response
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"

def test_get_activities(test_client, mock_repository, sample_activities):
    """Test getting activities with filters."""
    # Mock repository response
    mock_repository.get_activities.return_value = [
        PydanticActivity.model_validate({
            "id": activity.id,
            "user_id": activity.user_id,
            "start_date": activity.start_date,
            "name": activity.name,
            "sport_type": activity.sport_type,
            "duration": activity.duration,
            "distance": activity.distance,
            "average_speed": activity.average_speed,
            "average_heartrate": activity.average_heartrate,
        })
        for activity in sample_activities
    ]

    # Make request with filters
    response = test_client.get(
        "/activities",
        params={
            "user_id": "user123",
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=1)).isoformat(),
            "sport_type": "running",
            "limit": 3,
            "offset": 1,
        }
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(sample_activities)
    for activity in data:
        assert activity["user_id"] == "user123"

def test_get_activities_missing_user_id(test_client, mock_repository):
    """Test getting activities without required user_id."""
    # Make request without user_id
    response = test_client.get("/activities")

    # Verify response
    assert response.status_code == 422

def test_get_activity_laps(test_client, mock_repository, sample_laps):
    """Test getting activity laps."""
    # Mock repository response
    mock_repository.get_activity_laps.return_value = [
        PydanticActivityLap.model_validate({
            "activity_id": lap.activity_id,
            "sequence": lap.sequence,
            "start_date": lap.start_date,
            "duration": lap.duration,
            "distance": lap.distance,
            "average_speed": lap.average_speed,
            "average_heartrate": lap.average_heartrate,
            "average_cadence": lap.average_cadence,
            "average_power": lap.average_power,
            "average_lr_balance": lap.average_lr_balance,
            "intensity": lap.intensity,
        })
        for lap in sample_laps
    ]

    # Make request
    response = test_client.get("/activities/test123/laps")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(sample_laps)
    for i, lap in enumerate(data):
        assert lap["activity_id"] == "test123"
        assert lap["sequence"] == i

def test_get_activity_streams(test_client, mock_repository, sample_streams):
    """Test getting activity streams."""
    # Mock repository response
    mock_repository.get_activity_streams.return_value = [
        PydanticActivityStream.model_validate({
            "activity_id": stream.activity_id,
            "sequence": stream.sequence,
            "time": stream.time,
            "latitude": stream.latitude,
            "longitude": stream.longitude,
            "altitude": stream.altitude,
            "heart_rate": stream.heart_rate,
            "cadence": stream.cadence,
            "power": stream.power,
            "speed": stream.speed,
            "temperature": stream.temperature,
            "dfa_a1": stream.dfa_a1,
        })
        for stream in sample_streams
    ]

    # Make request
    response = test_client.get("/activities/test123/streams")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(sample_streams)
    for i, stream in enumerate(data):
        assert stream["activity_id"] == "test123"
        assert stream["sequence"] == i

def test_get_activity_streams_with_fields(test_client, mock_repository, sample_streams):
    """Test getting activity streams with field filtering."""
    # Mock repository response
    mock_repository.get_activity_streams.return_value = [
        PydanticActivityStream.model_validate({
            "activity_id": stream.activity_id,
            "sequence": stream.sequence,
            "time": stream.time,
            "heart_rate": stream.heart_rate,
            "power": stream.power,
            "cadence": stream.cadence,
        })
        for stream in sample_streams
    ]

    # Make request with field filtering
    fields = ["heart_rate", "power", "cadence"]
    response = test_client.get(
        "/activities/test123/streams",
        params={"fields": fields}
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(sample_streams)
    for stream in data:
        assert "heart_rate" in stream
        assert "power" in stream
        assert "cadence" in stream 