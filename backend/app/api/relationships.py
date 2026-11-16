"""API endpoints for File-to-User and User-to-File Relationship Mapping."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_current_active_user
from app.database.mongodb import get_database
from app.models.user import UserModel
from app.services.relationships import (
    get_file_users_mapping,
    get_relationships_summary,
    get_user_files_mapping,
)

router = APIRouter()


@router.get("/relationships/files/{file_id}")
async def get_file_users(
    file_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: UserModel = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """File-to-User view: Show users associated with a cloud file and their activities.

    Non-admin callers only see their own activities. Admins see all users.
    """
    db = get_database()
    return await get_file_users_mapping(
        db,
        file_id=file_id,
        caller_user_id=current_user.user_id,
        caller_role=current_user.role,
        limit=limit,
    )


@router.get("/relationships/users/{user_id}")
async def get_user_files(
    user_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: UserModel = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """User-to-File view: Show cloud files accessed by a user and their activities.

    Non-admin users can ONLY query their own user ID.
    """
    db = get_database()
    return await get_user_files_mapping(
        db,
        target_user_id=user_id,
        caller_user_id=current_user.user_id,
        caller_role=current_user.role,
        limit=limit,
    )


@router.get("/relationships/summary")
async def get_summary(
    current_user: UserModel = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Summary of file-user relationship graph and activity counts."""
    db = get_database()
    return await get_relationships_summary(
        db,
        caller_user_id=current_user.user_id,
        caller_role=current_user.role,
    )
