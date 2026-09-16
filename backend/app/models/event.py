from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum

class ActionEnum(str, Enum):
    ACCESS = "ACCESS"
    DOWNLOAD = "DOWNLOAD"
    UPLOAD = "UPLOAD"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    SHARE = "SHARE"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"

class EventModel(BaseModel):
    event_id: str
    user_id: Optional[str] = None
    file_id: Optional[str] = None
    action: ActionEnum
    source: str = "google_drive"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None
