import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.behavior.schemas import AnomalyFindingModel, BehaviorAnalysisRequest, BehaviorProfileModel
from app.behavior.service import analyze_behavior
from app.core.dependencies import ensure_self_or_admin, get_current_active_user
from app.database.mongodb import get_database
from app.models.user import UserModel
from app.services.audit import record_audit

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnomalyFindingModel, status_code=201)
async def perform_behavior_analysis(
    payload: BehaviorAnalysisRequest,
    request: Request,
    target_user_id: Optional[str] = Query(
        default=None, description="ADMIN only: analyse an event for another user."
    ),
    current_user: UserModel = Depends(get_current_active_user),
):
    """Run EWMA behavioural analysis for a persisted event.

    The event must exist and belong to the requested user. Analysis uses the
    server-side ingestion timestamp so a client cannot move its own baseline.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    owner_id = target_user_id or payload.user_id or current_user.user_id
    ensure_self_or_admin(current_user, owner_id)

    event = await db.events.find_one({"event_id": payload.event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.get("user_id") != owner_id:
        raise HTTPException(status_code=403, detail="Event does not belong to this user")

    baseline_time = event.get("ingestion_timestamp") or event.get("timestamp") or payload.timestamp
    target = await db.users.find_one({"user_id": owner_id})
    try:
        finding = await analyze_behavior(
            BehaviorAnalysisRequest(
                user_id=owner_id,
                event_id=payload.event_id,
                timestamp=baseline_time,
            ),
            business_role=(target or {}).get("business_role", "GENERAL"),
            event=event,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Behavior analysis failed for event %s", payload.event_id)
        raise HTTPException(status_code=500, detail="Behavior analysis failed")

    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "behavior.analyzed",
        "anomaly",
        finding.anomaly_id,
        "success",
        metadata={"owner_id": owner_id, "event_id": payload.event_id},
        client_ip=request.client.host if request.client else None,
    )
    return finding


@router.get("/profiles", response_model=List[BehaviorProfileModel])
async def list_behavior_profiles(
    limit: int = Query(100, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user_id: Optional[str] = Query(default=None, max_length=64),
    current_user: UserModel = Depends(get_current_active_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    query: dict = {}
    if current_user.role == "ADMIN":
        if user_id:
            query["user_id"] = user_id
    else:
        query["user_id"] = current_user.user_id

    cursor = (
        db.behavior_profiles.find(query)
        .sort("updated_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


@router.get("/users/{user_id}", response_model=BehaviorProfileModel)
async def get_user_behavior_profile(
    user_id: str,
    current_user: UserModel = Depends(get_current_active_user),
):
    ensure_self_or_admin(current_user, user_id)
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    profile = await db.behavior_profiles.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/anomalies", response_model=List[AnomalyFindingModel])
async def get_anomalies(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user_id: Optional[str] = Query(default=None, max_length=64),
    only_anomalies: bool = False,
    role_mismatches_only: bool = False,
    current_user: UserModel = Depends(get_current_active_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    query: dict = {}
    if current_user.role == "ADMIN":
        if user_id:
            query["user_id"] = user_id
    else:
        query["user_id"] = current_user.user_id
    if only_anomalies:
        query["is_anomaly"] = True
    if role_mismatches_only:
        query["role_mismatch"] = True

    cursor = db.anomalies.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


@router.get("/anomalies/{anomaly_id}", response_model=AnomalyFindingModel)
async def get_anomaly(
    anomaly_id: str,
    current_user: UserModel = Depends(get_current_active_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    finding = await db.anomalies.find_one({"anomaly_id": anomaly_id})
    if not finding:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    ensure_self_or_admin(current_user, finding.get("user_id"))
    return finding
