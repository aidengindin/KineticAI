import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from src import config
from src.models import SyncStatus, SyncStatusResponse
from src.sync import SyncManager


@pytest.mark.asyncio
@patch("src.config.Settings.get_intervals_api_key", return_value="test_api_key")
async def test_get_status_pending(mock_get_intervals_api_key):
    # Mock Redis client
    redis_client = MagicMock()
    redis_client.get.return_value = None

    # Create SyncManager instance
    sync_manager = SyncManager(redis_client)

    # Call get_status method
    user_id = "test_user"
    response = await sync_manager.get_status(user_id)

    # Assert the response
    assert response.status == SyncStatus.PENDING
    assert response.last_updated <= datetime.now(timezone.utc)


@pytest.mark.asyncio
@patch("src.config.Settings.get_intervals_api_key", return_value="test_api_key")
async def test_get_status_existing(mock_get_intervals_api_key):
    # Mock Redis client
    redis_client = MagicMock()
    mock_data = {
        "status": SyncStatus.IN_PROGRESS,
        "total_activities": 10,
        "processed_activities": 5,
        "failed_activities": 1,
        "error_message": None,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    redis_client.get.return_value = json.dumps(mock_data)

    # Create SyncManager instance
    sync_manager = SyncManager(redis_client)

    # Call get_status method
    user_id = "test_user"
    response = await sync_manager.get_status(user_id)

    # Assert the response
    assert response.status == SyncStatus.IN_PROGRESS
    assert response.total_activities == 10
    assert response.processed_activities == 5
    assert response.failed_activities == 1
    assert response.error_message is None
    assert response.last_updated.isoformat() == mock_data["last_updated"]


@pytest.mark.asyncio
@patch("src.config.Settings.get_intervals_api_key", return_value="test_api_key")
async def test_update_status_new(mock_get_intervals_api_key):
    # Mock Redis client
    redis_client = MagicMock()
    redis_client.get.return_value = None

    # Create SyncManager instance
    sync_manager = SyncManager(redis_client)

    # Call update_status method
    user_id = "test_user"
    status = SyncStatus.IN_PROGRESS
    total = 10
    processed = 5
    failed = 1
    error = "Some error"

    response = await sync_manager.update_status(
        user_id, status, total, processed, failed, error
    )

    # Assert the response
    assert response.status == SyncStatus.IN_PROGRESS
    assert response.total_activities == 10
    assert response.processed_activities == 5
    assert response.failed_activities == 1
    assert response.error_message == "Some error"
    assert response.last_updated <= datetime.now(timezone.utc)

    # Assert Redis set call
    redis_client.set.assert_called_once()
    key = sync_manager._get_status_key(user_id)
    redis_client.set.assert_called_with(key, response.model_dump_json())


@pytest.mark.asyncio
@patch("src.config.Settings.get_intervals_api_key", return_value="test_api_key")
async def test_update_status_existing(mock_get_intervals_api_key):
    # Mock Redis client
    redis_client = MagicMock()
    mock_data = {
        "status": SyncStatus.IN_PROGRESS,
        "total_activities": 10,
        "processed_activities": 5,
        "failed_activities": 1,
        "error_message": None,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    redis_client.get.return_value = json.dumps(mock_data)

    # Create SyncManager instance
    sync_manager = SyncManager(redis_client)

    # Call update_status method
    user_id = "test_user"
    status = SyncStatus.COMPLETED
    total = 15
    processed = 15
    failed = 0
    error = None

    response = await sync_manager.update_status(
        user_id, status, total, processed, failed, error
    )

    # Assert the response
    assert response.status == SyncStatus.COMPLETED
    assert response.total_activities == 15
    assert response.processed_activities == 15
    assert response.failed_activities == 0
    assert response.error_message is None
    assert response.last_updated <= datetime.now(timezone.utc)

    # Assert Redis set call
    redis_client.set.assert_called_once()
    key = sync_manager._get_status_key(user_id)
    redis_client.set.assert_called_with(key, response.model_dump_json())


@pytest.mark.asyncio
async def test_fetch_activities_success(mocker):
    mocker.patch(
        "src.config.Settings.get_intervals_api_key", return_value="test_api_key"
    )
    mocker.patch("src.sync.settings.INTERVALS_API_BASE_URL", "https://intervals.test")

    # Mock Redis client and response data
    redis_client = MagicMock()
    mock_activities = [
        {
            "id": "123",
            "start_date_local": "2024-01-01T10:00:00",
            "name": "Morning Run",
            "type": "run",
            "moving_time": 3600,
            "icu_distance": 10000,
        }
    ]

    session = MagicMock()
    session.closed = False
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value=mock_activities)
    session_get_return_value = MagicMock()
    session_get_return_value.__aenter__ = AsyncMock(return_value=mock_response)
    session_get_return_value.__aexit__ = AsyncMock(return_value=None)
    session.get.return_value = session_get_return_value

    sync_manager = SyncManager(redis_client)
    sync_manager._session = session

    # Test parameters
    user_id = "test_user"
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

    # Call fetch_activities
    activities = await sync_manager.fetch_activities(user_id, start_date, end_date)

    # Assertions
    assert len(activities) == 1
    activity = activities[0]
    assert activity.id == "123"
    assert activity.name == "Morning Run"
    assert activity.sport_type == "run"
    assert activity.duration == 3600
    assert activity.distance == 10000

    # Verify correct URL and parameters were used
    expected_url = f"https://intervals.test/athlete/{user_id}/activities"
    expected_params = {"oldest": "2024-01-01T00:00:00", "newest": "2024-01-02T00:00:00"}
    session.get.assert_called_once_with(expected_url, params=expected_params)


@pytest.mark.asyncio
@patch("src.config.Settings.get_intervals_api_key", return_value="test_api_key")
async def test_fetch_activities_http_error(mock_get_intervals_api_key):
    # Mock Redis client
    redis_client = MagicMock()

    # Mock aiohttp ClientSession with error
    session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.raise_for_status.side_effect = aiohttp.ClientError()
    session.get.return_value.__aenter__.return_value = mock_response

    sync_manager = SyncManager(redis_client)
    sync_manager._session = session

    # Test parameters
    user_id = "test_user"
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

    # Assert that ClientError is raised
    with pytest.raises(aiohttp.ClientError):
        await sync_manager.fetch_activities(user_id, start_date, end_date)
