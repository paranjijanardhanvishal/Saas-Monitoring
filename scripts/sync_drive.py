"""One-shot Google Drive metadata sync.

Only file metadata is retrieved (drive.metadata.readonly scope). File content
is never downloaded or stored. Run from the repository root:

    python scripts/sync_drive.py
"""

import asyncio
import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(ROOT, "backend"))

from app.database.mongodb import close_mongo_connection, connect_to_mongo
from app.services.google_drive import drive_service
from app.services.monitoring import persist_files, persist_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def sync():
    await connect_to_mongo()
    try:
        if not drive_service.authenticate():
            logger.error("Google Drive authentication failed; sync aborted.")
            return

        user_info = drive_service.get_current_user()
        if user_info:
            logger.info("Syncing metadata for Drive account %s", user_info.get("emailAddress"))
            await persist_user(user_info)
        else:
            logger.warning("Could not read the authenticated Drive account profile.")

        files = drive_service.list_files()
        if files:
            persisted = await persist_files(files)
            logger.info("Persisted metadata for %s file(s).", persisted)
        else:
            logger.info("No Drive file metadata returned.")
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(sync())
