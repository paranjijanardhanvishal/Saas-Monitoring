from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class IncidentBase(BaseModel):
    title: str
    severity: str # LOW, MEDIUM, HIGH, CRITICAL
    status: str = "OPEN" # OPEN, INVESTIGATING, CONTAINED, RESOLVED, DISMISSED
    user_id: Optional[str] = None
    saas_app: Optional[str] = None
    resource_id: Optional[str] = None
    reason: str
    risk_score: Optional[float] = None
    related_alerts: List[str] = []
    related_events: List[str] = []

class IncidentCreate(IncidentBase):
    pass

class IncidentInDB(IncidentBase):
    id: str = Field(alias="_id")
    created_time: datetime = Field(default_factory=datetime.utcnow)
    response_history: List[str] = []

class IncidentResponse(IncidentBase):
    id: str
    created_time: datetime
    response_history: List[str]
