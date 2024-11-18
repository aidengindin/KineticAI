import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from src.sync import SyncManager
from src.models import SyncStatus, SyncStatusResponse

@pytest.mark.asyncio
async def test_get_status_pending():
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
async def test_get_status_existing():
    # Mock Redis client
    redis_client = MagicMock()
    mock_data = {
        "status": SyncStatus.IN_PROGRESS,
        "total_activities": 10,
        "processed_activities": 5,
        "failed_activities": 1,
        "error_message": None,
        "last_updated": datetime.now(timezone.utc).isoformat()
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