from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FileModel(BaseModel):
    file_id: str
    name: str
    mime_type: str
    size: Optional[int] = None
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    source: str = "google_drive"
    retrieved_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    folder_id: Optional[str] = None
    drive_id: Optional[str] = None
    provider_file_id: Optional[str] = None
    web_url: Optional[str] = None
    available: Optional[bool] = True

    # Offline content analysis & Vector metadata indexing (Base Paper Phase 1)
    analysis_status: Optional[str] = "PENDING"  # PENDING, COMPLETED, FAILED, UNSUPPORTED
    last_analyzed_at: Optional[datetime] = None
    analysis_error: Optional[str] = None
    sensitivity_score: Optional[int] = None
    sensitivity_tier: Optional[str] = None  # SAFE, SENSITIVE, HIGH_RISK
    finding_id: Optional[str] = None
    vector_indexed: bool = False
    sharing_scope: Optional[str] = "private"  # private, shared_domain, public
    permissions_summary: Optional[List[Dict[str, Any]]] = None
    entities_summary: Optional[List[Dict[str, Any]]] = None
