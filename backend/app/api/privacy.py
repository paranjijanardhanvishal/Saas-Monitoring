import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.dependencies import ensure_self_or_admin, get_current_active_user
from app.core.config import settings
from app.database.mongodb import get_database
from app.models.event import ActionEnum, EventModel
from app.models.user import UserModel
from app.privacy.ocr import OCRInputError, OCRUnavailableError, extract_document_text, get_ocr_status
from app.privacy.schemas import OCRScanResponse, PrivacyAnalysisRequest, PrivacyFindingModel
from app.privacy.service import analyze_text
from app.risk.schemas import RiskAssessmentRequest
from app.risk.service import analyze_risk
from app.services.alerts import create_alerts_from_risk
from app.services.audit import record_audit

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ocr-status")
async def ocr_status(current_user: UserModel = Depends(get_current_active_user)):
    """Report local OCR readiness without exposing executable paths."""
    return get_ocr_status()


@router.post("/analyze", response_model=PrivacyFindingModel, status_code=201)
async def perform_privacy_analysis(
    request: Request,
    payload: PrivacyAnalysisRequest,
    target_user_id: Optional[str] = Query(
        default=None,
        description="ADMIN only: attribute the finding to another user.",
        max_length=64,
    ),
    current_user: UserModel = Depends(get_current_active_user),
):
    """Analyse controlled text and store derived PII metadata.

    The request body cannot choose the owning user. Raw text is not stored.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    owner_id = current_user.user_id
    if target_user_id and target_user_id != current_user.user_id:
        if current_user.role != "ADMIN":
            raise HTTPException(status_code=403, detail="Only administrators may target another user")
        if not await db.users.find_one({"user_id": target_user_id}):
            raise HTTPException(status_code=404, detail="Target user not found")
        owner_id = target_user_id

    try:
        finding = await analyze_text(payload, owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        logger.error("PII engine unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="PII analysis engine is unavailable")
    except Exception:
        logger.exception("Privacy analysis failed for user %s", owner_id)
        raise HTTPException(status_code=500, detail="Privacy analysis failed")

    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "privacy.analyzed",
        "pii_finding",
        finding.finding_id,
        "success",
        metadata={
            "owner_id": owner_id,
            "engine": finding.engine,
            "score": finding.sensitivity_score,
            "file_id": finding.file_id,
        },
        client_ip=request.client.host if request.client else None,
    )
    return finding


@router.post("/scan-ocr", response_model=OCRScanResponse, status_code=201)
async def scan_ocr_document(
    request: Request,
    upload: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_active_user),
):
    """OCR a user-selected image/PDF and persist only derived PII metadata.

    The original filename, uploaded bytes, OCR text and matched PII values are
    not persisted or included in audit metadata. A metadata-only scan event links
    the derived finding to a risk assessment without storing document content.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    try:
        payload_bytes = await upload.read(settings.OCR_MAX_FILE_BYTES + 1)
    finally:
        await upload.close()
    if len(payload_bytes) > settings.OCR_MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="The uploaded file exceeds the configured size limit.")

    try:
        extraction = await run_in_threadpool(
            extract_document_text, payload_bytes, upload.filename
        )
    except OCRUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except OCRInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        payload_bytes = b""

    if not extraction.text.strip():
        raise HTTPException(status_code=422, detail="No readable text was found in the uploaded document.")

    file_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc)
    file_type = Path(upload.filename or "").suffix.lower().lstrip(".")
    try:
        finding = await analyze_text(
            PrivacyAnalysisRequest(
                text=extraction.text,
                file_id=file_id,
                event_id=event_id,
            ),
            current_user.user_id,
            source="ocr_upload",
            ocr_engine=extraction.engine,
            file_type=file_type,
            page_count=extraction.page_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        logger.error("PII engine unavailable during OCR scan")
        raise HTTPException(status_code=503, detail="PII analysis engine is unavailable") from exc
    finally:
        extraction = None

    event = EventModel(
        event_id=event_id,
        event_type="privacy.file_scanned",
        user_id=current_user.user_id,
        source="privacy_scan",
        action=ActionEnum.ACCESS,
        resource_id=file_id,
        timestamp=timestamp,
        ingestion_timestamp=timestamp,
        metadata={
            "scan_source": "ocr_upload",
            "ocr_engine": finding.ocr_engine,
            "file_type": file_type,
            "page_count": finding.page_count,
        },
    )
    try:
        await db.events.insert_one(event.model_dump())
    except Exception as exc:
        await db.pii_findings.delete_one({"finding_id": finding.finding_id})
        logger.exception("Could not persist the metadata event for OCR finding %s", finding.finding_id)
        raise HTTPException(status_code=500, detail="Could not store the scan result.") from exc

    risk_assessment = None
    try:
        risk_assessment = await analyze_risk(
            RiskAssessmentRequest(
                user_id=current_user.user_id,
                event_id=event_id,
                privacy_finding_id=finding.finding_id,
                include_context_signals=True,
                timestamp=timestamp,
            )
        )
        await create_alerts_from_risk(db, risk_assessment.model_dump())
    except Exception:
        logger.exception("Risk analysis failed for OCR finding %s", finding.finding_id)

    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "privacy.ocr_scanned",
        "pii_finding",
        finding.finding_id,
        "success",
        metadata={
            "file_type": file_type,
            "page_count": finding.page_count,
            "engine": finding.ocr_engine,
            "sensitivity_score": finding.sensitivity_score,
        },
        client_ip=request.client.host if request.client else None,
    )
    return OCRScanResponse(
        finding=finding,
        risk_assessment=risk_assessment.model_dump(mode="json") if risk_assessment else None,
        ocr_engine=finding.ocr_engine or "tesseract",
        page_count=finding.page_count or 1,
    )


@router.get("/findings", response_model=List[PrivacyFindingModel])
async def get_privacy_findings(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user_id: Optional[str] = Query(default=None, max_length=64),
    category: Optional[str] = Query(
        default=None, pattern="^(SAFE|SENSITIVE|HIGH_RISK)$"
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
        query["category"] = category

    cursor = db.pii_findings.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


@router.get("/findings/{finding_id}", response_model=PrivacyFindingModel)
async def get_privacy_finding(
    finding_id: str,
    current_user: UserModel = Depends(get_current_active_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    finding = await db.pii_findings.find_one({"finding_id": finding_id})
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    ensure_self_or_admin(current_user, finding.get("user_id"))
    return finding
