import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.dependencies import ensure_self_or_admin, get_current_active_user
from app.database.mongodb import get_database
from app.models.user import UserModel
from app.risk.schemas import RiskAssessmentModel, RiskAssessmentRequest
from app.risk.service import analyze_risk
from app.services.alerts import create_alerts_from_risk
from app.services.audit import record_audit

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=RiskAssessmentModel, status_code=201)
async def perform_risk_assessment(
    payload: RiskAssessmentRequest,
    request: Request,
    target_user_id: Optional[str] = Query(
        default=None, description="ADMIN only: assess an event for another user."
    ),
    current_user: UserModel = Depends(get_current_active_user),
):
    """Combine stored privacy/behaviour findings and server-derived context."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    owner_id = target_user_id or payload.user_id or current_user.user_id
    ensure_self_or_admin(current_user, owner_id)

    try:
        assessment = await analyze_risk(
            RiskAssessmentRequest(
                user_id=owner_id,
                event_id=payload.event_id,
                privacy_finding_id=payload.privacy_finding_id,
                anomaly_id=payload.anomaly_id,
                include_context_signals=True,
                timestamp=payload.timestamp,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Risk assessment failed for event %s", payload.event_id)
        raise HTTPException(status_code=500, detail="Risk assessment failed")

    alerts = await create_alerts_from_risk(db, assessment.model_dump())
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "risk.assessed",
        "risk_assessment",
        assessment.risk_id,
        "success",
        metadata={
            "owner_id": owner_id,
            "event_id": payload.event_id,
            "category": assessment.risk_category,
            "score": assessment.combined_score,
            "alerts_created": len(alerts),
        },
        client_ip=request.client.host if request.client else None,
    )
    return assessment


@router.get("/assessments", response_model=List[RiskAssessmentModel])
async def get_risk_assessments(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user_id: Optional[str] = Query(default=None, max_length=64),
    category: Optional[str] = Query(
        default=None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"
    ),
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
    if category:
        query["risk_category"] = category

    cursor = db.risk_assessments.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


@router.get("/assessments/{risk_id}", response_model=RiskAssessmentModel)
async def get_risk_assessment(
    risk_id: str,
    current_user: UserModel = Depends(get_current_active_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    assessment = await db.risk_assessments.find_one({"risk_id": risk_id})
    if not assessment:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    ensure_self_or_admin(current_user, assessment.get("user_id"))
    return assessment


@router.get("/users/{user_id}", response_model=List[RiskAssessmentModel])
async def get_user_risk_assessments(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: UserModel = Depends(get_current_active_user),
):
    ensure_self_or_admin(current_user, user_id)
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    cursor = (
        db.risk_assessments.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    )
    return await cursor.to_list(length=limit)


@router.get("/summary")
async def get_risk_summary(current_user: UserModel = Depends(get_current_active_user)):
    """Risk category distribution and highest-risk users for dashboards."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    match: dict = {}
    if current_user.role != "ADMIN":
        match["user_id"] = current_user.user_id
    pipeline = [{"$match": match}] if match else []
    pipeline += [
        {"$group": {"_id": "$risk_category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    by_category = await db.risk_assessments.aggregate(pipeline).to_list(length=10)

    top_pipeline = [{"$match": match}] if match else []
    top_pipeline += [
        {
            "$group": {
                "_id": "$user_id",
                "max_score": {"$max": "$combined_score"},
                "assessments": {"$sum": 1},
                "last_seen": {"$max": "$timestamp"},
            }
        },
        {"$sort": {"max_score": -1}},
        {"$limit": 10},
    ]
    top_users = await db.risk_assessments.aggregate(top_pipeline).to_list(length=10)
    for item in top_users:
        item["user_id"] = item.pop("_id")

    return {"by_category": by_category, "top_users": top_users}
