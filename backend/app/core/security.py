"""Password hashing, JWT creation/validation and opaque token helpers.

Passwords are hashed with bcrypt directly. passlib is deliberately not used:
passlib 1.7.4 is incompatible with bcrypt >= 4.1 (the login page previously
failed because password hashing raised an exception at runtime).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
BCRYPT_MAX_BYTES = 72


def _resolve_secret_key() -> str:
    configured = (settings.JWT_SECRET_KEY or "").strip()
    if len(configured) >= 32:
        return configured
    if settings.APP_ENV.lower() == "production":
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a random value of at least 32 characters in production."
        )
    # Development / test fallback. Tokens are invalidated when the process
    # restarts. Set JWT_SECRET_KEY in .env for a stable local experience.
    logger.warning(
        "JWT_SECRET_KEY is not configured; using an ephemeral development key. "
        "Set JWT_SECRET_KEY in .env for persistent sessions."
    )
    return secrets.token_urlsafe(48)


SECRET_KEY = _resolve_secret_key()


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def validate_password_strength(password: str) -> None:
    """Raise ValueError when a password does not meet the minimum policy."""
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("Password must be at least 12 characters long.")
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError("Password must be at most 72 bytes when UTF-8 encoded.")
    if password.lower() in {"password1234", "administrator", "changeme1234"}:
        raise ValueError("Password is too common.")


def get_password_hash(password: str, validate: bool = True) -> str:
    if validate:
        validate_password_strength(password)
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode("ascii"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str | Any,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": str(subject),
        "role": role,
        "type": "access",
        "iat": now,
        "nbf": now,
        "exp": expire,
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub", "type"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload


def generate_opaque_token(prefix: str = "") -> tuple[str, str, str]:
    """Return (raw_token, token_hash, token_prefix).

    Only the hash is persisted so a database leak does not expose usable
    agent credentials. The raw token is returned to the caller once.
    """
    raw = f"{prefix}{secrets.token_urlsafe(32)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, digest, raw[:12]


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    return secrets.compare_digest(a or "", b or "")
