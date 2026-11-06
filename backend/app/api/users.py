from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.dependencies import ensure_self_or_admin, get_current_admin_user, get_current_user
from app.core.security import get_password_hash
from app.database.mongodb import get_database
from app.models.user import BusinessRoleUpdate, UserCreate, UserModel, UserResponse, UserUpdate
from app.services.audit import record_audit

router = APIRouter()


def _mask_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    parts = str(email).split("@")
    if len(parts) != 2:
        return "***"
    name, domain = parts
    masked_name = name[0] + "***" if len(name) > 1 else "***"
    return f"{masked_name}@{domain}"


@router.get("/users", response_model=List[UserResponse])
async def get_users(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    include_pending: bool = False,
    consent: Optional[str] = Query(None, pattern="^(NOT_ASKED|ALLOWED|DECLINED|REVOKED)$"),
    role: Optional[str] = Query(None, pattern="^(ADMIN|EDITOR|VISITOR|USER)$"),
    business_role: Optional[str] = Query(
        None, pattern="^(GENERAL|DEVELOPER|HR|FINANCE)$"
    ),
    q: Optional[str] = Query(None, max_length=100),
    current_user: UserModel = Depends(get_current_user),
):
    """Monitored user directory. Defaults to consenting (ALLOWED) users only."""
    if current_user.role not in ("ADMIN", "EDITOR", "VISITOR"):
        raise HTTPException(status_code=403, detail="Security console directory access required")

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
    responses = []
    for u in users:
        resp = UserResponse(**u)
        if current_user.role == "VISITOR":
            resp.email = _mask_email(resp.email)
        responses.append(resp)
    return responses


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user_record(
    payload: UserCreate,
    request: Request,
    current_user: UserModel = Depends(get_current_admin_user),
):
    """Create a user record directly from the User Directory (ADMIN only)."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    email = str(payload.email).lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already registered")
    if await db.users.find_one({"user_id": payload.user_id}):
        raise HTTPException(status_code=409, detail="User ID already registered")

    try:
        hashed = get_password_hash(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user_model = UserModel(
        user_id=payload.user_id,
        email=email,
        display_name=payload.display_name or payload.user_id,
        role=payload.role,
        business_role=payload.business_role,
        hashed_password=hashed,
        monitoring_enabled="NOT_ASKED",
    )
    await db.users.insert_one(user_model.model_dump())
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "user.created",
        "user",
        user_model.user_id,
        "success",
        metadata={"role": user_model.role, "business_role": user_model.business_role},
        client_ip=request.client.host if request.client else None,
    )
    return UserResponse(**user_model.model_dump())


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
):
    """Update user profile, role or status with strict role checks."""
    if current_user.role not in ("ADMIN", "EDITOR"):
        raise HTTPException(status_code=403, detail="Visitors have read-only access and cannot modify users.")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    existing = await db.users.find_one({"user_id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    # Editors cannot modify admin accounts or change roles
    if current_user.role == "EDITOR":
        if existing.get("role") == "ADMIN":
            raise HTTPException(status_code=403, detail="Editors cannot modify administrator accounts.")
        if payload.role is not None and payload.role != existing.get("role"):
            raise HTTPException(status_code=403, detail="Editors cannot change user roles.")

    # Prevent demoting the initial primary admin
    if user_id == "admin" and payload.role and payload.role != "ADMIN":
        raise HTTPException(status_code=400, detail="Cannot alter primary admin role.")

    update_dict = {}
    if payload.display_name is not None:
        update_dict["display_name"] = payload.display_name
    if payload.business_role is not None:
        update_dict["business_role"] = payload.business_role
    if payload.role is not None and current_user.role == "ADMIN":
        update_dict["role"] = payload.role
    if payload.is_active is not None and current_user.role == "ADMIN":
        if user_id == current_user.user_id and not payload.is_active:
            raise HTTPException(status_code=400, detail="Cannot deactivate own account.")
        update_dict["is_active"] = payload.is_active
    if payload.enforcement_status is not None:
        update_dict["enforcement_status"] = payload.enforcement_status

    if update_dict:
        await db.users.update_one({"user_id": user_id}, {"$set": update_dict})
        await record_audit(
            db,
            current_user.user_id,
            current_user.role,
            "user.updated",
            "user",
            user_id,
            "success",
            metadata={"updates": list(update_dict.keys())},
            client_ip=request.client.host if request.client else None,
        )

    updated = await db.users.find_one({"user_id": user_id})
    resp = UserResponse(**updated)
    return resp


@router.delete("/users/{user_id}", status_code=200)
async def delete_user(
    user_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_admin_user),
):
    """Delete a user record (ADMIN only)."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    if user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")
    if user_id == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete primary administrator account.")

    result = await db.users.delete_one({"user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "user.deleted",
        "user",
        user_id,
        "success",
        client_ip=request.client.host if request.client else None,
    )
    return {"status": "deleted", "user_id": user_id}


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
