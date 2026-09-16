from fastapi import APIRouter, HTTPException
from app.database.mongodb import get_database
from app.models.file import FileModel
from typing import List

router = APIRouter()

@router.get("/files", response_model=List[FileModel])
async def get_files(limit: int = 50, skip: int = 0):
    """Get monitored files."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    files_cursor = db.files.find().skip(skip).limit(limit)
    files = await files_cursor.to_list(length=limit)
    return files

@router.get("/files/{file_id}", response_model=FileModel)
async def get_file(file_id: str):
    """Get a specific file by ID."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    file = await db.files.find_one({"file_id": file_id})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file
