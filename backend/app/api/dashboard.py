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


@router.get("/dashboard/overview")
async def dashboard_overview(current_user: UserModel = Depends(get_current_active_user)):
    """Role-scoped dashboard aggregates computed from live collections."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    is_admin = current_user.role == "ADMIN"
    scope: dict = {} if is_admin else {"user_id": current_user.user_id}

    def scoped(**extra: Any) -> dict:
        query = dict(scope)
        query.update(extra)
        return query

    events_24h = await db.events.count_documents(scoped(timestamp={"$gte": day_ago}))
    events_7d = await db.events.count_documents(scoped(timestamp={"$gte": week_ago}))
    last_event = await db.events.find_one(scoped(), sort=[("timestamp", -1)])

    open_alerts = await db.alerts.count_documents(
        scoped(status={"$nin": ["RESOLVED", "DISMISSED"]})
    )
    alerts_24h = await db.alerts.count_documents(scoped(timestamp={"$gte": day_ago}))
    severity_rows = await db.alerts.aggregate(
        [
            {"$match": scoped(status={"$nin": ["RESOLVED", "DISMISSED"]})},
            {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
        ]
    ).to_list(length=10)
    by_severity = {row["_id"]: row["count"] for row in severity_rows}
    for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        by_severity.setdefault(level, 0)

    open_incidents = await db.incidents.count_documents(
        scoped(status={"$nin": ["RESOLVED", "DISMISSED"]})
    )
    critical_incidents = await db.incidents.count_documents(
        scoped(status={"$nin": ["RESOLVED", "DISMISSED"]}, severity="CRITICAL")
    )

    risk_rows = await db.risk_assessments.aggregate(
        [{"$match": scope}, {"$group": {"_id": "$risk_category", "count": {"$sum": 1}}}]
    ).to_list(length=10)
    risk_by_category = {row["_id"]: row["count"] for row in risk_rows}
    for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        risk_by_category.setdefault(level, 0)
    latest_risk = await db.risk_assessments.find_one(scope, sort=[("timestamp", -1)])

    device_query: dict = {} if is_admin else {"user_id": current_user.user_id}
    active_devices = await db.devices.count_documents({**device_query, "status": "ACTIVE"})
    revoked_devices = await db.devices.count_documents({**device_query, "status": "REVOKED"})
    stale_cutoff = now - timedelta(seconds=settings.AGENT_HEARTBEAT_STALE_SECONDS)
    stale_devices = await db.devices.count_documents(
        {
            **device_query,
            "status": "ACTIVE",
            "$or": [
                {"last_heartbeat": None},
                {"last_heartbeat": {"$lt": stale_cutoff}},
            ],
        }
    )

    hourly_rows = await db.events.aggregate(
        [
            {"$match": scoped(timestamp={"$gte": day_ago})},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%dT%H:00", "date": "$timestamp"}
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
    ).to_list(length=48)

    recent_events = await db.events.find(scoped()).sort("timestamp", -1).limit(8).to_list(length=8)
    recent_alerts = await db.alerts.find(scoped()).sort("timestamp", -1).limit(8).to_list(length=8)

    response: dict[str, Any] = {
        "generated_at": now,
        "scope": "ADMIN" if is_admin else "USER",
        "events": {
            "last_24h": events_24h,
            "last_7d": events_7d,
            "last_event_at": last_event.get("timestamp") if last_event else None,
            "by_hour": [{"hour": row["_id"], "count": row["count"]} for row in hourly_rows],
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
        response["users"] = {
            "total": await db.users.count_documents({}),
            "consented": await db.users.count_documents({"monitoring_enabled": "ALLOWED"}),
            "pending_consent": await db.users.count_documents(
                {"monitoring_enabled": {"$in": ["NOT_ASKED"]}, "role": "USER"}
            ),
            "declined_or_revoked": await db.users.count_documents(
                {"monitoring_enabled": {"$in": ["DECLINED", "REVOKED"]}}
            ),
        }
    else:
        response["account"] = {
            "user_id": current_user.user_id,
            "monitoring_enabled": current_user.monitoring_enabled,
            "enforcement_status": current_user.enforcement_status,
        }

    return response
