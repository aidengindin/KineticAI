import aiohttp
import asyncio
from typing import List, Optional
import json
from datetime import datetime, timezone
from redis import Redis
import logging
from src.config import settings
from src.models import Activity, SyncStatus, SyncStatusResponse
from src.metrics import SYNC_REQUESTS_TOTAL, ACTIVITY_PROCESSING_TIME, ACTIVE_SYNCS
import backoff
import base64

logger = logging.getLogger(__name__)

class SyncManager:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        credentials = base64.b64encode(f"API_KEY:{settings.get_intervals_api_key}".encode()).decode()
        self.headers = {"Authorization": f"Basic {credentials}"}
        self._session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
        error: Optional[str] = None
    ):
        key = self._get_status_key(user_id)
        current = await self.get_status(user_id)
        
        updated = SyncStatusResponse(
            status=status,
            total_activities=total if total is not None else current.total_activities,
            processed_activities=processed if processed is not None else current.processed_activities,
            failed_activities=failed if failed is not None else current.failed_activities,
            error_message=error,
            last_updated=datetime.now(timezone.utc)
        )
        
        self.redis.set(key, updated.model_dump_json())
        return updated

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=settings.MAX_RETRIES
    )
    async def fetch_activities(
        self, 
        user_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Activity]:
        url = f"{settings.INTERVALS_API_BASE_URL}/athlete/{user_id}/activities"
        params = {
            "oldest": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "newest": end_date.strftime("%Y-%m-%dT%H:%M:%S")
        }

        with ACTIVITY_PROCESSING_TIME.labels("fetch_activities").time():
            session = await self.session
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                # return [Activity(**activity) for activity in data]
                activities = []
                for activity in data:
                    mapped_activity = {
                        "id": activity["id"],
                        "start_date": activity["start_date_local"],
                        "name": activity["name"],
                        "sport_type": activity["type"],
                        "duration": activity["icu_recording_time"],
                        "distance": activity.get("icu_distance")
                    }
                    activities.append(Activity(**mapped_activity))
                return activities

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=settings.MAX_RETRIES
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
            
            # Stub: Send to ingestion service
            # In production, implement actual sending logic
            logger.info(f"Would send activity {activity.id} to ingestion service")
            
            return True
        except Exception as e:
            logger.error(f"Error processing activity {activity.id}: {str(e)}")
            return False

    async def start_sync(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
        try:
            ACTIVE_SYNCS.inc()
            SYNC_REQUESTS_TOTAL.labels(user_id=user_id, status="started").inc()
            
            await self.update_status(user_id, SyncStatus.IN_PROGRESS)
            
            activities = await self.fetch_activities(user_id, start_date, end_date)
            total_activities = len(activities)
            
            await self.update_status(
                user_id,
                SyncStatus.IN_PROGRESS,
                total=total_activities,
                processed=0,
                failed=0
            )

            processed = 0
            failed = 0
            
            for batch in [activities[i:i + settings.SYNC_BATCH_SIZE] 
                         for i in range(0, len(activities), settings.SYNC_BATCH_SIZE)]:
                results = await asyncio.gather(
                    *[self.process_activity(activity) for activity in batch],
                    return_exceptions=True
                )
                
                batch_processed = sum(1 for r in results if r is True)
                batch_failed = sum(1 for r in results if r is False or isinstance(r, Exception))
                
                processed += batch_processed
                failed += batch_failed
                
                await self.update_status(
                    user_id,
                    SyncStatus.IN_PROGRESS,
                    total=total_activities,
                    processed=processed,
                    failed=failed
                )

            final_status = SyncStatus.COMPLETED if failed == 0 else SyncStatus.FAILED
            await self.update_status(
                user_id,
                final_status,
                total=total_activities,
                processed=processed,
                failed=failed
            )
            
            SYNC_REQUESTS_TOTAL.labels(user_id=user_id, status="completed").inc()
            
        except Exception as e:
            logger.error(f"Sync failed for user {user_id}: {str(e)}")
            await self.update_status(
                user_id,
                SyncStatus.FAILED,
                error=str(e)
            )
            SYNC_REQUESTS_TOTAL.labels(user_id=user_id, status="failed").inc()
            raise
        finally:
            ACTIVE_SYNCS.dec()

    async def get_status(self, user_id: str) -> SyncStatusResponse:
        key = self._get_status_key(user_id)
        data = self.redis.get(key)
        
        if not data:
            return SyncStatusResponse(
                status=SyncStatus.PENDING,
                last_updated=datetime.now(timezone.utc)
            )
            
        return SyncStatusResponse(**json.loads(data))