from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


class ActionTypeEnum(str, Enum):
    LOG = "LOG"
    ALERT = "ALERT"
    WARN = "WARN"
    RESTRICT_USER = "RESTRICT_USER"
    REVOKE_DEVICES = "REVOKE_DEVICES"


class ResponseStatusEnum(str, Enum):
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    ALREADY_HANDLED = "ALREADY_HANDLED"
    ROLLED_BACK = "ROLLED_BACK"


ACTIVE_ACTIONS = {ActionTypeEnum.RESTRICT_USER, ActionTypeEnum.REVOKE_DEVICES}


class EnforcementRequest(BaseModel):
    risk_id: str = Field(min_length=1, max_length=128)
    # Administrators may override the recommended action. Destructive actions
    # additionally require an explicit confirmation flag.
    action: Optional[ActionTypeEnum] = None
    confirm: bool = False
    reason: Optional[str] = Field(default=None, max_length=500)


class EnforcementResponseModel(BaseModel):
    response_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    risk_id: str
    user_id: str
    event_id: Optional[str] = None

    risk_category: str
    action_taken: ActionTypeEnum
    response_status: ResponseStatusEnum
    reason: str

    actor_id: str
    confirmed: bool = False
    previous_enforcement_status: Optional[str] = None
    resulting_enforcement_status: Optional[str] = None
    revoked_devices: int = 0
    targets: List[str] = []
    integration_results: Dict[str, Any] = {}

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rolled_back_at: Optional[datetime] = None
    rollback_by: Optional[str] = None
    rollback_reason: Optional[str] = None


class EnforcementRecommendation(BaseModel):
    risk_id: str
    user_id: str
    event_id: Optional[str] = None
    risk_category: str
    combined_score: Optional[float] = None
    recommended_action: ActionTypeEnum
    requires_confirmation: bool
    current_enforcement_status: Optional[str] = None
    active_devices: int = 0
    existing_response_id: Optional[str] = None


class RollbackRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
