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
from typing import Optional

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
    redis.hset = AsyncMock(return_value=True)
    
    # Track completed tasks count
    completed_tasks = {}
    
    async def mock_hincrby(key: str, field: str, increment: int):
        if field == "completed_tasks":
            completed_tasks[key] = completed_tasks.get(key, 0) + increment
            return completed_tasks[key]
        return 1
    
    async def mock_hget(key: str, field: str):
        if field == "completed_tasks":
            return str(completed_tasks.get(key, 0))
        return "0"
    
    async def mock_execute():
        count = await mock_hincrby("", "completed_tasks", 1)
        tasks = await mock_hget("", "completed_tasks")
        return [count, tasks]
    
    # Mock pipeline operations
    redis.pipeline = Mock(return_value=redis)  # Mock pipeline to return self
    redis.hincrby = AsyncMock(side_effect=mock_hincrby)
    redis.hget = AsyncMock(side_effect=mock_hget)
    redis.execute = AsyncMock(side_effect=mock_execute)
    
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
    fit_file.get_messages.return_value = [Mock()]  # Return at least one message
    return fit_file

@pytest.fixture
async def mock_update_activity_status():
    """Create a mock for update_activity_status."""
    async def mock_func(activity_id: str, status: UploadStatus, error_message: Optional[str] = None) -> None:
        print(f"Mocked update_activity_status called for {activity_id} with status {status} and error {error_message}")
    return mock_func

@pytest.mark.asyncio
async def test_start_upload(
    app,
    test_client,
    mock_repository,
    mock_redis,
    upload_request,
    mock_fit_file,
    mock_update_activity_status,
    monkeypatch
):
    """Test the start_upload endpoint."""
    with patch('data_ingestion.main.update_activity_status', side_effect=mock_update_activity_status) as mock_update:
        async def mock_get_repository():
            return mock_repository
        
        # Add debug prints to repository methods
        async def debug_create_activity(*args, **kwargs):
            print("Creating activity...")
            return None
        
        async def debug_store_laps(*args, **kwargs):
            print("Storing laps...")
            return None
        
        async def debug_store_streams(*args, **kwargs):
            print("Storing streams...")
            return None
        
        mock_repository.create_activity.side_effect = debug_create_activity
        mock_repository.store_laps.side_effect = debug_store_laps
        mock_repository.store_streams.side_effect = debug_store_streams
        
        app.dependency_overrides[get_activity_repository] = mock_get_repository
        app.state.redis_client = mock_redis
        
        # Mock Redis batch status operations to succeed
        mock_redis.hset.return_value = True
        
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
            
            # Assert response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["status"] == UploadStatus.PENDING.value
            assert response_data["total_activities"] == 1
            assert response_data["processed_activities"] == 0
            
            # Wait for background tasks to complete
            print("\nWaiting for background tasks...")
            await asyncio.sleep(1)
            
            # Verify activity was processed
            activity_id = upload_request.activities[0].id
            
            # Print all status updates for debugging
            print("\nAll status updates:")
            for call in mock_update.call_args_list:
                status_args = call.args
                error_msg = status_args[2] if len(status_args) > 2 else None
                print(f"Status update: activity_id={status_args[0]}, status={status_args[1]}, error={error_msg}")
            
            # Verify repository methods were called
            mock_repository.create_activity.assert_called_once()
            mock_repository.store_laps.assert_called_once()
            mock_repository.store_streams.assert_called_once()
            
            # Get all status updates for this activity
            status_updates = [
                (call.args[0], call.args[1])
                for call in mock_update.call_args_list
                if call.args[0] == activity_id
            ]
            
            # Print status updates for debugging
            print("\nStatus updates for activity:", activity_id)
            for activity_id, status in status_updates:
                print(f"Status: {status}")
            
            # Verify we have both IN_PROGRESS and COMPLETED statuses
            assert any(status == UploadStatus.IN_PROGRESS for _, status in status_updates), \
                "Activity was never set to IN_PROGRESS"
            assert any(status == UploadStatus.COMPLETED for _, status in status_updates), \
                "Activity was never set to COMPLETED"
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_upload_status(app, test_client, mock_redis):
    """Test the get_upload_status endpoint."""
    activity_id = "test123"
    status_data = {
        "activity_id": activity_id,
        "status": UploadStatus.COMPLETED.value,
        "error_message": None,
        "completed_tasks": 3,  # All tasks completed (create_activity, store_laps, store_streams)
        "last_updated": datetime.now().isoformat(),
    }
    
    # Mock Redis response
    mock_redis.hgetall.return_value = status_data
    
    # Make the request
    response = test_client.get(f"/activities/{activity_id}/status")
    
    # Assert response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == UploadStatus.COMPLETED.value
    assert response_data["activity_id"] == activity_id
    assert response_data["completed_tasks"] == 3
    assert response_data["error_message"] is None
    assert "last_updated" in response_data
    
    # Verify Redis was called correctly
    mock_redis.hgetall.assert_called_once_with(f"activity:{activity_id}")

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
    
    async def mock_update_activity_status(activity_id: str, status: UploadStatus, error_message: Optional[str] = None) -> None:
        print(f"Mocked update_activity_status called for {activity_id} with status {status} and error {error_message}")
    
    with patch('data_ingestion.main.update_activity_status', side_effect=mock_update_activity_status) as mock_update:
        # Set up repository mock to fail
        error_message = "Test error during activity creation"
        mock_repository.create_activity.side_effect = Exception(error_message)
        
        async def mock_get_repository():
            return mock_repository
        
        app.dependency_overrides[get_activity_repository] = mock_get_repository
        app.state.redis_client = mock_redis
        
        # Mock FitFile to return valid messages
        mock_fit_file.get_messages.return_value = [Mock()]
        
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
            
            # Initial response should still be 200
            assert response.status_code == 200
            
            # Wait for background tasks to complete
            await asyncio.sleep(0.5)
            
            # Check that error status was set
            activity_id = upload_request.activities[0].id
            
            # Verify the mock was called
            mock_update.assert_called()
            # Check that the last call was with FAILED status
            last_call = mock_update.call_args_list[-1]
            assert last_call.args[0] == activity_id  # Check activity_id
            assert last_call.args[1] == UploadStatus.FAILED  # Check status
            assert error_message in last_call.args[2]  # Check error message contains our original error
    
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
    mock_update_activity_status,
    monkeypatch
):
    """Test start_upload when Redis operations fail during batch initialization."""
    with patch('data_ingestion.main.update_activity_status', side_effect=mock_update_activity_status) as mock_update:
        async def mock_get_repository():
            return mock_repository
        
        app.dependency_overrides[get_activity_repository] = mock_get_repository
        app.state.redis_client = mock_redis
        
        # Mock Redis failure during batch initialization
        mock_redis.hset.side_effect = Exception("Redis connection error")
        
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
            
            # Batch initialization happens before background tasks, so this should fail immediately
            assert response.status_code == 500
            assert "Failed to initialize batch status" in response.json()["detail"]
            
            # Mock should not have been called since we failed before background tasks
            mock_update.assert_not_called()
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_start_upload_redis_activity_failure(
    app,
    test_client,
    mock_repository,
    mock_redis,
    upload_request,
    mock_fit_file,
    mock_update_activity_status,
    monkeypatch
):
    """Test that Redis failure during activity status update is handled correctly."""
    with patch('data_ingestion.main.update_activity_status', side_effect=mock_update_activity_status) as mock_update:
        async def mock_get_repository():
            return mock_repository
        
        app.dependency_overrides[get_activity_repository] = mock_get_repository
        app.state.redis_client = mock_redis
        
        # Mock Redis failure for activity status but success for batch status
        mock_redis.hset.side_effect = [
            True,  # batch status succeeds
            Exception("Redis connection error"),  # activity status fails
        ]
        
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
            
            # Initial response should be 200 since batch initialization succeeds
            assert response.status_code == 200
            
            # Wait for background tasks to complete
            await asyncio.sleep(0.5)
            
            # Check that error status was set
            activity_id = upload_request.activities[0].id
            
            # Verify the mock was called
            mock_update.assert_called()
            # Check that the last call was with FAILED status
            last_call = mock_update.call_args_list[-1]
            assert last_call.args[0] == activity_id
            assert last_call.args[1] == UploadStatus.FAILED
            assert "Redis connection error" in last_call.args[2]
    
    # Clean up
    app.dependency_overrides.clear()

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
    mock_redis.hgetall.assert_called_once_with(f"activity:{activity_id}")

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
            "data_ingestion.main:app",
            host="127.0.0.1",
            port=8001,
            reload=True,
            log_level="debug"
        )
