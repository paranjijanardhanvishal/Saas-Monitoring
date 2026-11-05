import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from pymongo.errors import DuplicateKeyError

from app.database.mongodb import get_database
from app.models.event import EventModel
from app.models.file import FileModel
from app.models.user import UserModel

logger = logging.getLogger(__name__)

SENSITIVE_KEY_PARTS = (
    "password", "passwd", "secret", "token", "cookie", "authorization",
    "api_key", "apikey", "credential", "private_key",
)
DENIED_KEY_PARTS = ("content", "body", "text", "clipboard", "keystroke", "screenshot")
MAX_STRING_LENGTH = 512


def sanitize_metadata(value: Any, depth: int = 0) -> Any:
    """Bound and redact untrusted metadata before persistence."""
    if depth > 3:
        return "[truncated]"
    if isinstance(value, dict):
        clean: Dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 50:
                break
            key_str = str(key)[:64]
            lowered = key_str.lower()
            if any(part in lowered for part in DENIED_KEY_PARTS):
                continue
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                clean[key_str] = "[REDACTED]"
            else:
                clean[key_str] = sanitize_metadata(item, depth + 1)
        return clean
    if isinstance(value, list):
        return [sanitize_metadata(item, depth + 1) for item in value[:50]]
    if isinstance(value, str):
        return value[:MAX_STRING_LENGTH]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:MAX_STRING_LENGTH]


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def log_event(event_data: EventModel) -> bool:
    """Persist an event. Returns False when the event_id already exists.

    Endpoint-sourced fields (user/device/source) must be assigned by the caller
    from authenticated context before this function is invoked.
    """
    db = get_database()
    if db is None:
        raise RuntimeError("Database connection not established")

    document = event_data.model_dump()
    document["timestamp"] = ensure_utc(document["timestamp"])
    document["ingestion_timestamp"] = datetime.now(timezone.utc)
    if document.get("metadata") is not None:
        document["metadata"] = sanitize_metadata(document["metadata"])
    if not document.get("correlation_id"):
        document["correlation_id"] = document.get("event_id")

    try:
        await db.events.insert_one(document)
        return True
    except DuplicateKeyError:
        logger.info("Duplicate event delivery ignored: %s", event_data.event_id)
        return False


async def persist_files(files_data: List[Dict[str, Any]]) -> int:
    db = get_database()
    if db is None:
        raise RuntimeError("Database connection not established")
    count = 0
    for item in files_data:
        owner_email = None
        if item.get("owners"):
            owner_email = item["owners"][0].get("emailAddress")
        file_model = FileModel(
            file_id=item["id"],
            name=item["name"],
            mime_type=item["mimeType"],
            owner_email=owner_email,
            created_time=item.get("createdTime"),
            modified_time=item.get("modifiedTime"),
            web_url=item.get("webViewLink"),
        )
        await db.files.update_one(
            {"file_id": file_model.file_id},
            {"$set": file_model.model_dump()},
            upsert=True,
        )
        count += 1
    return count


async def persist_user(user_data: Dict[str, Any]) -> None:
    """Create a directory entry for a Drive user without touching credentials.

    Existing local accounts keep their role, password hash and consent state.
    """
    db = get_database()
    if db is None or not user_data:
        raise RuntimeError("Database connection not established")
    email = user_data.get("emailAddress")
    user_id = user_data.get("permissionId") or email
    if not user_id:
        return
    user_model = UserModel(
        user_id=user_id,
        email=email,
        display_name=user_data.get("displayName"),
        monitoring_enabled="NOT_ASKED",
        source="google_drive",
    )
    await db.users.update_one(
        {"user_id": user_model.user_id},
        {
            "$setOnInsert": {
                "user_id": user_model.user_id,
                "email": str(email).lower() if email else None,
                "display_name": user_model.display_name,
                "role": "USER",
                "monitoring_enabled": "NOT_ASKED",
                "hashed_password": "",
                "source": "google_drive",
                "is_active": True,
                "enforcement_status": "ACTIVE",
                "created_at": user_model.created_at,
            }
        },
        upsert=True,
    )
