"""Offline metadata analysis pipeline.

Important limitation: this script analyses *file names* only. It does not
download or inspect document contents, so its output must not be presented as
a content data-loss-prevention scan.
"""

import asyncio
import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(ROOT, "backend"))

from app.database.mongodb import close_mongo_connection, connect_to_mongo, get_database
from app.metadata.vector import local_vdb
from app.privacy.schemas import PrivacyAnalysisRequest
from app.privacy.service import analyze_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_offline_analysis():
    await connect_to_mongo()
    db = get_database()
    if db is None:
        logger.error("Database connection failed; offline analysis aborted.")
        return

    try:
        files = await db.files.find({}).to_list(length=None)
        if not files:
            logger.info("No synced file metadata found. Run scripts/sync_drive.py first.")
            return

        processed = 0
        failed = 0
        for item in files:
            file_id = item["file_id"]
            name = item.get("name", "")
            owner_email = item.get("owner_email")

            # The owner email links metadata to a local account when one exists.
            owner = (
                await db.users.find_one({"email": str(owner_email).lower()})
                if owner_email
                else None
            )
            if not owner:
                logger.warning("Skipping %s: no local account for owner", file_id)
                continue

            local_vdb.insert(file_id, name)

            try:
                finding = await analyze_text(
                    PrivacyAnalysisRequest(text=name, file_id=file_id), owner["user_id"]
                )
                await db.offline_baselines.update_one(
                    {"file_id": file_id},
                    {
                        "$set": {
                            "privacy_score": finding.sensitivity_score,
                            "category": finding.category,
                            "engine": finding.engine,
                            "analyzed_field": "file_name_only",
                            "finding_id": finding.finding_id,
                        }
                    },
                    upsert=True,
                )
                processed += 1
                logger.info(
                    "Metadata baseline for %s: %s (%s)",
                    file_id,
                    finding.category,
                    finding.sensitivity_score,
                )
            except Exception:
                failed += 1
                logger.exception("Offline metadata analysis failed for %s", file_id)

        logger.info("Offline metadata analysis complete: %s processed, %s failed", processed, failed)
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(run_offline_analysis())
