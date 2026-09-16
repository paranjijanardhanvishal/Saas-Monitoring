from fastapi import APIRouter, HTTPException
from app.database.mongodb import get_database
from app.models.user import UserModel
from typing import List

router = APIRouter()

@router.get("/users", response_model=List[UserModel])
async def get_users(limit: int = 50, skip: int = 0):
    """Get monitored users."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    users_cursor = db.users.find().skip(skip).limit(limit)
    users = await users_cursor.to_list(length=limit)
    return users
