import os
import platform
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.dependencies import get_current_admin_user
from app.database.mongodb import get_database
from app.models.user import UserModel
from app.privacy.ocr import get_ocr_status
from app.privacy.presidio_analyzer import active_engine_name

router = APIRouter()

START_TIME = datetime.now(timezone.utc)
APP_VERSION = "2.0.0"


@router.get("/system/health")
async def system_health(current_user: UserModel = Depends(get_current_admin_user)):
    """Operational health detail for SOC administrators.

    Values are measured from the live database; unavailable collections are
    reported as null rather than silently replaced with synthetic numbers.
    """
    db = get_database()

    async def count(collection: str, query: Optional[dict] = None) -> Optional[int]:
        if db is None:
            return None
        try:
            return await db[collection].count_documents(query or {})
        except Exception:
            return None

    database_ok = False
    if db is not None:
        try:
            await db.command("ping")
            database_ok = True
        except Exception:
            database_ok = False

    now = datetime.now(timezone.utc)
    stale_cutoff = now.timestamp() - settings.AGENT_HEARTBEAT_STALE_SECONDS
    active_devices = await count("devices", {"status": "ACTIVE"})
    stale_devices = 0
    if db is not None and active_devices:
        try:
            stale_devices = await db.devices.count_documents(
                {
                    "status": "ACTIVE",
                    "last_heartbeat": {"$lt": datetime.fromtimestamp(stale_cutoff, tz=timezone.utc)},
                }
            )
        except Exception:
            stale_devices = 0

    return {
        "version": APP_VERSION,
        "server_time": now,
        "uptime_seconds": int((now - START_TIME).total_seconds()),
        "environment": settings.APP_ENV,
        "database": {
            "connected": database_ok,
            "name": settings.MONGO_DB_NAME,
            "collections": {
                "users": await count("users"),
                "devices": await count("devices"),
                "events": await count("events"),
                "alerts": await count("alerts"),
                "incidents": await count("incidents"),
                "pii_findings": await count("pii_findings"),
                "anomalies": await count("anomalies"),
                "risk_assessments": await count("risk_assessments"),
                "enforcement_responses": await count("enforcement_responses"),
                "audit_logs": await count("audit_logs"),
            },
        },
        "devices": {
            "active": active_devices,
            "revoked": await count("devices", {"status": "REVOKED"}),
            "stale": stale_devices,
            "stale_after_seconds": settings.AGENT_HEARTBEAT_STALE_SECONDS,
        },
        "privacy_engine": {
            "configured": settings.PII_ENGINE,
            "active": active_engine_name(),
        },
        "ocr_engine": get_ocr_status(),
        "risk_engine": {"auto_enabled": settings.AUTO_RISK_ENABLED},
        "retention": {
            "events_days": settings.EVENT_RETENTION_DAYS,
            "audit_days": settings.AUDIT_RETENTION_DAYS,
        },
        "integrations": {
            "slack_configured": bool(os.getenv("SLACK_WEBHOOK_URL")),
            "jira_configured": bool(os.getenv("JIRA_API_URL") and os.getenv("JIRA_AUTH_TOKEN")),
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }


@router.get("/system/audit-logs")
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    actor_id: Optional[str] = Query(default=None, max_length=64),
    action: Optional[str] = Query(default=None, max_length=64),
    target_type: Optional[str] = Query(default=None, max_length=64),
    current_user: UserModel = Depends(get_current_admin_user),
):
    """Append-only audit trail. Tokens and payload contents are never stored."""
    db = get_database()
    query: dict = {}
    if actor_id:
        query["actor_id"] = actor_id
    if action:
        query["action"] = action
    if target_type:
        query["target_type"] = target_type

    cursor = db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    logs = await cursor.to_list(length=limit)
    for entry in logs:
        entry["_id"] = str(entry["_id"])
    return logs


@router.get("/system/consent-history")
async def get_consent_history(
    limit: int = Query(100, ge=1, le=500),
    user_id: Optional[str] = Query(default=None, max_length=64),
    current_user: UserModel = Depends(get_current_admin_user),
):
    db = get_database()
    query: dict = {}
    if user_id:
        query["user_id"] = user_id
    cursor = db.consent_history.find(query).sort("timestamp", -1).limit(limit)
    history = await cursor.to_list(length=limit)
    for entry in history:
        entry["_id"] = str(entry["_id"])
    return history
