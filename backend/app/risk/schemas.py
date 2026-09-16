from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import uuid

class RiskAssessmentRequest(BaseModel):
    user_id: str
    event_id: str
    privacy_finding_id: Optional[str] = None
    anomaly_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RiskAssessmentModel(BaseModel):
    risk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    event_id: str
    privacy_finding_id: Optional[str] = None
    anomaly_id: Optional[str] = None
    
    privacy_score: float = 0.0
    behavioral_score: float = 0.0
    
    privacy_weight: float
    behavioral_weight: float
    
    combined_score: float
    risk_category: str
    
    risk_factors: List[str] = []
    explanation: List[str] = []
    
    is_partial_assessment: bool = False
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
