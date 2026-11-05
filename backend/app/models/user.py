from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

Role = Literal["ADMIN", "USER"]
BusinessRole = Literal["GENERAL", "DEVELOPER", "HR", "FINANCE"]
ConsentState = Literal["NOT_ASKED", "ALLOWED", "DECLINED", "REVOKED"]
EnforcementStatus = Literal["ACTIVE", "RESTRICTED"]


class UserCreate(BaseModel):
    user_id: str = Field(min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(min_length=12, max_length=72)
    display_name: Optional[str] = Field(default=None, max_length=120)
    role: Role = "USER"
    business_role: BusinessRole = "GENERAL"

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        if not value.replace("-", "").replace("_", "").replace(".", "").isalnum():
            raise ValueError("user_id may only contain letters, digits, '-', '_' and '.'")
        return value


class UserModel(BaseModel):
    user_id: str
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    role: Role = "USER"
    business_role: BusinessRole = "GENERAL"
    monitoring_enabled: ConsentState = "NOT_ASKED"
    hashed_password: str = ""
    source: str = "local"
    is_active: bool = True
    enforcement_status: EnforcementStatus = "ACTIVE"
    must_change_password: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    consent_updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


class UserResponse(BaseModel):
    user_id: str
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    role: Role = "USER"
    business_role: BusinessRole = "GENERAL"
    monitoring_enabled: ConsentState = "NOT_ASKED"
    is_active: bool = True
    enforcement_status: EnforcementStatus = "ACTIVE"
    must_change_password: bool = False
    created_at: datetime
    consent_updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    source: str = "local"


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 0


class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None


class ConsentUpdate(BaseModel):
    monitoring_enabled: ConsentState

    @field_validator("monitoring_enabled")
    @classmethod
    def validate_state(cls, value: str) -> str:
        # NOT_ASKED is an internal initial state and may not be selected by a user.
        if value == "NOT_ASKED":
            raise ValueError("monitoring_enabled must be ALLOWED, DECLINED or REVOKED")
        return value


class BusinessRoleUpdate(BaseModel):
    business_role: BusinessRole
