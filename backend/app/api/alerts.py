import re
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.dependencies import (
    ensure_self_or_admin,
    get_current_active_user,
    get_current_admin_user,
    get_current_editor_or_admin_user,
)
from app.database.mongodb import get_database
from app.models.alert import (
    AlertCreate,
    AlertNote,
    AlertResponse,
    AlertStatusUpdate,
)
from app.models.user import UserModel
from app.services.alerts import create_alert
from app.services.audit import record_audit

router = APIRouter()


def _object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid alert ID")


def _to_response(alert: dict) -> AlertResponse:
    alert = dict(alert)
    alert["id"] = str(alert.pop("_id"))
    return AlertResponse(**alert)


@router.get("", response_model=List[AlertResponse])
async def get_alerts(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    severity: Optional[str] = Query(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"),
    status_filter: Optional[str] = Query(
        None, alias="status", pattern="^(OPEN|ACKNOWLEDGED|INVESTIGATING|RESOLVED|DISMISSED)$"
    ),
    user_id: Optional[str] = None,
    q: Optional[str] = Query(None, max_length=100),
    current_user: UserModel = Depends(get_current_active_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    query: dict = {}
    if current_user.role in ("ADMIN", "EDITOR", "VISITOR"):
        if user_id:
            query["user_id"] = user_id
    else:
        query["user_id"] = current_user.user_id
    if severity:
        query["severity"] = severity
    if status_filter:
        query["status"] = status_filter
    if q:
        safe = re.escape(q)
        query["$or"] = [
            {"title": {"$regex": safe, "$options": "i"}},
            {"reason": {"$regex": safe, "$options": "i"}},
        ]

    cursor = db.alerts.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    return [_to_response(a) for a in await cursor.to_list(length=limit)]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str, current_user: UserModel = Depends(get_current_active_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    alert = await db.alerts.find_one({"_id": _object_id(alert_id)})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_self_or_admin(current_user, alert.get("user_id"))
    return _to_response(alert)


@router.post("", status_code=201, response_model=AlertResponse)
async def create_manual_alert(
    payload: AlertCreate,
    request: Request,
    current_user: UserModel = Depends(get_current_admin_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    alert = await create_alert(
        db,
        severity=payload.severity,
        title=payload.title,
        reason=payload.reason,
        user_id=payload.user_id,
        device_id=payload.device_id,
        saas_app=payload.saas_app,
        resource_id=payload.resource_id,
        event_id=payload.event_id,
        risk_score=payload.risk_score,
        source=payload.source or "manual",
        evidence=payload.evidence,
        dedupe_scope=f"manual-{datetime.now(timezone.utc).isoformat()}",
    )
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "alert.created",
        "alert",
        str(alert["_id"]),
        "success",
        reason=payload.reason[:200],
        client_ip=request.client.host if request.client else None,
    )
    return _to_response(alert)


@router.patch("/{alert_id}/status", response_model=AlertResponse)
async def update_alert_status(
    alert_id: str,
    payload: AlertStatusUpdate,
    request: Request,
    current_user: UserModel = Depends(get_current_editor_or_admin_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    now = datetime.now(timezone.utc)
    update: dict = {
        "status": payload.status,
        "updated_at": now,
    }
    if payload.status == "ACKNOWLEDGED":
        update["acknowledged_at"] = now
        update["acknowledged_by"] = current_user.user_id

    result = await db.alerts.update_one(
        {"_id": _object_id(alert_id)},
        {
            "$set": update,
            "$push": {
                "history": {
                    "timestamp": now,
                    "actor": current_user.user_id,
                    "action": f"status:{payload.status}",
                    "detail": payload.note,
                }
            },
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "alert.status_changed",
        "alert",
        alert_id,
        "success",
        metadata={"status": payload.status},
        client_ip=request.client.host if request.client else None,
    )
    alert = await db.alerts.find_one({"_id": _object_id(alert_id)})
    return _to_response(alert)


@router.post("/{alert_id}/notes", response_model=AlertResponse)
async def add_alert_note(
    alert_id: str,
    payload: AlertNote,
    request: Request,
    current_user: UserModel = Depends(get_current_admin_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    now = datetime.now(timezone.utc)
    result = await db.alerts.update_one(
        {"_id": _object_id(alert_id)},
        {
            "$set": {"updated_at": now},
            "$push": {
                "history": {
                    "timestamp": now,
                    "actor": current_user.user_id,
                    "action": "note",
                    "detail": payload.note,
                }
            },
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "alert.note_added",
        "alert",
        alert_id,
        "success",
        client_ip=request.client.host if request.client else None,
    )
    return _to_response(await db.alerts.find_one({"_id": _object_id(alert_id)}))
