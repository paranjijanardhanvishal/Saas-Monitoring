from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


class RiskAssessmentRequest(BaseModel):
    user_id: str
    event_id: str
    privacy_finding_id: Optional[str] = None
    anomaly_id: Optional[str] = None
    # When true the server derives endpoint and access-pattern signals from
    # persisted events. Clients cannot submit numeric signal values.
    include_context_signals: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskAssessmentModel(BaseModel):
    risk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    event_id: str
    privacy_finding_id: Optional[str] = None
    anomaly_id: Optional[str] = None

    privacy_score: float = 0.0
    behavioral_score: float = 0.0
    endpoint_score: float = 0.0
    access_score: float = 0.0

    privacy_weight: float
    behavioral_weight: float
    weights_used: Dict[str, float] = {}

    combined_score: float
    risk_category: str
    signal_confidence: float = 1.0
    signals_used: List[str] = []

    risk_factors: List[str] = []
    explanation: List[str] = []

    is_partial_assessment: bool = False
    saas_app: Optional[str] = None
    resource_id: Optional[str] = None

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
