import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock
from sqlalchemy import select

from data_retrieval.db.activities import ActivityRepository
from kinetic_common.models import Activity, ActivityLap, ActivityStream

@pytest.mark.asyncio
async def test_get_activity(repository, mock_db, sample_activity):
    """Test getting a single activity."""
    # Mock the database response
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = sample_activity
    mock_db.execute.return_value = mock_result

    # Get the activity
    activity = await repository.get_activity("test123")

    # Verify the query
    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][0]
    assert str(call_args) == str(select(Activity).where(Activity.id == "test123"))

    # Verify the result
    assert activity is not None
    assert activity.id == "test123"
    assert activity.name == "Morning Run"
    assert activity.sport_type == "running"

@pytest.mark.asyncio
async def test_get_activity_not_found(repository, mock_db):
    """Test getting a non-existent activity."""
    # Mock the database response
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    # Get the activity
    activity = await repository.get_activity("nonexistent")

    # Verify the query
    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][0]
    assert str(call_args) == str(select(Activity).where(Activity.id == "nonexistent"))

    # Verify the result
    assert activity is None

@pytest.mark.asyncio
async def test_get_activities(repository, mock_db, sample_activities):
    """Test getting activities with filters."""
    # Mock the database response
    mock_result = Mock()
    mock_result.scalars.return_value.all.return_value = sample_activities
    mock_db.execute.return_value = mock_result

    # Test parameters
    user_id = "user123"
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    sport_type = "running"
    limit = 3
    offset = 1

    # Get activities
    activities = await repository.get_activities(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        sport_type=sport_type,
        limit=limit,
        offset=offset,
    )

    # Verify the query
    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][0]
    query_str = str(call_args)
    
    # Check query components
    assert "WHERE activities.user_id = :user_id_1" in query_str
    assert "activities.start_date >= :start_date_1" in query_str
    assert "activities.start_date <= :start_date_2" in query_str
    assert "activities.sport_type = :sport_type_1" in query_str
    assert "LIMIT :param_1 OFFSET :param_2" in query_str

    # Verify the results
    assert len(activities) == len(sample_activities)
    for activity in activities:
        assert activity.user_id == user_id

@pytest.mark.asyncio
async def test_get_activity_laps(repository, mock_db, sample_laps):
    """Test getting activity laps."""
    # Mock the database response
    mock_result = Mock()
    mock_result.scalars.return_value.all.return_value = sample_laps
    mock_db.execute.return_value = mock_result

    # Get the laps
    laps = await repository.get_activity_laps("test123")

    # Verify the query
    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][0]
    assert str(call_args) == str(
        select(ActivityLap)
        .where(ActivityLap.activity_id == "test123")
        .order_by(ActivityLap.sequence)
    )

    # Verify the results
    assert len(laps) == len(sample_laps)
    for i, lap in enumerate(laps):
        assert lap.activity_id == "test123"
        assert lap.sequence == i

@pytest.mark.asyncio
async def test_get_activity_streams(repository, mock_db, sample_streams):
    """Test getting activity streams."""
    # Mock the database response
    mock_result = Mock()
    mock_result.scalars.return_value.all.return_value = sample_streams
    mock_db.execute.return_value = mock_result

    # Get the streams
    streams = await repository.get_activity_streams("test123")

    # Verify the query
    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][0]
    assert str(call_args) == str(
        select(ActivityStream)
        .where(ActivityStream.activity_id == "test123")
        .order_by(ActivityStream.sequence)
    )

    # Verify the results
    assert len(streams) == len(sample_streams)
    for i, stream in enumerate(streams):
        assert stream.activity_id == "test123"
        assert stream.sequence == i

@pytest.mark.asyncio
async def test_get_activity_streams_with_fields(repository, mock_db, sample_streams):
    """Test getting activity streams with field filtering."""
    # Mock the database response
    mock_result = Mock()
    mock_result.scalars.return_value.all.return_value = sample_streams
    mock_db.execute.return_value = mock_result

    # Fields to request
    fields = ["heart_rate", "power", "cadence"]

    # Get the streams
    streams = await repository.get_activity_streams("test123", fields=fields)

    # Verify the query
    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][0]
    query_str = str(call_args)

    # Check that required fields are included
    assert "activity_id" in query_str
    assert "sequence" in query_str
    assert "time" in query_str

    # Check that requested fields are included
    for field in fields:
        assert field in query_str

    # Verify the results
    assert len(streams) == len(sample_streams)
    for stream in streams:
        assert stream.activity_id == "test123"
        assert stream.heart_rate is not None
        assert stream.power is not None
        assert stream.cadence is not None 