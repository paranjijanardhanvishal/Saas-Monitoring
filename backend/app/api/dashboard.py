import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.dependencies import get_current_active_user
from app.database.mongodb import get_database
from app.models.user import UserModel

router = APIRouter()


def _serialize(document: dict[str, Any]) -> dict[str, Any]:
    if "_id" in document:
        document["_id"] = str(document["_id"])
    return document


async def _group_counts(collection: Any, match: dict, field: str) -> list[dict]:
    """Aggregate category counts, with a lightweight fallback for test adapters."""
    if hasattr(collection, "aggregate"):
        return await collection.aggregate([
            {"$match": match},
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        ]).to_list(length=10)
    documents = await collection.find(match).to_list(length=10000)
    counts: dict[str, int] = {}
    for document in documents:
        value = document.get(field)
        if value:
            counts[value] = counts.get(value, 0) + 1
    return [{"_id": key, "count": value} for key, value in counts.items()]


async def _hourly_counts(collection: Any, match: dict) -> list[dict]:
    if hasattr(collection, "aggregate"):
        return await collection.aggregate([
            {"$match": match},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%dT%H:00:00Z", "date": "$timestamp"}}, "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]).to_list(length=48)
    documents = await collection.find(match).to_list(length=10000)
    counts: dict[str, int] = {}
    for document in documents:
        timestamp = document.get("timestamp")
        if isinstance(timestamp, datetime):
            key = timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")
            counts[key] = counts.get(key, 0) + 1
    return [{"_id": key, "count": value} for key, value in sorted(counts.items())]


async def _dashboard_overview(current_user: UserModel, personal: bool = False):
    """Role-scoped dashboard aggregates computed from live collections."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    is_admin = current_user.role == "ADMIN" and not personal
    scope: dict = {} if is_admin else {"user_id": current_user.user_id}

    def scoped(**extra: Any) -> dict:
        query = dict(scope)
        query.update(extra)
        return query

    device_query: dict = {} if is_admin else {"user_id": current_user.user_id}
    stale_cutoff = now - timedelta(seconds=settings.AGENT_HEARTBEAT_STALE_SECONDS)

    (
        events_24h,
        events_7d,
        last_event,
        open_alerts,
        alerts_24h,
        severity_rows,
        open_incidents,
        critical_incidents,
        risk_rows,
        latest_risk,
        active_devices,
        revoked_devices,
        stale_devices,
        hourly_rows,
        recent_events,
        recent_alerts,
    ) = await asyncio.gather(
        db.events.count_documents(scoped(timestamp={"$gte": day_ago})),
        db.events.count_documents(scoped(timestamp={"$gte": week_ago})),
        db.events.find_one(scoped(), sort=[("timestamp", -1)]),
        db.alerts.count_documents(scoped(status={"$nin": ["RESOLVED", "DISMISSED"]})),
        db.alerts.count_documents(scoped(timestamp={"$gte": day_ago})),
        _group_counts(db.alerts, scoped(status={"$nin": ["RESOLVED", "DISMISSED"]}), "severity"),
        db.incidents.count_documents(scoped(status={"$nin": ["RESOLVED", "DISMISSED"]})),
        db.incidents.count_documents(scoped(status={"$nin": ["RESOLVED", "DISMISSED"]}, severity="CRITICAL")),
        _group_counts(db.risk_assessments, scope, "risk_category"),
        db.risk_assessments.find_one(scope, sort=[("timestamp", -1)]),
        db.devices.count_documents({**device_query, "status": "ACTIVE"}),
        db.devices.count_documents({**device_query, "status": "REVOKED"}),
        db.devices.count_documents({
            **device_query,
            "status": "ACTIVE",
            "$or": [
                {"last_heartbeat": None},
                {"last_heartbeat": {"$lt": stale_cutoff}},
            ],
        }),
        _hourly_counts(db.events, scoped(timestamp={"$gte": day_ago})),
        db.events.find(scoped()).sort("timestamp", -1).limit(8).to_list(length=8),
        db.alerts.find(scoped()).sort("timestamp", -1).limit(8).to_list(length=8),
    )

    by_severity = {row["_id"]: row["count"] for row in severity_rows}
    for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        by_severity.setdefault(level, 0)

    risk_by_category = {row["_id"]: row["count"] for row in risk_rows}
    for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        risk_by_category.setdefault(level, 0)

    # Build continuous 24-hour timeline ending at the current hour (UTC)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    bucket_datetimes = [current_hour - timedelta(hours=23 - i) for i in range(24)]
    counts_by_hour = {row["_id"]: row["count"] for row in hourly_rows}
    by_hour = [
        {
            "hour": b.strftime("%Y-%m-%dT%H:00:00Z"),
            "count": counts_by_hour.get(b.strftime("%Y-%m-%dT%H:00:00Z"), 0),
        }
        for b in bucket_datetimes
    ]

    response: dict[str, Any] = {
        "generated_at": now,
        "scope": "ADMIN" if is_admin else "USER",
        "events": {
            "last_24h": events_24h,
            "last_7d": events_7d,
            "last_event_at": last_event.get("timestamp") if last_event else None,
            "by_hour": by_hour,
        },
        "alerts": {
            "open": open_alerts,
            "last_24h": alerts_24h,
            "by_severity": by_severity,
            "recent": [_serialize(a) for a in recent_alerts],
        },
        "incidents": {"open": open_incidents, "critical_open": critical_incidents},
        "risk": {
            "by_category": risk_by_category,
            "latest": _serialize(latest_risk) if latest_risk else None,
        },
        "devices": {
            "active": active_devices,
            "revoked": revoked_devices,
            "stale": stale_devices,
        },
        "recent_events": [_serialize(e) for e in recent_events],
    }

    if is_admin:
        (
            users_total,
            users_consented,
            users_pending,
            users_declined,
        ) = await asyncio.gather(
            db.users.count_documents({}),
            db.users.count_documents({"monitoring_enabled": "ALLOWED"}),
            db.users.count_documents({"monitoring_enabled": {"$in": ["NOT_ASKED"]}, "role": "USER"}),
            db.users.count_documents({"monitoring_enabled": {"$in": ["DECLINED", "REVOKED"]}}),
        )
        response["users"] = {
            "total": users_total,
            "consented": users_consented,
            "pending_consent": users_pending,
            "declined_or_revoked": users_declined,
        }
    else:
        response["account"] = {
            "user_id": current_user.user_id,
            "monitoring_enabled": current_user.monitoring_enabled,
            "enforcement_status": current_user.enforcement_status,
        }

    return response


@router.get("/dashboard/overview")
async def dashboard_overview(current_user: UserModel = Depends(get_current_active_user)):
    """Organization overview for administrators; personal overview for other roles."""
    return await _dashboard_overview(current_user)


@router.get("/dashboard/me")
async def my_dashboard(current_user: UserModel = Depends(get_current_active_user)):
    """Personal dashboard, including for administrators, never organization aggregates."""
    return await _dashboard_overview(current_user, personal=True)
