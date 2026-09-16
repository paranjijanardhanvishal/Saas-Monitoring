from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class AlertBase(BaseModel):
    severity: str # LOW, MEDIUM, HIGH, CRITICAL
    title: str
    user_id: Optional[str] = None
    saas_app: Optional[str] = None
    resource_id: Optional[str] = None
    reason: str
    privacy_signal: Optional[float] = None
    behavior_signal: Optional[float] = None
    risk_score: Optional[float] = None
    status: str = "OPEN" # OPEN, INVESTIGATING, RESOLVED, DISMISSED

class AlertCreate(AlertBase):
    pass

class AlertInDB(AlertBase):
    id: str = Field(alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AlertResponse(AlertBase):
    id: str
    timestamp: datetime
