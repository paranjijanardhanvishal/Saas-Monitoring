import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import settings
from app.core.dependencies import (
    DevicePrincipal,
    ensure_self_or_admin,
    get_current_admin_user,
    get_current_user,
    get_current_device,
    get_device_for_heartbeat,
)
from app.core.security import generate_opaque_token
from app.database.mongodb import get_database
from app.models.device import (
    DeviceResponse,
    EnrollmentRequest,
    EnrollmentResponse,
    EnrollmentTokenResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from app.models.event import EndpointEventIn, EventModel
from app.models.user import UserModel
from app.services.alerts import create_alert
from app.services.audit import record_audit
from app.services.devices import (
    activate_enrollment_token,
    consume_enrollment_token,
    issue_enrollment_token,
    revoke_device,
)
from app.services.monitoring import log_event
from app.services.risk_pipeline import evaluate_persisted_endpoint_event

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_ENDPOINT_EVENTS = {
    "process.started",
    "process.stopped",
    "application.foreground_changed",
    "application.usage",
    "session.locked",
    "session.unlocked",
    "session.logged_on",
    "session.logged_off",
    "system.started",
    "system.stopping",
    "system.suspended",
    "system.resumed",
    "file.created",
    "file.modified",
    "file.deleted",
    "file.download_observed",
    "file.access_observed",
    "failed_login.observed",
    "agent.error",
}
MAX_BATCH_SIZE = 200


@router.post("/enrollment-token", response_model=EnrollmentTokenResponse)
async def create_enrollment_token(
    request: Request,
    user_id: Optional[str] = None,
    current_user: UserModel = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    target_user_id = user_id or current_user.user_id
    ensure_self_or_admin(current_user, target_user_id)
    target = await db.users.find_one({"user_id": target_user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.get("monitoring_enabled") != "ALLOWED":
        raise HTTPException(
            status_code=409,
            detail="The user must grant ALLOWED monitoring consent before enrolling a device.",
        )

    raw, expires_at = await issue_enrollment_token(db, target_user_id, current_user.user_id)
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "device.enrollment_token_issued",
        "user",
        target_user_id,
        "success",
        client_ip=request.client.host if request.client else None,
    )
    return EnrollmentTokenResponse(
        enrollment_token=raw, expires_at=expires_at, user_id=target_user_id
    )


@router.post("/enroll", response_model=EnrollmentResponse, status_code=201)
async def enroll_device(payload: EnrollmentRequest):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    token_record = await consume_enrollment_token(db, payload.enrollment_token)
    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid or expired enrollment token")

    user_id = token_record["user_id"]
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=403, detail="Enrollment user no longer exists")
    if user.get("monitoring_enabled") != "ALLOWED":
        raise HTTPException(status_code=403, detail="Monitoring consent is not granted")
    if not user.get("is_active", True) or user.get("enforcement_status") != "ACTIVE":
        raise HTTPException(status_code=403, detail="Account is not permitted to enroll devices")

    existing = await db.devices.find_one({"device_id": payload.device_id})
    if existing and existing.get("status") == "ACTIVE":
        raise HTTPException(status_code=409, detail="This device is already enrolled")
    if existing and existing.get("user_id") != user_id:
        raise HTTPException(status_code=409, detail="Device identifier belongs to another user")

    raw_token, digest, prefix = generate_opaque_token("dev_")
    now = datetime.now(timezone.utc)
    device_doc = {
        "device_id": payload.device_id,
        "user_id": user_id,
        "hostname": payload.hostname,
        "os_version": payload.os_version,
        "agent_version": payload.agent_version,
        "status": "ACTIVE",
        "monitoring_enabled": True,
        "token_hash": digest,
        "token_prefix": prefix,
        "enrolled_at": now,
        "last_heartbeat": None,
        "revoked_at": None,
        "revoked_reason": None,
    }
    if existing:
        await db.devices.update_one({"_id": existing["_id"]}, {"$set": device_doc})
        device_id = existing["device_id"]
    else:
        await db.devices.insert_one(device_doc)
        device_id = payload.device_id

    await activate_enrollment_token(db, payload.enrollment_token, device_id)
    await record_audit(
        db,
        user_id,
        "USER",
        "device.enrolled",
        "device",
        device_id,
        "success",
        metadata={"hostname": payload.hostname[:120]},
    )
    return EnrollmentResponse(
        device_id=device_id,
        device_token=raw_token,
        user_id=user_id,
        heartbeat_interval=60,
    )


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def agent_heartbeat(
    request: HeartbeatRequest,
    principal: DevicePrincipal = Depends(get_device_for_heartbeat),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    monitoring_enabled = principal.user.monitoring_enabled == "ALLOWED"
    now = datetime.now(timezone.utc)
    await db.devices.update_one(
        {"device_id": principal.device_id, "user_id": principal.user_id},
        {
            "$set": {
                "hostname": request.hostname[:255],
                "os_version": request.os_version[:255],
                "agent_version": request.agent_version[:32],
                "last_heartbeat": now,
                "monitoring_enabled": monitoring_enabled,
            }
        },
    )
    return HeartbeatResponse(
        status="active" if monitoring_enabled else "consent_required",
        message="Monitoring active" if monitoring_enabled else "Monitoring paused: consent not granted",
        monitoring_enabled=monitoring_enabled,
        server_time=now,
        collection_interval_seconds=60,
    )


@router.post("/events")
async def ingest_endpoint_events(
    events: List[EndpointEventIn],
    principal: DevicePrincipal = Depends(get_current_device),
):
    if len(events) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=413, detail=f"Batch exceeds {MAX_BATCH_SIZE} events")
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    now = datetime.now(timezone.utc)
    accepted = 0
    duplicates = 0
    rejected = []
    created_events = []

    for index, item in enumerate(events):
        if item.event_type not in ALLOWED_ENDPOINT_EVENTS:
            rejected.append({"index": index, "reason": "unsupported event_type"})
            continue
        timestamp = item.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        timestamp = timestamp.astimezone(timezone.utc)
        if timestamp > now + timedelta(minutes=5):
            rejected.append({"index": index, "reason": "timestamp too far in the future"})
            continue
        if timestamp < now - timedelta(days=365):
            rejected.append({"index": index, "reason": "timestamp too old"})
            continue

        event = EventModel(
            event_id=item.event_id,
            event_type=item.event_type,
            timestamp=timestamp,
            action=item.action,
            user_id=principal.user_id,
            device_id=principal.device_id,
            session_id=None,
            source="endpoint_agent",
            saas_app="endpoint",
            resource_id=item.resource_id,
            resource_name=item.resource_name,
            application=item.application,
            device_info={
                "device_id": principal.device_id,
                "hostname": principal.device.get("hostname", ""),
                "os_version": principal.device.get("os_version", ""),
                "agent_version": principal.device.get("agent_version", ""),
            },
            metadata=item.metadata,
            correlation_id=item.correlation_id,
        )
        try:
            inserted = await log_event(event)
        except Exception:
            logger.exception("Failed to persist endpoint event %s", item.event_id)
            rejected.append({"index": index, "reason": "persistence failure"})
            continue
        if inserted:
            accepted += 1
            document = event.model_dump()
            document["ingestion_timestamp"] = now
            created_events.append(document)
        else:
            duplicates += 1

    for document in created_events:
        await evaluate_persisted_endpoint_event(db, document)

    await db.devices.update_one(
        {"device_id": principal.device_id},
        {"$set": {"last_event_at": now, "last_heartbeat": now}},
    )
    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
        "received": len(events),
    }


@router.get("/devices", response_model=List[DeviceResponse])
async def list_devices(
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(ACTIVE|REVOKED)$"),
    current_user: UserModel = Depends(get_current_admin_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    query = {}
    if status_filter:
        query["status"] = status_filter
    devices = await db.devices.find(query).sort("enrolled_at", -1).skip(skip).limit(limit).to_list(length=limit)
    return [DeviceResponse(**d) for d in devices]


@router.post("/devices/{device_id}/revoke")
async def revoke_enrolled_device(
    device_id: str,
    request: Request,
    reason: str = Query(min_length=3, max_length=500),
    current_user: UserModel = Depends(get_current_admin_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    ok = await revoke_device(db, device_id, reason)
    if not ok:
        raise HTTPException(status_code=404, detail="Active device not found")
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "device.revoked",
        "device",
        device_id,
        "success",
        reason=reason,
        client_ip=request.client.host if request.client else None,
    )
    return {"status": "success", "device_id": device_id}


@router.post("/test-alert")
async def create_test_alert(
    request: Request,
    current_user: UserModel = Depends(get_current_admin_user),
):
    """Create a clearly-labelled controlled test alert (never fake production data)."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    alert = await create_alert(
        db,
        severity="LOW",
        title="Controlled test alert",
        reason="Created from the administrative test endpoint to verify alerting.",
        user_id=current_user.user_id,
        source="controlled_test",
        dedupe_scope=f"test-{datetime.now(timezone.utc).isoformat()}",
    )
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "alert.test_created",
        "alert",
        str(alert.get("_id")),
        "success",
        client_ip=request.client.host if request.client else None,
    )
    return {"status": "created", "alert_id": str(alert.get("_id"))}
