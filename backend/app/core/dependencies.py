import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import constant_time_compare, decode_access_token
from app.database.mongodb import get_database
from app.models.user import UserModel

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"


def _extract_user_token(request: Request, bearer_token: Optional[str]) -> tuple[Optional[str], bool]:
    """Return (token, authenticated_via_cookie)."""
    if bearer_token:
        return bearer_token, False
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token, True
    return None, False


async def get_current_user(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
) -> UserModel:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token, via_cookie = _extract_user_token(request, bearer_token)
    if not token:
        raise credentials_exception

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception

    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    user_dict = await db.users.find_one({"user_id": user_id})
    if user_dict is None:
        raise credentials_exception
    user = UserModel(**user_dict)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # CSRF protection for cookie-authenticated state-changing requests.
    if via_cookie and request.method in UNSAFE_METHODS:
        cookie_token = request.cookies.get(CSRF_COOKIE)
        header_token = request.headers.get(CSRF_HEADER)
        if not cookie_token or not header_token or not constant_time_compare(cookie_token, header_token):
            raise HTTPException(status_code=403, detail="CSRF validation failed")

    return user


async def get_current_active_user(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    return current_user


async def get_current_admin_user(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Administrator privileges required")
    return current_user


def ensure_self_or_admin(current_user: UserModel, user_id: Optional[str]) -> None:
    if current_user.role == "ADMIN":
        return
    if not user_id or current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied for this user")


@dataclass
class DevicePrincipal:
    device: dict
    user: UserModel

    @property
    def device_id(self) -> str:
        return self.device["device_id"]

    @property
    def user_id(self) -> str:
        return self.user.user_id


def _hash_device_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _device_principal(token: str) -> DevicePrincipal:
    if not token:
        raise HTTPException(status_code=401, detail="Device credential required")
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    device = await db.devices.find_one({"token_hash": _hash_device_token(token)})
    if not device:
        raise HTTPException(status_code=401, detail="Invalid device credential")
    if device.get("status") != "ACTIVE":
        raise HTTPException(status_code=403, detail="Device enrollment is revoked")

    user_dict = await db.users.find_one({"user_id": device.get("user_id")})
    if not user_dict:
        raise HTTPException(status_code=403, detail="Device owner no longer exists")
    user = UserModel(**user_dict)
    if not user.is_active or user.enforcement_status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Device owner account is restricted")
    return DevicePrincipal(device=device, user=user)


async def get_current_device(
    x_device_token: Optional[str] = Header(default=None, alias="X-Device-Token"),
) -> DevicePrincipal:
    """Authenticate an enrolled agent and require active monitoring consent."""
    principal = await _device_principal(x_device_token or "")
    if principal.user.monitoring_enabled != "ALLOWED":
        raise HTTPException(
            status_code=403,
            detail={
                "status": "consent_required",
                "message": "Monitoring consent is not granted for this user.",
            },
        )
    return principal


async def get_device_for_heartbeat(
    x_device_token: Optional[str] = Header(default=None, alias="X-Device-Token"),
) -> DevicePrincipal:
    # Consent is evaluated in the handler so the agent receives an explicit
    # disabled response rather than a generic credential error.
    return await _device_principal(x_device_token or "")


async def require_ingestion_key(x_ingestion_key: Optional[str] = Header(default=None, alias="X-Ingestion-Key")) -> None:
    from app.core.config import settings

    if not settings.INGESTION_API_KEY:
        raise HTTPException(status_code=503, detail="SaaS proxy ingestion is not configured")
    if not x_ingestion_key or not constant_time_compare(x_ingestion_key, settings.INGESTION_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid ingestion credential")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
