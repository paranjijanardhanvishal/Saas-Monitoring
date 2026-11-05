import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.dependencies import get_current_admin_user, get_current_user
from app.core.rate_limit import login_limiter
from app.core.security import (
    create_access_token,
    get_password_hash,
    validate_password_strength,
    verify_password,
)
from app.database.mongodb import get_database
from app.models.user import (
    ConsentUpdate,
    Token,
    UserCreate,
    UserModel,
    UserResponse,
)
from app.services.audit import record_audit
from app.services.devices import revoke_all_user_devices

logger = logging.getLogger(__name__)
router = APIRouter()

ACCESS_COOKIE = "access_token"
CSRF_COOKIE = "csrf_token"


def _set_auth_cookies(response: Response, token: str, csrf_token: str) -> None:
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=max_age,
        path="/",
    )
    # Readable by the SPA so it can echo the value in X-CSRF-Token. It is not
    # an authentication credential on its own.
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=max_age,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(user: UserCreate, current_admin=Depends(get_current_admin_user)):
    """Create a user. Registration is administrative; there is no public signup."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    email = str(user.email).lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already registered")
    if await db.users.find_one({"user_id": user.user_id}):
        raise HTTPException(status_code=409, detail="User ID already registered")

    try:
        hashed = get_password_hash(user.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user_model = UserModel(
        user_id=user.user_id,
        email=email,
        display_name=user.display_name or user.user_id,
        role=user.role,
        business_role=user.business_role,
        hashed_password=hashed,
        monitoring_enabled="NOT_ASKED",
    )
    await db.users.insert_one(user_model.model_dump())
    await record_audit(
        db,
        current_admin.user_id,
        current_admin.role,
        "user.created",
        "user",
        user_model.user_id,
        "success",
        metadata={"role": user_model.role, "business_role": user_model.business_role},
    )
    return UserResponse(**user_model.model_dump())


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    client_ip = request.client.host if request.client else "unknown"
    limiter_key = f"{client_ip}:{form_data.username.strip().lower()}"
    if login_limiter.is_limited(limiter_key):
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(login_limiter.retry_after(limiter_key))},
        )

    username = form_data.username.strip()
    user_dict = await db.users.find_one({"email": username.lower()})
    if not user_dict:
        user_dict = await db.users.find_one({"user_id": username})
    if not user_dict and username.lower() == "admin@admin.com":
        user_dict = await db.users.find_one({"user_id": "admin"})
    if not user_dict:
        login_limiter.record_failure(limiter_key)
        # Constant-ish response regardless of which factor failed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/user ID or password",
        )

    if not verify_password(form_data.password, user_dict.get("hashed_password", "")):
        login_limiter.record_failure(limiter_key)
        await record_audit(
            db,
            None,
            None,
            "auth.login_failed",
            "user",
            user_dict.get("user_id"),
            "denied",
            client_ip=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/user ID or password",
        )

    user = UserModel(**user_dict)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    login_limiter.reset(limiter_key)
    now = datetime.now(timezone.utc)
    await db.users.update_one({"user_id": user.user_id}, {"$set": {"last_login_at": now}})

    token = create_access_token(subject=user.user_id, role=user.role)
    import secrets

    _set_auth_cookies(response, token, secrets.token_urlsafe(32))
    await record_audit(
        db,
        user.user_id,
        user.role,
        "auth.login",
        "user",
        user.user_id,
        "success",
        client_ip=client_ip,
    )
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    response: Response,
    current_user: UserModel = Depends(get_current_user),
    request: Request = None,
):
    _clear_auth_cookies(response)
    db = get_database()
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "auth.logout",
        "user",
        current_user.user_id,
        "success",
        client_ip=request.client.host if request and request.client else None,
    )
    return {"status": "success"}


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: UserModel = Depends(get_current_user)):
    return UserResponse(**current_user.model_dump())


@router.post("/consent", response_model=UserResponse)
async def update_consent(
    consent: ConsentUpdate,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    previous = current_user.monitoring_enabled
    state = consent.monitoring_enabled
    now = datetime.now(timezone.utc)

    await db.users.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"monitoring_enabled": state, "consent_updated_at": now}},
    )
    await db.consent_history.insert_one(
        {
            "user_id": current_user.user_id,
            "previous_state": previous,
            "new_state": state,
            "timestamp": now,
            "client_ip": request.client.host if request.client else None,
        }
    )

    revoked = 0
    if state in {"DECLINED", "REVOKED"}:
        revoked = await revoke_all_user_devices(
            db, current_user.user_id, f"Consent state changed to {state}"
        )

    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "consent.updated",
        "user",
        current_user.user_id,
        "success",
        metadata={"previous": previous, "new": state, "devices_revoked": revoked},
        client_ip=request.client.host if request.client else None,
    )

    updated = await db.users.find_one({"user_id": current_user.user_id})
    return UserResponse(**updated)


@router.post("/change-password")
async def change_password(
    payload: dict,
    current_user: UserModel = Depends(get_current_user),
):
    current_password = payload.get("current_password", "")
    new_password = payload.get("new_password", "")
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    try:
        validate_password_strength(new_password)
        hashed = get_password_hash(new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.users.update_one(
        {"user_id": current_user.user_id}, {"$set": {"hashed_password": hashed}}
    )
    await record_audit(
        db,
        current_user.user_id,
        current_user.role,
        "auth.password_changed",
        "user",
        current_user.user_id,
        "success",
    )
    return {"status": "success"}
