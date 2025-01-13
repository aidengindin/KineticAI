import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from data_ingestion.main import create_app, get_activity_repository
from data_ingestion.models import UploadRequest, Activity, UploadStatus

@pytest.fixture
def app(mock_redis):
    """Create a test app instance."""
    app = create_app(redis_client=mock_redis)
    return app

@pytest.fixture
def test_client(app):
    """Create a test client for the FastAPI app."""
    return TestClient(app)

@pytest.fixture
def mock_repository():
    """Create a mock activity repository."""
    repository = Mock()
    repository.create_activity = AsyncMock()
    repository.store_laps = AsyncMock()
    repository.store_streams = AsyncMock()
    return repository

@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    
    # Set up mock responses
    async def mock_get(key: str) -> str:
        if key.startswith("activity:"):
            return json.dumps({
                "activity_id": key.split(":")[-1],
                "status": UploadStatus.PENDING.value,
                "last_updated": datetime.now().isoformat(),
                "completed_tasks": 0,
            })
        return None
    
    redis.get = AsyncMock(side_effect=mock_get)
    redis.set = AsyncMock(return_value=True)
    redis.hgetall = AsyncMock(return_value={})
    redis.pipeline = Mock(return_value=redis)  # Mock pipeline to return self
    redis.execute = AsyncMock(return_value=[1, 1])  # Mock pipeline execution
    redis.hincrby = AsyncMock()
    redis.hget = AsyncMock()
    return redis

@pytest.fixture
def sample_activity():
    """Create a sample activity for testing."""
    return Activity(
        id="test123",
        start_date=datetime.now(),
        name="Morning Run",
        sport_type="running",
        duration=3600.0,
        distance=10000.0,
        average_speed=2.78,
        average_heartrate=150,
    )

@pytest.fixture
def upload_request(sample_activity):
    """Create a sample upload request."""
    return UploadRequest(
        user_id="user123",
        activities=[sample_activity]
    )

@pytest.fixture
def mock_fit_file():
    """Create a mock FitFile."""
    fit_file = Mock()
    
    # Create mock messages
    lap_message = Mock()
    lap_message.mesg_type = "lap"
    lap_message.get = lambda x: {
        "start_time": datetime.now(),
        "total_elapsed_time": 600.0,
        "total_distance": 2000.0,
        "avg_speed": 3.33,
        "avg_heart_rate": 155,
        "avg_cadence": 180,
        "avg_power": 200,
        "intensity": "active"
    }.get(x)

    record_message = Mock()
    record_message.mesg_type = "record"
    record_message.get = lambda x: {
        "timestamp": datetime.now(),
        "position_lat": 45.5,
        "position_long": -73.5,
        "power": 200,
        "heart_rate": 155,
        "cadence": 180,
        "distance": 1000.0,
        "enhanced_altitude": 100.0,
        "speed": 3.33,
    }.get(x)

    # Set up messages property to return all messages
    fit_file.messages = [lap_message, lap_message, record_message, record_message]
    return fit_file

@pytest.mark.asyncio
async def test_start_upload(
    app,
    test_client,
    mock_repository,
    mock_redis,
    upload_request,
    mock_fit_file,
    monkeypatch
):
    """Test the start_upload endpoint."""
    async def mock_get_repository():
        return mock_repository
    
    app.dependency_overrides[get_activity_repository] = mock_get_repository
    
    # Mock FitFile class
    with patch('data_ingestion.main.FitFile', return_value=mock_fit_file):
        # Create test file content
        test_file = b"mock fit file content"
        
        # Make the request with proper multipart form data
        response = test_client.post(
            "/activities",
            files=[
                ("fit_files", ("test.fit", test_file, "application/octet-stream")),
            ],
            data={
                "request": upload_request.model_dump_json(),
            }
        )
        
        # Print response for debugging
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.json()}")
        
        # Assert response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == UploadStatus.PENDING.value
        assert response_data["total_activities"] == 1
        assert response_data["processed_activities"] == 0
        
        # Assert Redis calls
        mock_redis.set.assert_called()
        
        # Clean up
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_upload_status(app, test_client, mock_redis):
    """Test the get_upload_status endpoint."""
    activity_id = "test123"
    batch_id = "batch123"
    status_data = {
        "status": UploadStatus.COMPLETED.value,
        "error_message": "",
        "batch_id": batch_id,
        "last_updated": datetime.now().isoformat(),
        "total_activities": 1,
        "processed_activities": 1,
        "failed_activities": 0,
    }
    
    # Mock Redis response
    mock_redis.hgetall.return_value = status_data
    
    # Make the request
    response = test_client.get(f"/activities/{activity_id}/status")
    
    # Assert response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == UploadStatus.COMPLETED.value
    assert response_data["batch_id"] == batch_id
    assert "last_updated" in response_data
    
    # Assert Redis call
    mock_redis.hgetall.assert_called_once_with(f"status:{activity_id}")

@pytest.mark.asyncio
async def test_get_upload_status_not_found(app, test_client, mock_redis):
    """Test the get_upload_status endpoint with non-existent activity."""
    activity_id = "nonexistent"
    
    # Mock Redis response for non-existent activity
    mock_redis.hgetall.return_value = {}
    
    # Make the request
    response = test_client.get(f"/activities/{activity_id}/status")
    
    # Assert response
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found" 
