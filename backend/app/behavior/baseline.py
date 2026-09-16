from typing import Optional
from app.behavior.schemas import BehaviorProfileModel
from app.database.mongodb import get_database

async def get_user_profile(user_id: str) -> Optional[BehaviorProfileModel]:
    db = get_database()
    if db is None:
        return None
        
    data = await db.behavior_profiles.find_one({"user_id": user_id})
    if data:
        return BehaviorProfileModel(**data)
    return None

async def save_user_profile(profile: BehaviorProfileModel):
    db = get_database()
    if db is not None:
        await db.behavior_profiles.update_one(
            {"user_id": profile.user_id},
            {"$set": profile.model_dump()},
            upsert=True
        )

async def save_anomaly_finding(finding):
    db = get_database()
    if db is not None:
        await db.anomalies.insert_one(finding.model_dump())
