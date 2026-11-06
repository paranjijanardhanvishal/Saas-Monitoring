import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.dependencies import (
    ensure_self_or_admin,
    get_current_active_user,
    require_ingestion_key,
)
from app.database.mongodb import get_database
from app.models.event import EventModel
from app.models.user import UserModel
from app.services.audit import record_audit
from app.services.monitoring import log_event

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/events", status_code=201, response_model=dict)
async def create_event(
    event: EventModel,
    request: Request,
    _: None = Depends(require_ingestion_key),
):
    """Ingest a SaaS proxy event using a server-side ingestion credential.

    The proxy session identity is explicitly marked unverified. ``user_id`` is
    cleared regardless of the payload so a proxy cannot impersonate a user.
    """
    now = datetime.now(timezone.utc)
    timestamp = event.timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    if timestamp > now + timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="Event timestamp is in the future")
    if timestamp < now - timedelta(days=365):
        raise HTTPException(status_code=400, detail="Event timestamp is too old")

    event.source = "saas_proxy"
    event.user_id = None
    event.device_id = None
    event.schema_version = "1.0"
    event.timestamp = timestamp
    event.metadata = {**(event.metadata or {}), "identity_verified": False}
    try:
        inserted = await log_event(event)
        db = get_database()
        if db is not None:
            await record_audit(
                db,
                "saas_proxy",
                "SERVICE",
                "event.ingested",
                "event",
                event.event_id,
                "success" if inserted else "duplicate",
                client_ip=request.client.host if request.client else None,
                metadata={"source": "saas_proxy"},
            )
        return {
            "status": "success" if inserted else "duplicate",
            "event_id": event.event_id,
            "duplicate": not inserted,
            "identity_verified": False,
        }
    except Exception:
        logger.exception("SaaS proxy event ingestion failed")
        raise HTTPException(status_code=500, detail="Event ingestion failed")


@router.get("/events", response_model=List[EventModel])
async def get_events(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user_id: Optional[str] = Query(None, max_length=64),
    device_id: Optional[str] = Query(None, max_length=128),
    source: Optional[str] = Query(None, max_length=32),
    action: Optional[str] = Query(None, max_length=32),
    event_type: Optional[str] = Query(None, max_length=64),
    q: Optional[str] = Query(None, max_length=100),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    current_user: UserModel = Depends(get_current_active_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    if current_user.role in ("EDITOR", "VISITOR"):
        raise HTTPException(
            status_code=403,
            detail="Live Activity monitoring is restricted to SOC administrators.",
        )

    if start and end and start > end:
        raise HTTPException(status_code=400, detail="start must be before end")

    query: dict = {}
    if current_user.role == "ADMIN":
        if user_id:
            query["user_id"] = user_id
        if device_id:
            query["device_id"] = device_id
    else:
        query["user_id"] = current_user.user_id
    if source:
        query["source"] = source
    if action:
        query["action"] = action
    if event_type:
        query["event_type"] = event_type
    if q:
        safe = re.escape(q)
        query["$or"] = [
            {"resource_id": {"$regex": safe, "$options": "i"}},
            {"resource_name": {"$regex": safe, "$options": "i"}},
            {"saas_app": {"$regex": safe, "$options": "i"}},
            {"application.name": {"$regex": safe, "$options": "i"}},
        ]
    if start or end:
        time_filter = {}
        if start:
            time_filter["$gte"] = start
        if end:
            time_filter["$lte"] = end
        query["timestamp"] = time_filter

    cursor = db.events.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


@router.get("/events/{event_id}", response_model=EventModel)
async def get_event(event_id: str, current_user: UserModel = Depends(get_current_active_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    event = await db.events.find_one({"event_id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    ensure_self_or_admin(current_user, event.get("user_id"))
    return event
