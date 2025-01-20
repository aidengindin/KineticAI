import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
from fitparse import FitFile

from data_ingestion.db.activities import ActivityRepository
from kinetic_common.models import (
    PydanticActivity,
    PydanticActivityLap,
    PydanticActivityStream,
    Activity,
    ActivityLap,
    ActivityStream,
)
from data_ingestion.models import UploadStatus

@pytest.fixture
def mock_db():
    """Create a mock async session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.add = AsyncMock()
    session.run_sync = AsyncMock()
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
    """Create a mock FitFile."""
    fit_file = Mock(spec=FitFile)
    
    # Create mock messages
    mock_messages = []
    
    # Add 2 lap messages
    for i in range(2):
        message = Mock()
        message.name = "lap"
        message.mesg_num = 19  # This is the message number for lap messages
        
        # Create mock fields for lap
        lap_field_names = ["start_time", "total_elapsed_time", "total_distance", "avg_speed",
                          "avg_heart_rate", "avg_cadence", "avg_power",
                          "left_right_balance", "intensity"]
        mock_fields = []
        for field_name in lap_field_names:
            field = Mock()
            field.name = field_name
            mock_fields.append(field)
        message.fields = mock_fields
        
        message.get_value = Mock(side_effect=lambda field: {
            "start_time": datetime.now(),
            "total_elapsed_time": 300.0,
            "total_distance": 1000.0,
            "avg_speed": 3.33,
            "avg_heart_rate": 155,
            "avg_cadence": 85,
            "avg_power": 210,
            "left_right_balance": 50.5,
            "intensity": "active",
        }.get(field))
        mock_messages.append(message)
    
    # Add 5 record messages
    for i in range(5):
        message = Mock()
        message.name = "record"
        message.mesg_num = 20  # This is the message number for record messages
        
        # Create mock fields for record
        record_field_names = ["timestamp", "heart_rate", "cadence", "power", "speed", 
                            "position_lat", "position_long", "altitude", "temperature"]
        mock_fields = []
        for field_name in record_field_names:
            field = Mock()
            field.name = field_name
            mock_fields.append(field)
        message.fields = mock_fields
        
        message.get_value = Mock(side_effect=lambda field: {
            "timestamp": datetime.now(),
            "heart_rate": 150,
            "cadence": 80,
            "power": 200,
            "speed": 3.0,
            "position_lat": 45.5,
            "position_long": -73.5,
            "enhanced_altitude": 100,
            "temperature": 20,
        }.get(field))
        mock_messages.append(message)
    
    # Set up get_messages to return a new iterator each time it's called
    def get_messages():
        return iter(mock_messages)
    
    fit_file.get_messages = Mock(side_effect=get_messages)
    
    return fit_file

@pytest.mark.asyncio
async def test_create_activity(repository, sample_activity_data):
    """Test creating an activity."""
    fit_file_bytes = b"mock fit file content"
    
    # Convert dict to Pydantic model
    activity = PydanticActivity(**sample_activity_data)
    
    # Call the method
    await repository.create_activity(activity, fit_file_bytes)
    
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
    assert len(repository.db.add.call_args_list) == 2  # Two lap messages
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
    
    # Assert bulk_save_objects was called and committed
    repository.db.run_sync.assert_called_once()
    repository.db.commit.assert_called_once()
    
    # Get the bulk_save_objects function that was called
    bulk_save_fn = repository.db.run_sync.call_args[0][0]
    session_mock = Mock()
    bulk_save_fn(session_mock)
    
    # Verify bulk_save_objects was called with the correct number of streams
    assert session_mock.bulk_save_objects.call_count == 1
    streams = session_mock.bulk_save_objects.call_args[0][0]
    assert len(streams) == 5  # We expect 5 streams
    
    # Check the first stream that was saved
    first_stream = streams[0]
    assert isinstance(first_stream, ActivityStream)  # Now checking against SQLAlchemy model
    assert first_stream.activity_id == activity_id
    assert first_stream.sequence == 0
    assert first_stream.latitude == 45.5
    assert first_stream.longitude == -73.5
    assert first_stream.power == 200
    assert first_stream.heart_rate == 150  # First message heart_rate 
