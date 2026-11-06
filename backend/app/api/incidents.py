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
from app.models.incident import (
    IncidentAssign,
    IncidentCreate,
    IncidentNote,
    IncidentResponse,
    IncidentStatusUpdate,
)
from app.models.user import UserModel
from app.services.audit import record_audit

router = APIRouter()


def _object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid incident ID")


def _to_response(incident: dict) -> IncidentResponse:
    incident = dict(incident)
    incident["id"] = str(incident.pop("_id"))
    incident.setdefault("response_history", [])
    incident.setdefault("history", [])
    return IncidentResponse(**incident)


@router.get("", response_model=List[IncidentResponse])
async def get_incidents(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    severity: Optional[str] = Query(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"),
    status_filter: Optional[str] = Query(
        None, alias="status", pattern="^(OPEN|INVESTIGATING|CONTAINED|RESOLVED|DISMISSED)$"
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
            {"assigned_to": {"$regex": safe, "$options": "i"}},
        ]

    cursor = db.incidents.find(query).sort("created_time", -1).skip(skip).limit(limit)
    return [_to_response(i) for i in await cursor.to_list(length=limit)]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str, current_user: UserModel = Depends(get_current_active_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    incident = await db.incidents.find_one({"_id": _object_id(incident_id)})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    ensure_self_or_admin(current_user, incident.get("user_id"))
    return _to_response(incident)


@router.post("", status_code=201, response_model=IncidentResponse)
async def create_incident(
    payload: IncidentCreate,
    request: Request,
    current_user: UserModel = Depends(get_current_editor_or_admin_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    now = datetime.now(timezone.utc)
    document = payload.model_dump()
    document.update(
        {
            "created_time": now,
            "updated_at": now,
            "response_history": [f"Incident created by {current_user.user_id}"],
            "history": [
                {
                    "timestamp": now,
                    "actor": current_user.user_id,
                    "action": "created",
                    "detail": payload.reason[:200],
                }
            ],
        }
    )
    result = await db.incidents.insert_one(document)
    document["_id"] = result.inserted_id
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "incident.created",
        "incident",
        str(result.inserted_id),
        "success",
        reason=payload.reason[:200],
        client_ip=request.client.host if request.client else None,
    )
    return _to_response(document)


@router.patch("/{incident_id}/status", response_model=IncidentResponse)
async def update_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    request: Request,
    current_user: UserModel = Depends(get_current_editor_or_admin_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    now = datetime.now(timezone.utc)
    result = await db.incidents.update_one(
        {"_id": _object_id(incident_id)},
        {
            "$set": {"status": payload.status, "updated_at": now},
            "$push": {
                "response_history": f"Status changed to {payload.status} by {current_user.user_id}",
                "history": {
                    "timestamp": now,
                    "actor": current_user.user_id,
                    "action": f"status:{payload.status}",
                    "detail": payload.note,
                },
            },
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Incident not found")
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "incident.status_changed",
        "incident",
        incident_id,
        "success",
        metadata={"status": payload.status},
        client_ip=request.client.host if request.client else None,
    )
    return _to_response(await db.incidents.find_one({"_id": _object_id(incident_id)}))


@router.patch("/{incident_id}/assign", response_model=IncidentResponse)
async def assign_incident(
    incident_id: str,
    payload: IncidentAssign,
    request: Request,
    current_user: UserModel = Depends(get_current_editor_or_admin_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    now = datetime.now(timezone.utc)
    result = await db.incidents.update_one(
        {"_id": _object_id(incident_id)},
        {
            "$set": {"assigned_to": payload.assigned_to, "updated_at": now},
            "$push": {
                "response_history": f"Assigned to {payload.assigned_to}",
                "history": {
                    "timestamp": now,
                    "actor": current_user.user_id,
                    "action": "assigned",
                    "detail": payload.assigned_to,
                },
            },
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Incident not found")
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "incident.assigned",
        "incident",
        incident_id,
        "success",
        metadata={"assigned_to": payload.assigned_to},
        client_ip=request.client.host if request.client else None,
    )
    return _to_response(await db.incidents.find_one({"_id": _object_id(incident_id)}))


@router.post("/{incident_id}/notes", response_model=IncidentResponse)
async def add_incident_note(
    incident_id: str,
    payload: IncidentNote,
    request: Request,
    current_user: UserModel = Depends(get_current_editor_or_admin_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    now = datetime.now(timezone.utc)
    result = await db.incidents.update_one(
        {"_id": _object_id(incident_id)},
        {
            "$set": {"updated_at": now},
            "$push": {
                "notes": {
                    "timestamp": now,
                    "author": current_user.user_id,
                    "note": payload.note,
                },
                "history": {
                    "timestamp": now,
                    "actor": current_user.user_id,
                    "action": "note_added",
                    "detail": payload.note[:200],
                },
            },
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Incident not found")
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "incident.note_added",
        "incident",
        incident_id,
        "success",
        client_ip=request.client.host if request.client else None,
    )
    return _to_response(await db.incidents.find_one({"_id": _object_id(incident_id)}))
