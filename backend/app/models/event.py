from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class ActionEnum(str, Enum):
    ACCESS = "ACCESS"
    DOWNLOAD = "DOWNLOAD"
    UPLOAD = "UPLOAD"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    SHARE = "SHARE"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"
    EXECUTE = "EXECUTE"
    SESSION = "SESSION"
    SYSTEM = "SYSTEM"


class EventModel(BaseModel):
    """Canonical event stored in MongoDB.

    Endpoint clients never control ``user_id``, ``device_id``, ``source``,
    ``ingestion_timestamp`` or risk fields; the ingestion API overwrites them
    with values derived from the authenticated device.
    """

    event_id: str = Field(min_length=8, max_length=128)
    event_type: str = Field(default="saas.activity", max_length=64)
    schema_version: str = "1.0"

    user_id: Optional[str] = None
    device_id: Optional[str] = None
    session_id: Optional[str] = None
    source: str = "saas_proxy"  # saas_proxy | endpoint_agent | offline_analysis | privacy_scan

    saas_app: str = "unknown_saas"
    action: ActionEnum
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None

    application: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ingestion_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    device_info: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        # Dotted lowercase namespace, e.g. process.started, file.deleted.
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
        if not value or any(ch not in allowed for ch in value):
            raise ValueError("event_type must be a lowercase dotted identifier")
        return value


class EndpointEventIn(BaseModel):
    """Payload accepted from an enrolled endpoint agent.

    Unknown fields are forbidden so a client cannot inject trusted fields.
    """

    model_config = {"extra": "forbid"}

    event_id: str = Field(min_length=8, max_length=128)
    event_type: str = Field(max_length=64)
    timestamp: datetime
    action: ActionEnum
    resource_id: Optional[str] = Field(default=None, max_length=256)
    resource_name: Optional[str] = Field(default=None, max_length=256)
    application: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = Field(default=None, max_length=128)
