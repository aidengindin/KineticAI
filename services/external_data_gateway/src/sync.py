import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
import aiohttp
import backoff
from redis import Redis

from src.config import settings
from src.metrics import ACTIVE_SYNCS, ACTIVITY_PROCESSING_TIME, SYNC_REQUESTS_TOTAL, GEAR_PROCESSING_TIME
from src.models import SyncStatus, SyncStatusResponse
from kinetic_common.models import (
    PydanticActivity as Activity,
    PydanticGear as Gear,
)

logger = logging.getLogger(__name__)


class SyncManager:
    """SyncManager handles synchronization of user activities from Intervals.icu API.
    This class manages the synchronization process of user activities, including fetching
    activities, downloading FIT files, and maintaining sync status in Redis.
    Attributes:
        redis (Redis): Redis client instance for storing sync status
        headers (dict): HTTP headers for API authentication
        _session (aiohttp.ClientSession): Async HTTP session for making API requests
    Example:
        ```python
        async with SyncManager(redis_client) as sync_manager:
            await sync_manager.start_sync(user_id='123', start_date=start, end_date=end)
            status = await sync_manager.get_status(user_id='123')
        ```
    The class implements the async context manager protocol for proper resource cleanup.
    It includes automatic retries for API requests using exponential backoff strategy
    and maintains detailed sync status including progress metrics in Redis.
    The sync process is batched to handle large amounts of activities efficiently
    and includes comprehensive error handling and status tracking.
    Notes:
        - Requires valid Intervals.icu API credentials
        - Uses Redis for storing sync status
        - Implements prometheus metrics for monitoring
        - Handles API rate limiting through backoff decorators
    """

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        credentials = base64.b64encode(
            f"API_KEY:{settings.get_intervals_api_key}".encode()
        ).decode()
        self.headers = {"Authorization": f"Basic {credentials}"}
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        await self.close()

    @property
    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_status_key(self, user_id: str) -> str:
        return f"sync:status:{user_id}"

    async def update_status(
        self,
        user_id: str,
        status: SyncStatus,
        total: Optional[int] = None,
        processed: Optional[int] = None,
        failed: Optional[int] = None,
        error: Optional[str] = None,
    ):
        key = self._get_status_key(user_id)
        current = await self.get_status(user_id)

        updated = SyncStatusResponse(
            status=status,
            total_activities=total if total is not None else current.total_activities,
            processed_activities=(
                processed if processed is not None else current.processed_activities
            ),
            failed_activities=(
                failed if failed is not None else current.failed_activities
            ),
            error_message=error,
            last_updated=datetime.now(timezone.utc),
        )

        self.redis.set(key, updated.model_dump_json())
        return updated

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=settings.MAX_RETRIES,
    )
    async def fetch_activities(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> List[Activity]:
        """
        Fetch activities for a given user within a specified date range.

        Args:
            user_id (str): The ID of the user whose activities are to be fetched.
            start_date (datetime): The start date of the range to fetch activities.
            end_date (datetime): The end date of the range to fetch activities.

        Returns:
            List[Activity]: A list of Activity objects representing the fetched activities.

        Raises:
            HTTPError: If the HTTP request to fetch activities fails.
        """
        url = f"{settings.INTERVALS_API_BASE_URL}/athlete/{user_id}/activities"
        params = {
            "oldest": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "newest": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        with ACTIVITY_PROCESSING_TIME.labels("fetch_activities").time():
            session = await self.session
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                activities = []
                for activity in data:
                    mapped_activity = {
                        "id": activity.get("id"),
                        "start_date": activity.get("start_date_local"),
                        "name": activity.get("name"),
                        "description": activity.get("description", None),
                        "sport_type": activity.get("type"),
                        "duration": activity.get("moving_time"),
                        "distance": activity.get("icu_distance", None),
                        "total_elevation_gain": activity.get(
                            "total_elevation_gain", None
                        ),
                        "average_speed": activity.get("average_speed", None),
                        "average_heartrate": activity.get("average_heartrate", None),
                        "average_cadence": activity.get("average_cadence", None),
                        "average_power": activity.get("icu_average_watts", None),
                        "calories": activity.get("calories", None),
                        "average_lr_balance": activity.get("avg_lr_balance", None),
                        "average_gap": activity.get("gap", None),
                        "perceived_exertion": activity.get("perceived_exertion", None),
                        "polarization_index": activity.get("polarization_index", None),
                        "decoupling": activity.get("decoupling", None),
                        "carbs_ingested": activity.get("carbs_ingested", None),
                        "normalized_power": activity.get(
                            "icu_weighted_average_watts", None
                        ),
                        "training_load": activity.get("icu_training_load", None),
                    }
                    activities.append(Activity(**mapped_activity))
                return activities

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=settings.MAX_RETRIES,
    )
    async def fetch_fit_file(self, activity_id: str) -> bytes:
        url = f"{settings.INTERVALS_API_BASE_URL}/activity/{activity_id}/fit-file"

        with ACTIVITY_PROCESSING_TIME.labels("fetch_fit_file").time():
            session = await self.session
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.read()

    async def process_activity(self, activity: Activity) -> bool:
        try:
            fit_data = await self.fetch_fit_file(activity.id)

            # Send to ingestion service
            with ACTIVITY_PROCESSING_TIME.labels("process_activity").time():
                session = await self.session
                async with session.post(f"{settings.DATA_INGESTION_SERVICE_URL}/activities", json=activity.model_dump(), files={"fit_file": fit_data}) as response:
                    response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error processing activity {activity.id}: {str(e)}")
            return False

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=settings.MAX_RETRIES,
    )
    async def fetch_gear(self, user_id: str) -> List[Gear]:
        url = f"{settings.INTERVALS_API_BASE_URL}/athlete/{user_id}/gear"

        with GEAR_PROCESSING_TIME.labels("fetch_gear").time():
            session = await self.session
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                gear = []
                for gear_item in data:
                    if gear_item.get("retired") == "true" or gear_item.get("component"):
                        continue
                    mapped_gear = {
                        "id": gear_item.get("id"),
                        "athlete_id": gear_item.get("athlete_id"),
                        "name": gear_item.get("name"),
                        "distance": gear_item.get("distance"),
                        "time": gear_item.get("time"),
                    }
                    gear.append(Gear(**mapped_gear))
                return gear

    async def process_gear(self, gear: Gear) -> bool:
        try:
            # Send to ingestion service
            with GEAR_PROCESSING_TIME.labels("process_gear").time():
                session = await self.session
                async with session.post(f"{settings.DATA_INGESTION_SERVICE_URL}/gear", json=gear.model_dump()) as response:
                    response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error processing gear {gear.id}: {str(e)}")
            return False

    async def start_sync(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ):
        """
        Starts the synchronization process for a given user within an optional date range.
        This method performs the following steps:
        1. Increments the active sync counter and logs the sync request as started.
        2. Updates the user's sync status to IN_PROGRESS.
        3. Fetches activities for the user within the specified date range.
        4. Updates the user's sync status with the total number of activities to be processed.
        5. Processes activities in batches, updating the sync status after each batch.
        6. Updates the user's sync status to COMPLETED if all activities are processed successfully,
           or to FAILED if any activity fails.
        7. Logs the sync request as completed or failed based on the final status.
        Args:
            user_id (str): The ID of the user for whom the sync is being performed.
            start_date (datetime): The start date for fetching activities. Defaults to None.
            end_date (datetime): The end date for fetching activities. Defaults to None.
        Raises:
            Exception: If any error occurs during the synchronization process, it is logged and re-raised.
        """
        try:
            ACTIVE_SYNCS.inc()
            SYNC_REQUESTS_TOTAL.labels(user_id=user_id, status="started").inc()

            await self.update_status(user_id, SyncStatus.IN_PROGRESS)

            activities = await self.fetch_activities(user_id, start_date, end_date)
            total_activities = len(activities)

            gear = await self.fetch_gear(user_id)
            total_gear = len(gear)

            await self.update_status(
                user_id,
                SyncStatus.IN_PROGRESS,
                total=total_activities,
                processed=0,
                failed=0,
            )

            processed = 0
            failed = 0

            for batch in [
                activities[i : i + settings.SYNC_BATCH_SIZE]
                for i in range(0, len(activities), settings.SYNC_BATCH_SIZE)
            ]:
                results = await asyncio.gather(
                    *[self.process_activity(activity) for activity in batch],
                    return_exceptions=True,
                )

                batch_processed = sum(1 for r in results if r is True)
                batch_failed = sum(
                    1 for r in results if r is False or isinstance(r, Exception)
                )

                processed += batch_processed
                failed += batch_failed

                await self.update_status(
                    user_id,
                    SyncStatus.IN_PROGRESS,
                    total=total_activities,
                    processed=processed,
                    failed=failed,
                )

            for batch in [
                gear[i : i + settings.SYNC_BATCH_SIZE]
                for i in range(0, len(gear), settings.SYNC_BATCH_SIZE)
            ]:
                results = await asyncio.gather(
                    *[self.process_gear(gear) for gear in batch],
                    return_exceptions=True,
                )

                batch_processed = sum(1 for r in results if r is True)
                batch_failed = sum(
                    1 for r in results if r is False or isinstance(r, Exception)
                )

                processed += batch_processed
                failed += batch_failed

                await self.update_status(
                    user_id,
                    SyncStatus.IN_PROGRESS,
                    total=total_gear,
                    processed=processed,
                    failed=failed,
                )

            final_status = SyncStatus.COMPLETED if failed == 0 else SyncStatus.FAILED
            await self.update_status(
                user_id,
                final_status,
                total=total_activities,
                processed=processed,
                failed=failed,
            )

            SYNC_REQUESTS_TOTAL.labels(user_id=user_id, status="completed").inc()

        except Exception as e:
            logger.error(f"Sync failed for user {user_id}: {str(e)}")
            await self.update_status(user_id, SyncStatus.FAILED, error=str(e))
            SYNC_REQUESTS_TOTAL.labels(user_id=user_id, status="failed").inc()
            raise
        finally:
            ACTIVE_SYNCS.dec()

    async def get_status(self, user_id: str) -> SyncStatusResponse:
        key = self._get_status_key(user_id)
        data = self.redis.get(key)

        if not data:
            return SyncStatusResponse(
                status=SyncStatus.PENDING, last_updated=datetime.now(timezone.utc)
            )

        return SyncStatusResponse(**json.loads(data))
