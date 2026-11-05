import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.dependencies import (
    ensure_self_or_admin,
    get_current_active_user,
    get_current_admin_user,
)
from app.database.mongodb import get_database
from app.enforcement.policy import determine_response_action, requires_confirmation
from app.enforcement.schemas import (
    EnforcementRecommendation,
    EnforcementRequest,
    EnforcementResponseModel,
    RollbackRequest,
)
from app.enforcement.service import (
    EnforcementConfirmationRequired,
    EnforcementConflict,
    EnforcementNotFound,
    execute_response,
    rollback_response,
)
from app.models.user import UserModel
from app.services.audit import record_audit

logger = logging.getLogger(__name__)
router = APIRouter()


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


@router.get(
    "/recommendation/{risk_id}", response_model=EnforcementRecommendation
)
async def get_recommendation(
    risk_id: str,
    current_user: UserModel = Depends(get_current_admin_user),
):
    """Advisory recommendation only; nothing is executed."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    risk = await db.risk_assessments.find_one({"risk_id": risk_id})
    if not risk:
        raise _not_found("Risk assessment not found")

    user_id = risk.get("user_id")
    user = await db.users.find_one({"user_id": user_id}) if user_id else None
    active_devices = (
        await db.devices.count_documents({"user_id": user_id, "status": "ACTIVE"})
        if user_id
        else 0
    )
    existing = await db.enforcement_responses.find_one({"risk_id": risk_id})
    action = determine_response_action(risk.get("risk_category", "LOW"))
    return EnforcementRecommendation(
        risk_id=risk_id,
        user_id=user_id,
        event_id=risk.get("event_id"),
        risk_category=risk.get("risk_category", "UNKNOWN"),
        combined_score=risk.get("combined_score"),
        recommended_action=action,
        requires_confirmation=requires_confirmation(action),
        current_enforcement_status=user.get("enforcement_status") if user else None,
        active_devices=active_devices,
        existing_response_id=existing.get("response_id") if existing else None,
    )


@router.post("/respond", response_model=EnforcementResponseModel, status_code=201)
async def trigger_enforcement_response(
    payload: EnforcementRequest,
    request: Request,
    current_user: UserModel = Depends(get_current_admin_user),
):
    """Execute an administrator-confirmed response for a risk assessment."""
    try:
        response = await execute_response(payload, current_user.user_id)
    except EnforcementNotFound as exc:
        raise _not_found(str(exc))
    except EnforcementConfirmationRequired as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except EnforcementConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    db = get_database()
    if db is not None:
        await record_audit(
            db,
            current_user.user_id,
            current_user.role,
            f"enforcement.{response.action_taken.value.lower()}",
            "risk_assessment",
            payload.risk_id,
            response.response_status.value.lower(),
            reason=response.reason,
            metadata={
                "response_id": response.response_id,
                "user_id": response.user_id,
                "revoked_devices": response.revoked_devices,
                "confirmed": response.confirmed,
            },
            client_ip=request.client.host if request.client else None,
        )
    return response


@router.get("/responses", response_model=List[EnforcementResponseModel])
async def get_enforcement_responses(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user_id: Optional[str] = Query(default=None, max_length=64),
    action: Optional[str] = Query(default=None, max_length=32),
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
    if action:
        query["action_taken"] = action

    cursor = (
        db.enforcement_responses.find(query)
        .sort("timestamp", -1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


@router.get("/responses/{response_id}", response_model=EnforcementResponseModel)
async def get_enforcement_response(
    response_id: str,
    current_user: UserModel = Depends(get_current_active_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    response = await db.enforcement_responses.find_one({"response_id": response_id})
    if not response:
        raise _not_found("Response not found")
    ensure_self_or_admin(current_user, response.get("user_id"))
    return response


@router.post(
    "/responses/{response_id}/rollback", response_model=EnforcementResponseModel
)
async def rollback_enforcement_response(
    response_id: str,
    payload: RollbackRequest,
    request: Request,
    current_user: UserModel = Depends(get_current_admin_user),
):
    """Undo an active restriction. Revoked devices must re-enroll."""
    try:
        response = await rollback_response(response_id, current_user.user_id, payload.reason)
    except EnforcementNotFound as exc:
        raise _not_found(str(exc))
    except EnforcementConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    db = get_database()
    if db is not None:
        await record_audit(
            db,
            current_user.user_id,
            current_user.role,
            "enforcement.rollback",
            "enforcement_response",
            response_id,
            "success",
            reason=payload.reason,
            metadata={"user_id": response.user_id},
            client_ip=request.client.host if request.client else None,
        )
    return response


@router.get("/users/{user_id}", response_model=List[EnforcementResponseModel])
async def get_user_responses(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: UserModel = Depends(get_current_active_user),
):
    ensure_self_or_admin(current_user, user_id)
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    cursor = (
        db.enforcement_responses.find({"user_id": user_id})
        .sort("timestamp", -1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)
