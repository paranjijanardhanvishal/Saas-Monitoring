from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

DeviceStatus = Literal["ACTIVE", "REVOKED"]


class DeviceModel(BaseModel):
    device_id: str
    user_id: str
    hostname: str = ""
    os_version: str = ""
    agent_version: str = ""
    status: DeviceStatus = "ACTIVE"
    monitoring_enabled: bool = False
    enrolled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None


class DeviceResponse(BaseModel):
    device_id: str
    user_id: str
    hostname: str = ""
    os_version: str = ""
    agent_version: str = ""
    status: DeviceStatus = "ACTIVE"
    monitoring_enabled: bool = False
    enrolled_at: datetime
    last_heartbeat: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class EnrollmentRequest(BaseModel):
    enrollment_token: str = Field(min_length=16, max_length=256)
    device_id: str = Field(min_length=8, max_length=128)
    hostname: str = Field(max_length=255)
    os_version: str = Field(max_length=255)
    agent_version: str = Field(max_length=32)


class EnrollmentResponse(BaseModel):
    device_id: str
    device_token: str
    user_id: str
    expires_at: Optional[datetime] = None
    heartbeat_interval: int = 60


class EnrollmentTokenResponse(BaseModel):
    enrollment_token: str
    expires_at: datetime
    user_id: str


class HeartbeatRequest(BaseModel):
    model_config = {"extra": "forbid"}

    hostname: str = Field(max_length=255)
    os_version: str = Field(max_length=255)
    agent_version: str = Field(max_length=32)
    monitoring_active: bool = True


class HeartbeatResponse(BaseModel):
    status: str
    message: str
    monitoring_enabled: bool
    server_time: datetime
    collection_interval_seconds: int = 60
