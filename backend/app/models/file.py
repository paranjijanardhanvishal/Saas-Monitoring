from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

class FileModel(BaseModel):
    file_id: str
    name: str
    mime_type: str
    owner_email: Optional[str] = None
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    web_url: Optional[str] = None
    source: str = "google_drive"
    retrieved_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
