from app.database.mongodb import get_database
from app.models.event import EventModel
from app.models.file import FileModel
from app.models.user import UserModel
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

async def persist_files(files_data: List[Dict[str, Any]]):
    """Persist file metadata to MongoDB."""
    db = get_database()
    if db is None:
        logger.error("Database connection not established.")
        return
        
    for item in files_data:
        owner_email = None
        if 'owners' in item and len(item['owners']) > 0:
            owner_email = item['owners'][0].get('emailAddress')
            
        file_model = FileModel(
            file_id=item['id'],
            name=item['name'],
            mime_type=item['mimeType'],
            owner_email=owner_email,
            created_time=item.get('createdTime'),
            modified_time=item.get('modifiedTime'),
            web_url=item.get('webViewLink')
        )
        
        await db.files.update_one(
            {"file_id": file_model.file_id},
            {"$set": file_model.model_dump()},
            upsert=True
        )

async def persist_user(user_data: Dict[str, Any]):
    """Persist user info to MongoDB."""
    db = get_database()
    if db is None or not user_data:
        return
        
    email = user_data.get('emailAddress')
    user_id = user_data.get('permissionId', email)
    
    if user_id:
        user_model = UserModel(
            user_id=user_id,
            email=email,
            display_name=user_data.get('displayName')
        )
        
        await db.users.update_one(
            {"user_id": user_model.user_id},
            {"$set": user_model.model_dump()},
            upsert=True
        )

async def log_event(event_data: EventModel):
    """Log a structured monitoring event."""
    db = get_database()
    if db is None:
        return
        
    await db.events.insert_one(event_data.model_dump())
