from sqlalchemy.ext.asyncio import AsyncSession
from fitparse import FitFile

from data_ingestion.models import Activity, ActivityStream

class ActivityRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_activity(self, activity_data: dict, fit_file: bytes) -> Activity:
        activity = Activity(
            fit_file=fit_file,
            **activity_data
        )
        self.db.add(activity)
        await self.db.commit()
        return activity
    
    async def store_laps(self, activity_id: str, laps: list[dict]) -> None:
        # TODO: Implement this method
        await self.db.commit()

    async def store_streams(self, activity_id: str, fit_file: bytes) -> None:
        file = FitFile(fit_file)
        messages = file.messages
        records = [message for message in messages if message.mesg_type == "record"]
        for index, record in enumerate(records):
            stream = ActivityStream(
                time=record.get("timestamp"),
                activity_id=activity_id,
                sequence=index,
                latitude=record.get("position_lat"),
                longitude=record.get("position_long"),
                power=record.get("power"),
                heart_rate=record.get("heart_rate"),
                cadence=record.get("cadence"),
                distance=record.get("distance"),
                altitude=record.get("enhanced_altitude"),
                speed=record.get("speed"),
                temperature=record.get("Stryd Temperature") or record.get("temperature"),
                humidity=record.get("Stryd Humidity"),
                vertical_oscillation=record.get("vertical_oscillation"),
                ground_contact_time=record.get("stance_time"),
                left_right_balance=record.get("stance_time_balance") or record.get("left_right_balance"),
                form_power=record.get("Form Power"),
                leg_spring_stiffness=record.get("Leg Spring Stiffness"),
                air_power=record.get("Air Power"),
                dfa_a1=record.get("Alpha1"),
                artifacts=record.get("Artifacts"),
                respiration_rate=record.get("unknown_108", 0) / 100 if record.get("unknown_108") else None,
                front_gear=record.get("FrontGear"),
                rear_gear=record.get("RearGear"),
            )
            self.db.add(stream)
        await self.db.commit()

# temp code to read fit files - will be removed
if __name__ == "__main__":
    with open("i55928721_Recovery.fit", "rb") as f, open("out.txt", "w") as out:
        fit_file = f.read()
        for message in FitFile(fit_file).messages:
            out.write(str(message.mesg_type) + " " + str(message.get_values()) + "\n")
