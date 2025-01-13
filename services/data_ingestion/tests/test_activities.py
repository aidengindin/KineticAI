import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
from fitparse import FitFile

from data_ingestion.db.activities import ActivityRepository
from data_ingestion.models import Activity, ActivityLap, ActivityStream

@pytest.fixture
def mock_db():
    """Create a mock async session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.add = AsyncMock()
    return session

@pytest.fixture
def repository(mock_db):
    """Create an ActivityRepository instance with a mock db."""
    return ActivityRepository(mock_db)

@pytest.fixture
def sample_activity_data():
    """Create sample activity data."""
    return {
        "id": "test123",
        "start_date": datetime.now(),
        "name": "Morning Run",
        "sport_type": "running",
        "duration": 3600.0,
        "distance": 10000.0,
        "average_speed": 2.78,
        "average_heartrate": 150,
    }

@pytest.fixture
def mock_fit_file():
    """Create a mock FitFile with sample messages."""
    fit_file = Mock(spec=FitFile)
    
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
async def test_create_activity(repository, sample_activity_data):
    """Test creating an activity."""
    fit_file_bytes = b"mock fit file content"
    
    # Call the method
    await repository.create_activity(sample_activity_data, fit_file_bytes)
    
    # Assert the activity was added to the session
    repository.db.add.assert_called_once()
    repository.db.commit.assert_called_once()
    
    # Get the Activity object that was added
    added_activity = repository.db.add.call_args[0][0]
    assert isinstance(added_activity, Activity)
    assert added_activity.id == sample_activity_data["id"]
    assert added_activity.name == sample_activity_data["name"]
    assert added_activity.fit_file == fit_file_bytes

@pytest.mark.asyncio
async def test_store_laps(repository, mock_fit_file):
    """Test storing lap data."""
    activity_id = "test123"
    
    # Call the method
    await repository.store_laps(activity_id, mock_fit_file)
    
    # Assert laps were added and committed
    assert repository.db.add.call_count == 2  # Two lap messages
    repository.db.commit.assert_called_once()
    
    # Check the first lap that was added
    first_lap = repository.db.add.call_args_list[0][0][0]
    assert isinstance(first_lap, ActivityLap)
    assert first_lap.activity_id == activity_id
    assert first_lap.sequence == 0
    assert first_lap.average_speed == 3.33
    assert first_lap.average_heartrate == 155

@pytest.mark.asyncio
async def test_store_streams(repository, mock_fit_file):
    """Test storing stream data."""
    activity_id = "test123"
    
    # Call the method
    await repository.store_streams(activity_id, mock_fit_file)
    
    # Assert streams were added and committed
    assert repository.db.add.call_count == 2  # Two record messages
    repository.db.commit.assert_called_once()
    
    # Check the first stream that was added
    first_stream = repository.db.add.call_args_list[0][0][0]
    assert isinstance(first_stream, ActivityStream)
    assert first_stream.activity_id == activity_id
    assert first_stream.sequence == 0
    assert first_stream.latitude == 45.5
    assert first_stream.longitude == -73.5
    assert first_stream.power == 200
    assert first_stream.heart_rate == 155 