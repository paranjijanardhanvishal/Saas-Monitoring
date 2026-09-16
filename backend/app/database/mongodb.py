from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

class MongoDB:
    client: AsyncIOMotorClient | None = None
    db = None

db_client = MongoDB()

async def connect_to_mongo():
    import certifi
    db_client.client = AsyncIOMotorClient(
        settings.MONGODB_URI, 
        tlsCAFile=certifi.where(),
        tlsAllowInvalidCertificates=True
    )
    db_client.db = db_client.client[settings.MONGO_DB_NAME]

async def close_mongo_connection():
    if db_client.client:
        db_client.client.close()

def get_database():
    return db_client.db
