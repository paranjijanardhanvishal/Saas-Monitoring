from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import uuid

class EntitySummary(BaseModel):
    entity_type: str
    sensitivity: str
    count: int

class PrivacyFindingModel(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_id: Optional[str] = None
    event_id: Optional[str] = None
    user_id: Optional[str] = "unknown"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    entities: List[EntitySummary] = []
    
    high_count: int = 0
    moderate_count: int = 0
    low_count: int = 0
    
    sensitivity_score: int = 0
    category: str = "SAFE"

class PrivacyAnalysisRequest(BaseModel):
    text: str
    file_id: Optional[str] = None
    event_id: Optional[str] = None
    user_id: Optional[str] = "unknown"
