from pydantic import BaseModel, Field
from typing import Dict, Optional, Any
from datetime import datetime, timezone
import uuid

class BehaviorAnalysisRequest(BaseModel):
    user_id: str
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = {}

class BehaviorProfileModel(BaseModel):
    user_id: str
    last_activity_timestamp: datetime
    ewma: Dict[str, float]
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AnomalyFindingModel(BaseModel):
    anomaly_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    activity_rate: float
    ewma: Dict[str, float]
    deviation: float
    
    is_anomaly: bool
    reason: str
    anomaly_type: str = "ACTIVITY_SPIKE"
