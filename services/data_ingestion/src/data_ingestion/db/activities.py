from sqlalchemy.ext.asyncio import AsyncSession
from fitparse import FitFile
import logging
import re

from data_ingestion.models import Activity as PydanticActivity
from data_ingestion.models import ActivityLap as PydanticActivityLap
from data_ingestion.models import ActivityStream as PydanticActivityStream
from data_ingestion.db.models import Activity, ActivityLap, ActivityStream

logger = logging.getLogger(__name__)

def parse_lr_balance(balance_str: str | None) -> float | None:
    """Parse a left/right balance string like '50.1% L / 49.9% R' into a float."""
    if not balance_str:
        return None
    
    try:
        # Try to extract the left percentage using regex
        match = re.search(r'(\d+\.?\d*)%\s*L', balance_str)
        if match:
            return float(match.group(1))
        return None
    except (ValueError, TypeError, AttributeError):
        logger.debug(f"Failed to parse balance string: {balance_str}")
        return None

class ActivityRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_activity(self, activity_data: PydanticActivity, fit_file: bytes) -> None:
        """Create a new activity in the database.
        
        Args:
            activity_data: Activity object containing activity metadata
            fit_file: Raw bytes of the FIT file
        """
        # Convert Pydantic model to dict and update fit_file
        # TODO: remove the exclude once we have a Gear model
        activity_dict = activity_data.model_dump(exclude={'gear'})
        activity_dict['fit_file'] = fit_file
        
        # Create SQLAlchemy model instance
        activity = Activity(**activity_dict)
        await self.db.add(activity)
        await self.db.commit()
    
    async def store_laps(self, activity_id: str, fit_file: FitFile) -> None:
        logger.debug(f"Starting to store laps for activity {activity_id}")
        messages = list(fit_file.get_messages())
        # Debug: print all message types
        message_types = set(message.mesg_type for message in messages)
        logger.debug(f"Available message types in FIT file: {message_types}")
        
        # Get all messages with mesg_num 19 (lap)
        laps = [message for message in messages if message.mesg_num == 19]
        logger.debug(f"Found {len(laps)} laps in activity {activity_id}")
        
        # Debug: print first lap fields if any
        if laps:
            logger.debug(f"First lap fields: {[field.name for field in laps[0].fields]}")
            if "GCTBalance" in [field.name for field in laps[0].fields]:
                logger.debug(f"First lap GCTBalance value: {laps[0].get_value('GCTBalance')}")
        
        for index, lap in enumerate(laps):
            # Create Pydantic model first for validation
            try:
                gct_balance = lap.get_value("GCTBalance")
                logger.debug(f"Lap {index} GCTBalance raw value: {gct_balance}")
                balance = parse_lr_balance(gct_balance)
                logger.debug(f"Lap {index} parsed balance: {balance}")
                if balance is None:
                    balance = lap.get_value("left_right_balance")
                
                lap_data = PydanticActivityLap(
                    activity_id=activity_id,
                    sequence=index,
                    start_date=lap.get_value("start_time"),
                    duration=lap.get_value("total_elapsed_time"),
                    distance=lap.get_value("total_distance"),
                    average_speed=lap.get_value("avg_speed"),
                    average_heartrate=lap.get_value("avg_heart_rate"),
                    average_cadence=lap.get_value("avg_cadence"),
                    average_power=lap.get_value("avg_power"),
                    average_lr_balance=balance,
                    intensity=lap.get_value("intensity"),
                )
                # Convert to SQLAlchemy model
                db_lap = ActivityLap(**lap_data.model_dump())
                await self.db.add(db_lap)
                logger.debug(f"Added lap {index} for activity {activity_id}")
            except Exception as e:
                logger.error(f"Error processing lap {index} for activity {activity_id}: {str(e)}")
                raise
        await self.db.commit()
        logger.debug(f"Committed {len(laps)} laps for activity {activity_id}")

    async def store_streams(self, activity_id: str, fit_file: FitFile) -> None:
        logger.debug(f"Starting to store streams for activity {activity_id}")
        messages = list(fit_file.get_messages())
        # Debug: print all message types
        message_types = set(message.mesg_type for message in messages)
        logger.debug(f"Available message types in FIT file: {message_types}")
        
        # Get all messages with mesg_num 20 (record)
        records = [message for message in messages if message.mesg_num == 20]
        logger.debug(f"Found {len(records)} records in activity {activity_id}")
        
        # Debug: print first record fields if any
        if records:
            logger.debug(f"First record fields: {[field.name for field in records[0].fields]}")
        
        streams_to_add = []
        for index, record in enumerate(records):
            # Create Pydantic model first for validation
            try:
                stream = PydanticActivityStream(
                    time=record.get_value("timestamp"),
                    activity_id=activity_id,
                    sequence=index,
                    latitude=record.get_value("position_lat"),
                    longitude=record.get_value("position_long"),
                    power=record.get_value("power"),
                    heart_rate=record.get_value("heart_rate"),
                    cadence=record.get_value("cadence"),
                    distance=record.get_value("distance"),
                    altitude=record.get_value("enhanced_altitude"),
                    speed=record.get_value("speed"),
                    temperature=record.get_value("Stryd Temperature") or record.get_value("temperature"),
                    humidity=record.get_value("Stryd Humidity"),
                    vertical_oscillation=record.get_value("vertical_oscillation"),
                    ground_contact_time=record.get_value("stance_time"),
                    left_right_balance=record.get_value("stance_time_balance") or record.get_value("left_right_balance"),
                    form_power=record.get_value("Form Power"),
                    leg_spring_stiffness=record.get_value("Leg Spring Stiffness"),
                    air_power=record.get_value("Air Power"),
                    dfa_a1=record.get_value("Alpha1"),
                    artifacts=record.get_value("Artifacts"),
                    respiration_rate=record.get_value("unknown_108", 0) / 100 if record.get_value("unknown_108") else None,
                    front_gear=record.get_value("FrontGear"),
                    rear_gear=record.get_value("RearGear"),
                )
                # Convert to SQLAlchemy model and add to list
                db_stream = ActivityStream(**stream.model_dump())
                streams_to_add.append(db_stream)
                if index % 100 == 0:  # Log every 100 records
                    logger.debug(f"Added {index} records for activity {activity_id}")
            except Exception as e:
                logger.error(f"Error processing record {index} for activity {activity_id}: {str(e)}")
                raise
        
        # Bulk insert all streams without returning IDs
        await self.db.run_sync(lambda session: session.bulk_save_objects(streams_to_add))
        await self.db.commit()
        logger.debug(f"Committed {len(records)} records for activity {activity_id}")
