from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone

class UserModel(BaseModel):
    user_id: str
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    source: str = "google_drive"
    created_at: datetime = datetime.now(timezone.utc)
