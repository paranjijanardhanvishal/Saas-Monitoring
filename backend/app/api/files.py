from typing import List, Optional
import asyncio
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_active_user
from app.database.mongodb import get_database
from app.models.file import FileModel
from app.models.user import UserModel
from app.models.event import ActionEnum, EventModel
from app.services.google_drive import drive_service
from app.services.monitoring import log_event, persist_files
from app.services.audit import record_audit

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/files", response_model=List[FileModel])
async def get_files(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    owner_email: Optional[str] = Query(default=None, max_length=254),
    source: Optional[str] = Query(default=None, max_length=64),
    current_user: UserModel = Depends(get_current_active_user),
):
    """List synced cloud file metadata visible to the caller.

    Files are only linked to a user by owner email; content is never stored.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    query: dict = {}
    if owner_email and current_user.role == "ADMIN":
        query["owner_email"] = owner_email
    elif current_user.role != "ADMIN":
        # Shared-folder Drive records are visible across roles; legacy personal
        # metadata remains isolated to its owner.
        email = str(current_user.email).lower() if current_user.email else None
        query["$or"] = ([{"folder_id": {"$exists": True}}] + ([{"owner_email": email}] if email else []))
    if source:
        query["source"] = source

    query["available"] = {"$ne": False}
    files_cursor = db.files.find(query).sort("modified_time", -1).skip(skip).limit(limit)
    return await files_cursor.to_list(length=limit)


@router.get("/files/drive/status")
async def get_drive_status(
    current_user: UserModel = Depends(get_current_active_user),
):
    """Report non-sensitive Google Drive integration status."""
    return drive_service.get_status()


@router.post("/files/sync")
async def sync_drive_files(
    request: Request,
    current_user: UserModel = Depends(get_current_active_user),
):
    """Synchronize metadata for the configured shared Drive folder (ADMIN only)."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Administrator privileges required")
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        records = await asyncio.to_thread(drive_service.list_files)
        for record in records:
            record["_folder_id"] = drive_service.folder_id
        count = await persist_files(records)
        drive_ids = [item["id"] for item in records]
        # Scope cleanup to this provider and configured folder only; no cloud data is deleted.
        await db.files.update_many(
            {"source": "google_drive", "folder_id": drive_service.folder_id,
             "file_id": {"$nin": drive_ids}},
            {"$set": {"available": False}},
        )
        await db.files.update_many(
            {"source": "google_drive", "folder_id": drive_service.folder_id,
             "file_id": {"$in": drive_ids}},
            {"$set": {"available": True, "folder_id": drive_service.folder_id}},
        )
        await record_audit(db, current_user.user_id, current_user.role, "drive.files.synced",
                           "drive_folder", drive_service.folder_id, "success",
                           metadata={"file_count": count},
                           client_ip=request.client.host if request.client else None)
        return {"synchronized": count}
    except RuntimeError as rerr:
        logger.warning("Google Drive configuration error during sync: %s", rerr)
        await record_audit(db, current_user.user_id, current_user.role, "drive.files.synced",
                           "drive_folder", drive_service.folder_id or None, "failure",
                           reason=str(rerr),
                           client_ip=request.client.host if request.client else None)
        raise HTTPException(status_code=503, detail=str(rerr)) from rerr
    except Exception as exc:
        logger.exception("Google Drive metadata synchronization failed")
        await record_audit(db, current_user.user_id, current_user.role, "drive.files.synced",
                           "drive_folder", drive_service.folder_id or None, "failure",
                           reason="Provider synchronization failed",
                           client_ip=request.client.host if request.client else None)
        raise HTTPException(status_code=502, detail="Google Drive synchronization failed") from exc


@router.get("/files/{file_id}/download")
async def download_drive_file(
    file_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_active_user),
):
    """Backend-mediated download. ADMIN/USER only; never redirects to Drive."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    if current_user.role not in ("ADMIN", "USER"):
        await record_audit(db, current_user.user_id, current_user.role, "file.download",
                           "file", file_id, "denied", reason="Role cannot download shared files",
                           client_ip=request.client.host if request.client else None)
        raise HTTPException(status_code=403, detail="Your role is not permitted to download files")
    if not file_id or len(file_id) > 256 or any(c in file_id for c in "/\\"):
        raise HTTPException(status_code=400, detail="Invalid file ID")
    file = await db.files.find_one({"file_id": file_id, "source": "google_drive", "available": {"$ne": False}})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content, content_type = await asyncio.to_thread(drive_service.download_file, file_id)
    except RuntimeError as rerr:
        logger.warning("Google Drive configuration error during download: %s", rerr)
        await record_audit(db, current_user.user_id, current_user.role, "file.download",
                           "file", file_id, "failure", reason=str(rerr),
                           client_ip=request.client.host if request.client else None)
        raise HTTPException(status_code=503, detail=str(rerr)) from rerr
    except ValueError as verr:
        logger.warning("Google Drive invalid download request: %s", verr)
        raise HTTPException(status_code=400, detail=str(verr)) from verr
    except Exception as exc:
        logger.exception("Google Drive download failed for file ID %s", file_id)
        await record_audit(db, current_user.user_id, current_user.role, "file.download",
                           "file", file_id, "failure", reason="Provider download failed",
                           client_ip=request.client.host if request.client else None)
        raise HTTPException(status_code=502, detail="Cloud file is unavailable") from exc

    event_id = str(uuid4())
    timestamp = datetime.now(timezone.utc)
    event = EventModel(
        event_id=event_id, event_type="file.download", user_id=current_user.user_id,
        source="sensitive_files", saas_app="google_drive", action=ActionEnum.DOWNLOAD,
        resource_id=file_id, resource_name=str(file.get("name", ""))[:256],
        timestamp=timestamp, metadata={"file_type": file.get("mime_type"), "outcome": "success",
                                       "endpoint": "/api/files/{file_id}/download"},
    )
    try:
        inserted = await log_event(event)
        if inserted:
            from app.behavior.schemas import BehaviorAnalysisRequest
            from app.behavior.service import analyze_behavior
            user_doc = await db.users.find_one({"user_id": current_user.user_id})
            await analyze_behavior(
                BehaviorAnalysisRequest(user_id=current_user.user_id, event_id=event_id, timestamp=timestamp),
                business_role=(user_doc or {}).get("business_role", "GENERAL"),
                event=event.model_dump(),
            )
    except Exception:
        logger.exception("Download event persistence/EWMA processing failed")
        content.close()
        await record_audit(db, current_user.user_id, current_user.role, "file.download",
                           "file", file_id, "failure", reason="Monitoring pipeline unavailable",
                           client_ip=request.client.host if request.client else None)
        raise HTTPException(status_code=503, detail="Download monitoring is temporarily unavailable")
    await record_audit(db, current_user.user_id, current_user.role, "file.download",
                       "file", file_id, "success", metadata={"event_id": event_id},
                       client_ip=request.client.host if request.client else None)
    filename = re.sub(r"[\r\n\x00-\x1f\x7f\"\\/]", "_", str(file.get("name", "download")))[:180]
    provider_type = str(file.get("mime_type", content_type))
    if not re.fullmatch(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+", provider_type):
        provider_type = "application/octet-stream"
    return StreamingResponse(content, media_type=provider_type,
                             headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                      "X-Content-Type-Options": "nosniff"})


@router.get("/files/{file_id}", response_model=FileModel)
async def get_file(
    file_id: str,
    current_user: UserModel = Depends(get_current_active_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    file = await db.files.find_one({"file_id": file_id})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if file.get("available") is False or (
        not file.get("folder_id") and current_user.role != "ADMIN"
        and (not current_user.email or (file.get("owner_email") or "").lower() != str(current_user.email).lower())
    ):
        raise HTTPException(status_code=404, detail="File not found")
    return file


@router.get("/files/{file_id}/pii-findings")
async def get_file_pii_findings(
    file_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: UserModel = Depends(get_current_active_user),
):
    """Return derived PII metadata for a file the caller is allowed to see."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    file = await db.files.find_one({"file_id": file_id})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if file.get("available") is False or (
        not file.get("folder_id") and current_user.role != "ADMIN"
        and (not current_user.email or (file.get("owner_email") or "").lower() != str(current_user.email).lower())
    ):
        raise HTTPException(status_code=404, detail="File not found")

    cursor = (
        db.pii_findings.find({"file_id": file_id}).sort("timestamp", -1).limit(limit)
    )
    return await cursor.to_list(length=limit)
