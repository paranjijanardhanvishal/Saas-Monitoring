from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum
import uuid

class ActionTypeEnum(str, Enum):
    LOG = "LOG"
    ALERT = "ALERT"
    WARN = "WARN"
    SIMULATED_BLOCK = "SIMULATED_BLOCK"

class ResponseStatusEnum(str, Enum):
    SIMULATED = "SIMULATED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    ALREADY_HANDLED = "ALREADY_HANDLED"

class EnforcementRequest(BaseModel):
    risk_id: str

class EnforcementResponseModel(BaseModel):
    response_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    risk_id: str
    user_id: str
    event_id: str
    
    risk_category: str
    action_taken: ActionTypeEnum
    response_status: ResponseStatusEnum
    reason: str
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
