import logging
from datetime import datetime, timezone
from typing import Any, Optional

import bcrypt
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.core.config import settings

logger = logging.getLogger(__name__)


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    db: Any = None


db_client = MongoDB()


def _tls_options() -> dict:
    uri = settings.MONGODB_URI
    if "localhost" in uri or "127.0.0.1" in uri:
        return {}
    # TLS is always validated. Invalid-certificate bypass is never enabled.
    return {"tlsCAFile": certifi.where()}


async def connect_to_mongo() -> None:
    db_client.client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        # Return UTC-aware datetimes so API responses contain an explicit
        # timezone instead of ambiguous naive timestamps.
        tz_aware=True,
        **_tls_options(),
    )
    db_client.db = db_client.client[settings.MONGO_DB_NAME]
    try:
        await db_client.client.admin.command("ping")
        logger.info("Connected to MongoDB database '%s'", settings.MONGO_DB_NAME)
    except Exception:
        logger.exception("MongoDB connection check failed; API will report degraded health")
    await ensure_indexes()
    await ensure_initial_admin()


async def close_mongo_connection() -> None:
    if db_client.client:
        db_client.client.close()
        db_client.client = None
        db_client.db = None


def get_database():
    return db_client.db


def is_test_database() -> bool:
    return settings.MONGO_DB_NAME.lower().endswith("_test")


INDEX_DEFINITIONS: dict[str, list[IndexModel]] = {
    "users": [
        IndexModel([("user_id", ASCENDING)], unique=True),
        IndexModel([("email", ASCENDING)], unique=True, sparse=True),
        IndexModel([("monitoring_enabled", ASCENDING)]),
    ],
    "devices": [
        IndexModel([("device_id", ASCENDING)], unique=True),
        IndexModel([("token_hash", ASCENDING)], unique=True),
        IndexModel([("user_id", ASCENDING)]),
        IndexModel([("status", ASCENDING), ("last_heartbeat", DESCENDING)]),
    ],
    "enrollment_tokens": [
        IndexModel([("token_hash", ASCENDING)], unique=True),
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0),
        IndexModel([("used_at", ASCENDING)]),
    ],
    "events": [
        IndexModel([("event_id", ASCENDING)], unique=True),
        IndexModel([("timestamp", DESCENDING)]),
        IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("device_id", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("source", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("event_type", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("correlation_id", ASCENDING)]),
    ],
    "alerts": [
        IndexModel([("timestamp", DESCENDING)]),
        IndexModel([("status", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("dedupe_key", ASCENDING)], unique=True, sparse=True),
    ],
    "incidents": [
        IndexModel([("created_time", DESCENDING)]),
        IndexModel([("status", ASCENDING), ("created_time", DESCENDING)]),
        IndexModel([("user_id", ASCENDING), ("created_time", DESCENDING)]),
    ],
    "pii_findings": [
        IndexModel([("finding_id", ASCENDING)], unique=True),
        IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("event_id", ASCENDING)]),
    ],
    "anomalies": [
        IndexModel([("anomaly_id", ASCENDING)], unique=True),
        IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("event_id", ASCENDING)]),
    ],
    "behavior_profiles": [
        IndexModel([("user_id", ASCENDING)], unique=True),
        IndexModel([("updated_at", DESCENDING)]),
    ],
    "risk_assessments": [
        IndexModel([("risk_id", ASCENDING)], unique=True),
        IndexModel([("event_id", ASCENDING)]),
        IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("risk_category", ASCENDING), ("timestamp", DESCENDING)]),
    ],
    "enforcement_responses": [
        IndexModel([("response_id", ASCENDING)], unique=True),
        IndexModel([("risk_id", ASCENDING)]),
        IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)]),
    ],
    "audit_logs": [
        IndexModel([("timestamp", DESCENDING)]),
        IndexModel([("actor_id", ASCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("target_id", ASCENDING), ("timestamp", DESCENDING)]),
    ],
    "consent_history": [
        IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)]),
    ],
    "demo_runs": [
        IndexModel([("created_at", DESCENDING)]),
        IndexModel([("run_id", ASCENDING)], unique=True),
    ],
}


async def ensure_indexes() -> None:
    """Create query indexes idempotently.

    A duplicate value in an existing collection must not prevent the API from
    starting; the conflict is logged and the remaining indexes are created.
    """
    if db_client.db is None:
        return
    for collection, indexes in INDEX_DEFINITIONS.items():
        try:
            await db_client.db[collection].create_indexes(indexes)
        except (DuplicateKeyError, OperationFailure) as exc:
            logger.warning("Could not create all indexes for %s: %s", collection, exc)
        except Exception:
            logger.exception("Unexpected failure creating indexes for %s", collection)
    logger.info("MongoDB index initialisation complete")


async def ensure_initial_admin() -> None:
    """Safely provision or synchronize initial administrator account on startup."""
    if db_client.db is None or is_test_database():
        return

    admin_email = (getattr(settings, "ADMIN_EMAIL", "admin@admin.com") or "admin@admin.com").strip().lower()
    admin_user_id = getattr(settings, "ADMIN_USER_ID", "admin") or "admin"
    admin_password = getattr(settings, "ADMIN_PASSWORD", "admin123") or "admin123"

    try:
        existing_admin = await db_client.db.users.find_one({
            "$or": [
                {"email": admin_email},
                {"user_id": admin_user_id},
                {"role": "ADMIN"},
            ]
        })

        hashed = bcrypt.hashpw(
            admin_password.encode("utf-8")[:72],
            bcrypt.gensalt(rounds=12)
        ).decode("ascii")

        if not existing_admin:
            now = datetime.now(timezone.utc)
            admin_doc = {
                "user_id": admin_user_id,
                "email": admin_email,
                "display_name": "Administrator",
                "role": "ADMIN",
                "business_role": "GENERAL",
                "monitoring_enabled": "NOT_ASKED",
                "hashed_password": hashed,
                "source": "local",
                "is_active": True,
                "enforcement_status": "ACTIVE",
                "must_change_password": True,
                "created_at": now,
                "consent_updated_at": None,
                "last_login_at": None,
            }
            await db_client.db.users.insert_one(admin_doc)
            logger.info("Auto-provisioned initial administrator '%s'", admin_email)
        elif getattr(settings, "AUTO_SYNC_ADMIN_CREDENTIALS", False):
            updates = {
                "email": admin_email,
                "role": "ADMIN",
                "is_active": True,
                "hashed_password": hashed,
                "must_change_password": True,
            }
            await db_client.db.users.update_one(
                {"_id": existing_admin["_id"]},
                {"$set": updates}
            )
            logger.info("Synchronized administrator credentials for '%s'", admin_email)
    except Exception as exc:
        logger.warning("Could not auto-provision initial administrator: %s", exc)


async def ping_database() -> bool:
    if db_client.client is None:
        return False
    try:
        await db_client.client.admin.command("ping")
        return True
    except Exception:
        logger.warning("MongoDB ping failed")
        return False


async def drop_test_database() -> None:
    """Only callable against databases ending in '_test'."""
    if not is_test_database():
        raise RuntimeError("Refusing to drop a non-test database")
    if db_client.client is not None:
        await db_client.client.drop_database(settings.MONGO_DB_NAME)
