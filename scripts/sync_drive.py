import asyncio
import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

from backend.app.services.google_drive import drive_service
from backend.app.services.monitoring import persist_files, persist_user
from backend.app.database.mongodb import connect_to_mongo, close_mongo_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def sync():
    logger.info("Connecting to MongoDB...")
    await connect_to_mongo()
    
    logger.info("Authenticating with Google Drive...")
    if not drive_service.authenticate():
        logger.error("Authentication failed.")
        await close_mongo_connection()
        return

    logger.info("Fetching current user info...")
    user_info = drive_service.get_current_user()
    if user_info:
        logger.info(f"User: {user_info.get('emailAddress')}")
        await persist_user(user_info)
        
    logger.info("Fetching files...")
    files = drive_service.list_files()
    if files:
        logger.info(f"Found {len(files)} files. Persisting...")
        await persist_files(files)
        logger.info("Sync complete.")
    else:
        logger.info("No files found or error occurred.")
        
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(sync())
