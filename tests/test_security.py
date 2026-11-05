"""Unit tests for password, JWT, token and rate-limit primitives."""

from datetime import timedelta

import jwt
import pytest

from app.core import security
from app.core.rate_limit import SlidingWindowLimiter


def test_password_hash_roundtrip():
    hashed = security.get_password_hash("CorrectHorseBattery42")
    assert hashed.startswith("$2")
    assert security.verify_password("CorrectHorseBattery42", hashed)
    assert not security.verify_password("WrongPassword123", hashed)


def test_password_policy_rejects_short_and_common():
    with pytest.raises(ValueError):
        security.validate_password_strength("short")
    with pytest.raises(ValueError):
        security.validate_password_strength("password1234")
    with pytest.raises(ValueError):
        security.validate_password_strength("a" * 73)


def test_verify_password_handles_garbage_hash():
    assert security.verify_password("anything", "not-a-bcrypt-hash") is False
    assert security.verify_password("", "") is False


def test_access_token_roundtrip():
    token = security.create_access_token("user-1", "USER")
    payload = security.decode_access_token(token)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "USER"
    assert payload["type"] == "access"


def test_expired_token_is_rejected():
    token = security.create_access_token(
        "user-1", "USER", expires_delta=timedelta(seconds=-10)
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(token)


def test_tampered_token_is_rejected():
    token = security.create_access_token("user-1", "USER")
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(token + "x")


def test_opaque_token_only_hash_is_deterministic():
    raw, digest, prefix = security.generate_opaque_token("dev_")
    assert raw.startswith("dev_")
    assert prefix == raw[:12]
    assert digest == security.hash_token(raw)
    assert security.hash_token(raw) != raw


def test_constant_time_compare():
    assert security.constant_time_compare("abc", "abc")
    assert not security.constant_time_compare("abc", "abd")
    assert not security.constant_time_compare("", "abc")


def test_sliding_window_limiter_blocks_after_max_events():
    limiter = SlidingWindowLimiter(max_events=2, window_seconds=60)
    assert not limiter.is_limited("k")
    limiter.record_failure("k")
    limiter.record_failure("k")
    assert limiter.is_limited("k")
    assert limiter.retry_after("k") > 0
    limiter.reset("k")
    assert not limiter.is_limited("k")
