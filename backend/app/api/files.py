from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_current_active_user
from app.database.mongodb import get_database
from app.models.file import FileModel
from app.models.user import UserModel

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
    if current_user.role == "ADMIN":
        if owner_email:
            query["owner_email"] = owner_email
    else:
        if not current_user.email:
            return []
        query["owner_email"] = str(current_user.email).lower()
    if source:
        query["source"] = source

    files_cursor = db.files.find(query).sort("modified_time", -1).skip(skip).limit(limit)
    return await files_cursor.to_list(length=limit)


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
    if current_user.role != "ADMIN":
        if not current_user.email or (
            (file.get("owner_email") or "").lower() != str(current_user.email).lower()
        ):
            # Do not disclose the existence of another user's file.
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
    if current_user.role != "ADMIN":
        if not current_user.email or (
            (file.get("owner_email") or "").lower() != str(current_user.email).lower()
        ):
            raise HTTPException(status_code=404, detail="File not found")

    cursor = (
        db.pii_findings.find({"file_id": file_id}).sort("timestamp", -1).limit(limit)
    )
    return await cursor.to_list(length=limit)
