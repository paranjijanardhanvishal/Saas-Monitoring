from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

IncidentSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
IncidentStatus = Literal["OPEN", "INVESTIGATING", "CONTAINED", "RESOLVED", "DISMISSED"]


class IncidentBase(BaseModel):
    title: str = Field(max_length=200)
    severity: IncidentSeverity
    status: IncidentStatus = "OPEN"
    user_id: Optional[str] = None
    saas_app: Optional[str] = None
    resource_id: Optional[str] = None
    reason: str = Field(max_length=4000)
    risk_score: Optional[float] = None
    related_alerts: List[str] = []
    related_events: List[str] = []
    assigned_to: Optional[str] = None
    evidence: List[Dict[str, Any]] = []
    notes: List[Dict[str, Any]] = []


class IncidentCreate(IncidentBase):
    pass


class IncidentResponse(IncidentBase):
    id: str
    created_time: datetime
    updated_at: Optional[datetime] = None
    response_history: List[str] = []
    history: List[Dict[str, Any]] = []


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus
    note: Optional[str] = Field(default=None, max_length=2000)


class IncidentAssign(BaseModel):
    assigned_to: str = Field(min_length=1, max_length=64)


class IncidentNote(BaseModel):
    note: str = Field(min_length=1, max_length=4000)
