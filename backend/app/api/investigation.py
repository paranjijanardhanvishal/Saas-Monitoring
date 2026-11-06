import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import (
    ensure_self_or_admin,
    get_current_active_user,
    get_current_admin_user,
)
from app.database.mongodb import get_database
from app.models.user import UserModel, UserResponse

router = APIRouter()


def _serialize(document: dict[str, Any]) -> dict[str, Any]:
    if "_id" in document:
        document["_id"] = str(document["_id"])
    return document


def _mask_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    parts = str(email).split("@")
    if len(parts) != 2:
        return "***"
    name, domain = parts
    masked_name = name[0] + "***" if len(name) > 1 else "***"
    return f"{masked_name}@{domain}"


@router.get("/investigation/search")
async def search_users(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserModel = Depends(get_current_active_user),
):
    """Search the user directory by id, email or display name."""
    if current_user.role not in ("ADMIN", "EDITOR", "VISITOR"):
        raise HTTPException(status_code=403, detail="Security console access required")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    safe = re.escape(q)
    cursor = db.users.find(
        {
            "$or": [
                {"user_id": {"$regex": safe, "$options": "i"}},
                {"email": {"$regex": safe, "$options": "i"}},
                {"display_name": {"$regex": safe, "$options": "i"}},
            ]
        }
    ).limit(limit)
    users = await cursor.to_list(length=limit)

    results = []
    for user in users:
        response = UserResponse(**user).model_dump()
        response["active_devices"] = await db.devices.count_documents(
            {"user_id": user["user_id"], "status": "ACTIVE"}
        )
        response["open_alerts"] = await db.alerts.count_documents(
            {
                "user_id": user["user_id"],
                "status": {"$nin": ["RESOLVED", "DISMISSED"]},
            }
        )
        results.append(response)
    return results


@router.get("/investigation/users/{user_id}")
async def investigate_user(
    user_id: str,
    event_limit: int = Query(50, ge=1, le=200),
    current_user: UserModel = Depends(get_current_active_user),
):
    """Correlate a user's devices, events, alerts, incidents and risk history."""
    ensure_self_or_admin(current_user, user_id)
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    events = (
        await db.events.find({"user_id": user_id})
        .sort("timestamp", -1)
        .limit(event_limit)
        .to_list(length=event_limit)
    )
    alerts = (
        await db.alerts.find({"user_id": user_id})
        .sort("timestamp", -1)
        .limit(event_limit)
        .to_list(length=event_limit)
    )
    incidents = (
        await db.incidents.find({"user_id": user_id})
        .sort("created_time", -1)
        .limit(event_limit)
        .to_list(length=event_limit)
    )
    assessments = (
        await db.risk_assessments.find({"user_id": user_id})
        .sort("timestamp", -1)
        .limit(event_limit)
        .to_list(length=event_limit)
    )
    anomalies = (
        await db.anomalies.find({"user_id": user_id})
        .sort("timestamp", -1)
        .limit(event_limit)
        .to_list(length=event_limit)
    )
    findings = (
        await db.pii_findings.find({"user_id": user_id})
        .sort("timestamp", -1)
        .limit(event_limit)
        .to_list(length=event_limit)
    )
    devices = await db.devices.find({"user_id": user_id}).sort("enrolled_at", -1).to_list(length=100)
    for device in devices:
        device.pop("token_hash", None)
        device.pop("token_prefix", None)

    return {
        "generated_at": datetime.now(timezone.utc),
        "user": UserResponse(**user).model_dump(),
        "devices": [_serialize(d) for d in devices],
        "events": [_serialize(e) for e in events],
        "alerts": [_serialize(a) for a in alerts],
        "incidents": [_serialize(i) for i in incidents],
        "risk_assessments": [_serialize(r) for r in assessments],
        "anomalies": [_serialize(a) for a in anomalies],
        "pii_findings": [_serialize(f) for f in findings],
    }


@router.get("/investigation/events/{event_id}/context")
async def investigate_event(
    event_id: str,
    current_user: UserModel = Depends(get_current_active_user),
):
    """Return an event plus correlated risk, alert and anomaly records."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    event = await db.events.find_one({"event_id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    ensure_self_or_admin(current_user, event.get("user_id"))

    correlation_id = event.get("correlation_id") or event_id
    related_events = (
        await db.events.find({"correlation_id": correlation_id})
        .sort("timestamp", 1)
        .limit(100)
        .to_list(length=100)
    )
    alerts = await db.alerts.find({"event_id": event_id}).to_list(length=50)
    assessment = await db.risk_assessments.find_one({"event_id": event_id})
    anomaly = await db.anomalies.find_one({"event_id": event_id})
    finding = await db.pii_findings.find_one({"event_id": event_id})

    return {
        "event": _serialize(event),
        "correlation_id": correlation_id,
        "related_events": [_serialize(e) for e in related_events],
        "alerts": [_serialize(a) for a in alerts],
        "risk_assessment": _serialize(assessment) if assessment else None,
        "anomaly": _serialize(anomaly) if anomaly else None,
        "pii_finding": _serialize(finding) if finding else None,
    }
