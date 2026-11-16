"""Targeted unit tests for Users directory authorization, email masking, and mutation policies."""

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock

from app.api.users import UserDirectoryEntry, _mask_email, _deny_restricted_directory_details
from app.core.dependencies import _enforce_role_mutation_policy, ensure_self_or_admin
from app.models.user import UserModel, UserResponse


def test_mask_email():
    assert _mask_email("visitor@visitor.com") == "v******@visitor.com"
    assert _mask_email("vishal@gmail.com") == "v*****@gmail.com"
    assert _mask_email("admin@admin.com") == "a****@admin.com"
    assert _mask_email("a@b.com") == "a@b.com"
    assert _mask_email(None) is None
    assert _mask_email("") is None
    assert _mask_email("invalid") == "***"


def test_user_directory_entry_schema():
    entry = UserDirectoryEntry(
        user_id="u123",
        display_name="Test User",
        email="t*****@example.com",
        role="VISITOR",
        business_role="DEVELOPER",
    )
    dump = entry.model_dump()
    assert set(dump.keys()) == {"user_id", "display_name", "email", "role", "business_role"}
    assert "monitoring_enabled" not in dump
    assert "enforcement_status" not in dump
    assert "created_at" not in dump
    assert "last_login_at" not in dump
    assert "hashed_password" not in dump


def test_deny_restricted_directory_details():
    visitor = UserModel(user_id="v1", role="VISITOR")
    user = UserModel(user_id="u1", role="USER")
    admin = UserModel(user_id="a1", role="ADMIN")
    editor = UserModel(user_id="e1", role="EDITOR")

    # VISITOR and USER are denied with 403
    with pytest.raises(HTTPException) as exc_v:
        _deny_restricted_directory_details(visitor)
    assert exc_v.value.status_code == 403

    with pytest.raises(HTTPException) as exc_u:
        _deny_restricted_directory_details(user)
    assert exc_u.value.status_code == 403

    # ADMIN and EDITOR are permitted
    _deny_restricted_directory_details(admin)
    _deny_restricted_directory_details(editor)


def test_ensure_self_or_admin():
    admin = UserModel(user_id="admin-1", role="ADMIN")
    user = UserModel(user_id="user-1", role="USER")

    # ADMIN can access any user_id
    ensure_self_or_admin(admin, "user-1")
    ensure_self_or_admin(admin, "other-user")

    # USER can only access own user_id
    ensure_self_or_admin(user, "user-1")
    with pytest.raises(HTTPException) as exc_diff:
        ensure_self_or_admin(user, "other-user")
    assert exc_diff.value.status_code == 403


def test_enforce_role_mutation_policy():
    visitor = UserModel(user_id="v1", role="VISITOR")
    user = UserModel(user_id="u1", role="USER")
    admin = UserModel(user_id="a1", role="ADMIN")

    def mock_req(method, path):
        req = MagicMock()
        req.method = method
        req.scope = {"route": MagicMock(path=path)}
        req.url.path = path
        return req

    # GET requests are not blocked by mutation policy
    _enforce_role_mutation_policy(mock_req("GET", "/api/users"), visitor)
    _enforce_role_mutation_policy(mock_req("GET", "/api/events"), user)
    _enforce_role_mutation_policy(mock_req("GET", "/api/users"), admin)

    # VISITOR mutations are blocked with 403 everywhere except logout
    endpoints = [
        "/api/users",
        "/api/alerts/123/status",
        "/api/incidents",
        "/api/enforcement/respond",
        "/api/files/sync",
        "/api/agent/enrollment-token",
        "/api/auth/consent",
        "/api/auth/change-password",
    ]
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        for ep in endpoints:
            with pytest.raises(HTTPException) as exc:
                _enforce_role_mutation_policy(mock_req(method, ep), visitor)
            assert exc.value.status_code == 403

    # VISITOR logout is permitted
    _enforce_role_mutation_policy(mock_req("POST", "/api/auth/logout"), visitor)

    # ADMIN and USER are not blocked by this blanket visitor policy (route-level guards apply to USER)
    _enforce_role_mutation_policy(mock_req("POST", "/api/users"), admin)
    _enforce_role_mutation_policy(mock_req("POST", "/api/events"), user)


def test_user_response_fields():
    # UserResponse includes directory columns needed for USER read-only view
    from datetime import datetime, timezone
    resp = UserResponse(
        user_id="user1",
        email="user1@example.com",
        display_name="User One",
        role="USER",
        business_role="DEVELOPER",
        monitoring_enabled="ALLOWED",
        enforcement_status="ACTIVE",
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    d = resp.model_dump()
    assert d["user_id"] == "user1"
    assert d["email"] == "user1@example.com"
    assert d["display_name"] == "User One"
    assert d["role"] == "USER"
    assert d["business_role"] == "DEVELOPER"
    assert d["monitoring_enabled"] == "ALLOWED"
    assert d["enforcement_status"] == "ACTIVE"
    assert d["is_active"] is True
    assert "hashed_password" not in d
