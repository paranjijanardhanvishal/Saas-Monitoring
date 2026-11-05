from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import ensure_self_or_admin, get_current_admin_user, get_current_user
from app.database.mongodb import get_database
from app.models.user import BusinessRoleUpdate, UserModel, UserResponse
from app.services.audit import record_audit

router = APIRouter()


@router.get("/users", response_model=List[UserResponse])
async def get_users(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    include_pending: bool = False,
    consent: Optional[str] = Query(None, pattern="^(NOT_ASKED|ALLOWED|DECLINED|REVOKED)$"),
    role: Optional[str] = Query(None, pattern="^(ADMIN|USER)$"),
    business_role: Optional[str] = Query(
        None, pattern="^(GENERAL|DEVELOPER|HR|FINANCE)$"
    ),
    q: Optional[str] = Query(None, max_length=100),
    current_user: UserModel = Depends(get_current_admin_user),
):
    """Monitored user directory. Defaults to consenting (ALLOWED) users only."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    query: dict = {}
    if consent:
        query["monitoring_enabled"] = consent
    elif not include_pending:
        query["monitoring_enabled"] = "ALLOWED"
    if role:
        query["role"] = role
    filters: list[dict] = []
    if business_role == "GENERAL":
        filters.append(
            {
                "$or": [
                    {"business_role": "GENERAL"},
                    {"business_role": {"$exists": False}},
                    {"business_role": None},
                ]
            }
        )
    elif business_role:
        query["business_role"] = business_role
    if q:
        filters.append(
            {
                "$or": [
                    {"user_id": {"$regex": q, "$options": "i"}},
                    {"email": {"$regex": q, "$options": "i"}},
                    {"display_name": {"$regex": q, "$options": "i"}},
                ]
            }
        )
    if filters:
        query["$and"] = filters

    cursor = db.users.find(query).sort("user_id", 1).skip(skip).limit(limit)
    users = await cursor.to_list(length=limit)
    return [UserResponse(**u) for u in users]


@router.patch("/users/{user_id}/business-role", response_model=UserResponse)
async def update_user_business_role(
    user_id: str,
    payload: BusinessRoleUpdate,
    current_user: UserModel = Depends(get_current_admin_user),
):
    """Update a monitored user's business role for role-aware analytics."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one(
        {"user_id": user_id}, {"$set": {"business_role": payload.business_role}}
    )
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "user.business_role_updated",
        "user",
        user_id,
        "success",
        metadata={"previous": user.get("business_role", "GENERAL"), "business_role": payload.business_role},
    )
    updated = await db.users.find_one({"user_id": user_id})
    return UserResponse(**updated)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, current_user: UserModel = Depends(get_current_user)):
    ensure_self_or_admin(current_user, user_id)
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user)


@router.get("/users/{user_id}/summary")
async def get_user_summary(user_id: str, current_user: UserModel = Depends(get_current_user)):
    ensure_self_or_admin(current_user, user_id)
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    devices = await db.devices.find({"user_id": user_id}).sort("enrolled_at", -1).to_list(length=50)
    latest_risk = await db.risk_assessments.find_one(
        {"user_id": user_id}, sort=[("timestamp", -1)]
    )
    open_alerts = await db.alerts.count_documents(
        {"user_id": user_id, "status": {"$nin": ["RESOLVED", "DISMISSED"]}}
    )
    events_today = await db.events.count_documents(
        {"user_id": user_id, "timestamp": {"$gte": day_ago}}
    )
    events_week = await db.events.count_documents(
        {"user_id": user_id, "timestamp": {"$gte": week_ago}}
    )
    latest_event = await db.events.find_one({"user_id": user_id}, sort=[("timestamp", -1)])

    for device in devices:
        device["_id"] = str(device["_id"])
    if latest_risk:
        latest_risk.pop("_id", None)
    summary = UserResponse(**user).model_dump()
    return {
        "user": summary,
        "devices": devices,
        "activity": {
            "events_last_24h": events_today,
            "events_last_7d": events_week,
            "last_event_at": latest_event.get("timestamp") if latest_event else None,
        },
        "risk": {
            "latest": latest_risk,
            "open_alerts": open_alerts,
        },
    }


@router.get("/users/{user_id}/devices")
async def get_user_devices(user_id: str, current_user: UserModel = Depends(get_current_user)):
    ensure_self_or_admin(current_user, user_id)
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    devices = await db.devices.find({"user_id": user_id}).sort("enrolled_at", -1).to_list(length=100)
    for device in devices:
        device["_id"] = str(device["_id"])
        device.pop("token_hash", None)
        device.pop("token_prefix", None)
    return devices
