from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

AlertSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
AlertStatus = Literal["OPEN", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "DISMISSED"]


class AlertBase(BaseModel):
    severity: AlertSeverity
    title: str = Field(max_length=200)
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    saas_app: Optional[str] = None
    resource_id: Optional[str] = None
    reason: str = Field(max_length=2000)
    privacy_signal: Optional[float] = None
    behavior_signal: Optional[float] = None
    endpoint_signal: Optional[float] = None
    risk_score: Optional[float] = None
    status: AlertStatus = "OPEN"
    source: str = "risk_engine"
    event_id: Optional[str] = None
    risk_id: Optional[str] = None
    dedupe_key: Optional[str] = None
    evidence: List[Dict[str, Any]] = []
    history: List[Dict[str, Any]] = []


class AlertCreate(AlertBase):
    # Manual alert creation is an administrative action.
    pass


class AlertResponse(AlertBase):
    id: str
    timestamp: datetime
    updated_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


class AlertStatusUpdate(BaseModel):
    status: AlertStatus
    note: Optional[str] = Field(default=None, max_length=1000)


class AlertNote(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
