import pytest
from unittest.mock import Mock, patch, AsyncMock
import unittest.mock as mock
from datetime import datetime
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from data_ingestion.main import create_app, get_activity_repository, json_dumps
from data_ingestion.models import UploadRequest, Activity, UploadStatus
import asyncio

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
    session_message = Mock()
    session_message.mesg_type = "session"
    session_message.get = lambda x: {
        "start_time": datetime.now(),
        "total_elapsed_time": 3600.0,
        "total_distance": 10000.0,
        "avg_speed": 2.78,
        "avg_heart_rate": 150,
        "sport": "running",
    }.get(x)

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

    # Set up messages as an iterator
    messages = [session_message, lap_message, lap_message, record_message, record_message]
    fit_file.messages = iter(messages)  # Make messages an iterator directly
    
    # Also make the fit_file itself iterable to return a new iterator each time
    fit_file.__iter__ = lambda self: iter([session_message, lap_message, lap_message, record_message, record_message])
    
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

@pytest.mark.asyncio
async def test_start_upload_invalid_request(
    app,
    test_client,
    mock_repository,
    mock_redis,
    monkeypatch
):
    """Test start_upload with invalid request data."""
    async def mock_get_repository():
        return mock_repository
    
    app.dependency_overrides[get_activity_repository] = mock_get_repository
    
    # Create test file content
    test_file = b"mock fit file content"
    
    # Make request with invalid JSON
    response = test_client.post(
        "/activities",
        files=[
            ("fit_files", ("test.fit", test_file, "application/octet-stream")),
        ],
        data={
            "request": "invalid json",
        }
    )
    
    assert response.status_code == 422
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_start_upload_mismatched_files(
    app,
    test_client,
    mock_repository,
    mock_redis,
    upload_request,
    monkeypatch
):
    """Test start_upload with mismatched number of files and activities."""
    async def mock_get_repository():
        return mock_repository
    
    app.dependency_overrides[get_activity_repository] = mock_get_repository
    
    # Create test file content
    test_file = b"mock fit file content"
    
    # Make request with too few files
    response = test_client.post(
        "/activities",
        files=[],  # No files
        data={
            "request": upload_request.model_dump_json(),
        }
    )
    
    assert response.status_code == 422
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_process_with_status_error(
    app,
    test_client,
    mock_repository,
    mock_redis,
    upload_request,
    mock_fit_file,
    monkeypatch
):
    """Test process_with_status when task fails."""
    # Set up repository mock to fail
    error_message = "Test error during activity creation"
    mock_repository.create_activity.side_effect = Exception(error_message)
    
    async def mock_get_repository():
        return mock_repository

    app.dependency_overrides[get_activity_repository] = mock_get_repository

    # Track Redis status updates
    status_updates = {}

    async def mock_redis_set(key: str, value: str):
        print(f"Setting Redis key {key} with value {value}")  # Debug print
        status_updates[key] = value
        return True

    async def mock_redis_get(key: str):
        return status_updates.get(key)

    mock_redis.set.side_effect = mock_redis_set
    mock_redis.get.side_effect = mock_redis_get

    # Mock FitFile class to return our mock_fit_file
    with patch('data_ingestion.main.FitFile', return_value=mock_fit_file):
        # Create test file content
        test_file = b"mock fit file content"

        # Make the request
        response = test_client.post(
            "/activities",
            files=[
                ("fit_files", ("test.fit", test_file, "application/octet-stream")),
            ],
            data={
                "request": upload_request.model_dump_json(),
            }
        )

        # Initial response should still be 200
        assert response.status_code == 200

        # Wait for background tasks to complete
        await asyncio.sleep(0.5)

        # Check that error status was set
        activity_id = upload_request.activities[0].id
        activity_key = f"activity:{activity_id}"

        # Verify the status was updated
        assert activity_key in status_updates, "Activity status was not updated"
        status_data = json.loads(status_updates[activity_key])
        assert status_data["status"] == UploadStatus.FAILED.value
        
        # Verify error message includes function name
        expected_error = f"Error in AsyncMock: {error_message}"
        assert expected_error in status_data.get("error", ""), f"Expected error message '{expected_error}' not found in status data: {status_data}"

        # Verify status transitions
        status_updates_list = []
        for args, kwargs in mock_redis.set.call_args_list:
            if args[0] == activity_key:
                status_data = json.loads(args[1])
                status_updates_list.append(status_data["status"])
        
        # Should see: PENDING -> IN_PROGRESS -> FAILED
        assert status_updates_list == [UploadStatus.PENDING.value, UploadStatus.IN_PROGRESS.value, UploadStatus.FAILED.value], \
            f"Unexpected status transitions: {status_updates_list}"

    # Clean up
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_start_upload_invalid_file_type(
    app,
    test_client,
    mock_repository,
    mock_redis,
    upload_request,
    monkeypatch
):
    """Test start_upload with invalid file type."""
    async def mock_get_repository():
        return mock_repository
    
    app.dependency_overrides[get_activity_repository] = mock_get_repository
    
    # Create test file content
    test_file = b"not a fit file"
    
    # Make request with non-FIT file
    response = test_client.post(
        "/activities",
        files=[
            ("fit_files", ("test.txt", test_file, "text/plain")),
        ],
        data={
            "request": upload_request.model_dump_json(),
        }
    )
    
    assert response.status_code == 422
    assert "Invalid file type" in response.json()["detail"]
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_start_upload_redis_failure(
    app,
    test_client,
    mock_repository,
    mock_redis,
    upload_request,
    mock_fit_file,
    monkeypatch
):
    """Test start_upload when Redis operations fail."""
    async def mock_get_repository():
        return mock_repository
    
    app.dependency_overrides[get_activity_repository] = mock_get_repository
    
    # Mock Redis failure
    mock_redis.set.side_effect = Exception("Redis connection error")
    
    # Mock FitFile class
    with patch('data_ingestion.main.FitFile', return_value=mock_fit_file):
        # Create test file content
        test_file = b"mock fit file content"
        
        # Make the request
        response = test_client.post(
            "/activities",
            files=[
                ("fit_files", ("test.fit", test_file, "application/octet-stream")),
            ],
            data={
                "request": upload_request.model_dump_json(),
            }
        )
        
        assert response.status_code == 500
        assert "Failed to initialize batch status" in response.json()["detail"]
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_start_upload_invalid_fit_file(
    app,
    test_client,
    mock_repository,
    mock_redis,
    upload_request,
    monkeypatch
):
    """Test start_upload with invalid FIT file content."""
    async def mock_get_repository():
        return mock_repository
    
    app.dependency_overrides[get_activity_repository] = mock_get_repository
    
    # Mock FitFile to raise an error
    def mock_fit_file_error(*args, **kwargs):
        raise Exception("Invalid FIT file format")
    
    with patch('data_ingestion.main.FitFile', side_effect=mock_fit_file_error):
        # Create test file content
        test_file = b"invalid fit file content"
        
        # Make the request
        response = test_client.post(
            "/activities",
            files=[
                ("fit_files", ("test.fit", test_file, "application/octet-stream")),
            ],
            data={
                "request": upload_request.model_dump_json(),
            }
        )
        
        # Initial response should still be 200 as the error is handled
        assert response.status_code == 200
        
        # Wait for background tasks
        await asyncio.sleep(0.5)
        
        # Verify activity status was updated
        activity_id = upload_request.activities[0].id
        
        # Get the actual call arguments
        call_args = mock_redis.set.call_args_list
        found_status_update = False
        
        for args, kwargs in call_args:
            if args[0] == f"activity:{activity_id}":
                status_data = json.loads(args[1])
                assert status_data["activity_id"] == activity_id
                assert status_data["status"] == UploadStatus.FAILED.value
                assert status_data["error_message"] == "Invalid FIT file: Invalid FIT file format"
                assert status_data["completed_tasks"] == 0
                assert "last_updated" in status_data  # Just verify the field exists
                found_status_update = True
                break
        
        assert found_status_update, "Activity status update not found in Redis calls"
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_start_upload_redis_batch_failure(mock_redis, mock_repository):
    """Test that Redis failure during batch status initialization is handled correctly."""
    # Mock Redis to fail on batch status initialization
    mock_redis.set.side_effect = [Exception("Redis connection error"), None]  # First call fails, subsequent calls succeed
    
    # Create test client with mocked Redis
    app = create_app(mock_redis)
    test_client = TestClient(app)
    
    # Create test data
    activity_id = "test123"
    activity = Activity(
        id=activity_id,
        name="Test Activity",
        start_date=datetime.now(),
        sport_type="run",
        duration=3600,
    )
    request = UploadRequest(user_id="user123", activities=[activity])
    
    # Create test file
    file_content = b"test fit file content"
    files = [("fit_files", ("test.fit", file_content, "application/octet-stream"))]
    data = {"request": request.model_dump_json()}
    
    # Make request and check response
    response = test_client.post("/activities", files=files, data=data)
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to initialize batch status"
    
    # Verify Redis was called correctly
    mock_redis.set.assert_called_once()
    assert "batch:" in mock_redis.set.call_args[0][0]  # First arg should be key starting with "batch:"

@pytest.mark.asyncio
async def test_start_upload_invalid_fit_content(mock_redis, mock_repository):
    """Test that invalid FIT file content is handled correctly."""
    # Create test client with mocked Redis
    app = create_app(mock_redis)
    test_client = TestClient(app)
    
    # Create test data
    activity_id = "test123"
    activity = Activity(
        id=activity_id,
        name="Test Activity",
        start_date=datetime.now(),
        sport_type="run",
        duration=3600,
    )
    request = UploadRequest(user_id="user123", activities=[activity])
    
    # Create invalid test file (not a real FIT file)
    file_content = b"not a real fit file"
    files = [("fit_files", ("test.fit", file_content, "application/octet-stream"))]
    data = {"request": request.model_dump_json()}
    
    # Make request and check response
    response = test_client.post("/activities", files=files, data=data)
    assert response.status_code == 200  # Should still return 200 as this is handled gracefully
    
    # Verify Redis was called to update activity status to FAILED
    # Get the actual call arguments
    call_args = mock_redis.set.call_args_list
    found_status_update = False
    
    for args, kwargs in call_args:
        if args[0] == f"activity:{activity_id}":
            status_data = json.loads(args[1])
            assert status_data["activity_id"] == activity_id
            assert status_data["status"] == "failed"
            assert "Invalid FIT file:" in status_data["error_message"]
            assert status_data["completed_tasks"] == 0
            assert "last_updated" in status_data  # Just verify the field exists
            found_status_update = True
            break
    
    assert found_status_update, "Activity status update not found in Redis calls"

@pytest.mark.asyncio
async def test_start_upload_redis_activity_failure(mock_redis, mock_repository, mock_fit_file):
    """Test that Redis failure during activity status update is handled correctly."""
    # Mock Redis to fail on activity status update
    mock_redis.set.side_effect = [
        None,  # batch status succeeds
        Exception("Redis connection error"),  # activity status fails
    ]
    
    # Create test client with mocked Redis
    app = create_app(mock_redis)
    test_client = TestClient(app)
    
    # Create test data
    activity_id = "test123"
    activity = Activity(
        id=activity_id,
        name="Test Activity",
        start_date=datetime.now(),
        sport_type="run",
        duration=3600,
    )
    request = UploadRequest(user_id="user123", activities=[activity])
    
    # Create test file
    file_content = b"test fit file content"
    files = [("fit_files", ("test.fit", file_content, "application/octet-stream"))]
    data = {"request": request.model_dump_json()}
    
    # Make request and check response
    response = test_client.post("/activities", files=files, data=data)
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to update activity status"
    
    # Verify Redis calls
    assert mock_redis.set.call_count == 2
    assert "batch:" in mock_redis.set.call_args_list[0][0][0]  # First call should be batch status
    assert f"activity:{activity_id}" == mock_redis.set.call_args_list[1][0][0]  # Second call should be activity status

@pytest.mark.asyncio
async def test_get_upload_status_redis_failure(mock_redis):
    """Test that Redis failure during get_upload_status is handled correctly."""
    # Mock Redis to fail
    mock_redis.hgetall.side_effect = Exception("Redis connection error")
    
    # Create test client with mocked Redis
    app = create_app(mock_redis)
    test_client = TestClient(app)
    
    # Make request and check response
    activity_id = "test123"
    response = test_client.get(f"/activities/{activity_id}/status")
    assert response.status_code == 500
    assert "Redis connection error" in response.json()["detail"]
    
    # Verify Redis was called correctly
    mock_redis.hgetall.assert_called_once_with(f"status:{activity_id}")

def test_main_cli(monkeypatch):
    """Test the main CLI entrypoint."""
    import sys
    from unittest.mock import patch
    import uvicorn
    from data_ingestion.main import create_app
    
    # Mock sys.argv
    test_args = ["main.py", "--host", "127.0.0.1", "--port", "8001", "--reload", "--log-level", "debug"]
    monkeypatch.setattr(sys, "argv", test_args)
    
    # Mock uvicorn.run
    with patch("uvicorn.run") as mock_run:
        # Import and run the main function directly
        from data_ingestion.main import main
        main()
        
        # Verify uvicorn.run was called with correct args
        mock_run.assert_called_once_with(
            "main:app",
            host="127.0.0.1",
            port=8001,
            reload=True,
            log_level="debug"
        )
