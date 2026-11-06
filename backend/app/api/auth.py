import hashlib
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.dependencies import get_current_admin_user, get_current_user
from app.core.rate_limit import forgot_password_limiter, login_limiter
from app.core.security import (
    create_access_token,
    get_password_hash,
    validate_password_strength,
    verify_password,
)
from app.database.mongodb import get_database
from app.models.user import (
    ConsentUpdate,
    ForgotPasswordRequest,
    ResetPasswordRequest,
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
        {"user_id": current_user.user_id}, {"$set": {"hashed_password": hashed, "must_change_password": False}}
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


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
):
    """Initiate a secure password reset.
    Enumeration-safe: always returns 200 whether email exists or not.
    """
    client_ip = request.client.host if request.client else "unknown"
    limiter_key = f"{client_ip}:{str(payload.email).lower().strip()}"
    if forgot_password_limiter.is_limited(limiter_key):
        raise HTTPException(
            status_code=429,
            detail="Too many password reset requests. Please try again later.",
        )
    forgot_password_limiter.record_failure(limiter_key)

    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    email = str(payload.email).lower().strip()
    user = await db.users.find_one({"email": email})

    dev_reset_link = None
    if user and user.get("is_active", True):
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=15)

        # Invalidate any previous unexpired reset tokens for this user
        await db.password_resets.update_many(
            {"user_id": user["user_id"], "used": False},
            {"$set": {"used": True, "invalidated_at": now}},
        )

        # Store only the SHA-256 hash of the token
        await db.password_resets.insert_one({
            "token_hash": token_hash,
            "user_id": user["user_id"],
            "email": email,
            "expires_at": expires_at,
            "used": False,
            "created_at": now,
        })

        await record_audit(
            db,
            user["user_id"],
            user.get("role", "USER"),
            "auth.password_reset_requested",
            "user",
            user["user_id"],
            "success",
            client_ip=client_ip,
        )

        frontend_origin = (settings.FRONTEND_URL.split(",")[0] if settings.FRONTEND_URL else "http://localhost:5173").rstrip("/")
        reset_link = f"{frontend_origin}/reset-password?token={raw_token}"

        if getattr(settings, "SMTP_HOST", ""):
            try:
                import email.message
                msg = email.message.EmailMessage()
                msg["Subject"] = "SaaS Security Monitor - Password Reset Request"
                msg["From"] = settings.SMTP_FROM
                msg["To"] = email
                msg.set_content(
                    f"Hello,\n\nA password reset was requested for your account ({user['user_id']}).\n"
                    f"Use the following link to reset your password:\n{reset_link}\n\n"
                    f"This link will expire in 15 minutes. If you did not request this, please ignore this email.\n"
                )
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                    server.starttls()
                    if settings.SMTP_USER and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)
            except Exception as mail_exc:
                logger.warning("SMTP delivery failed for password reset: %s", mail_exc)

        if getattr(settings, "APP_ENV", "development") != "production":
            dev_reset_link = reset_link

    response_data = {
        "status": "success",
        "message": "If an account exists with that email address, a password reset link has been dispatched.",
    }
    if dev_reset_link:
        response_data["dev_reset_link"] = dev_reset_link
    return response_data


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
):
    """Validate single-use token and update password."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    token_hash = hashlib.sha256(payload.token.strip().encode("utf-8")).hexdigest()
    reset_doc = await db.password_resets.find_one({"token_hash": token_hash})
    if not reset_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token.")

    if reset_doc.get("used", False):
        raise HTTPException(status_code=400, detail="This reset token has already been used.")

    now = datetime.now(timezone.utc)
    expires_at = reset_doc["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status_code=400, detail="This password reset token has expired.")

    try:
        validate_password_strength(payload.new_password)
        hashed = get_password_hash(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user_id = reset_doc["user_id"]
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"hashed_password": hashed, "must_change_password": False}},
    )

    # Invalidate token immediately to prevent reuse
    await db.password_resets.update_one(
        {"_id": reset_doc["_id"]},
        {"$set": {"used": True, "used_at": now}},
    )

    await record_audit(
        db,
        user_id,
        "USER",
        "auth.password_reset_completed",
        "user",
        user_id,
        "success",
        client_ip=request.client.host if request.client else None,
    )
    return {
        "status": "success",
        "message": "Your password has been reset successfully. You can now log in with your new password.",
    }
