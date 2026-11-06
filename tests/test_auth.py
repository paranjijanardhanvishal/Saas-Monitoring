"""Authentication, session, consent and cookie/CSRF integration tests."""

import pytest

from conftest import TEST_PASSWORD, create_device, create_user, csrf_headers, login


@pytest.mark.asyncio
async def test_public_registration_is_forbidden(client, db):
    payload = {
        "user_id": "new-user",
        "email": "new@example.com",
        "password": TEST_PASSWORD,
    }
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_cannot_register_users(client, db):
    await create_user("plain-user")
    token = (await login(client, "plain-user"))["access_token"]
    response = await client.post(
        "/api/auth/register",
        json={"user_id": "sneaky", "email": "s@example.com", "password": TEST_PASSWORD},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_register_and_duplicate_email_is_rejected(client, db):
    await create_user("admin-user", role="ADMIN")
    admin_token = (await login(client, "admin-user"))["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    created = await client.post(
        "/api/auth/register",
        json={
            "user_id": "created-user",
            "email": "created@example.com",
            "password": TEST_PASSWORD,
            "role": "USER",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["monitoring_enabled"] == "NOT_ASKED"
    assert "hashed_password" not in created.json()

    duplicate = await client.post(
        "/api/auth/register",
        json={
            "user_id": "created-user-2",
            "email": "created@example.com",
            "password": TEST_PASSWORD,
        },
        headers=headers,
    )
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_login_rejects_bad_password_and_unknown_user(client, db):
    await create_user("known-user")
    bad = await client.post(
        "/api/auth/login", data={"username": "known-user", "password": "WrongPassword999"}
    )
    assert bad.status_code == 401
    unknown = await client.post(
        "/api/auth/login", data={"username": "nobody", "password": TEST_PASSWORD}
    )
    assert unknown.status_code == 401


@pytest.mark.asyncio
async def test_login_sets_httponly_cookie_and_csrf_cookie(client, db):
    await create_user("cookie-user")
    response = await client.post(
        "/api/auth/login", data={"username": "cookie-user", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]

    set_cookies = response.headers.get_list("set-cookie")
    access = next(c for c in set_cookies if c.startswith("access_token="))
    csrf = next(c for c in set_cookies if c.startswith("csrf_token="))
    assert "HttpOnly" in access
    assert "HttpOnly" not in csrf
    assert client.cookies.get("access_token")
    assert client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_me_works_with_cookie_and_bearer(client, db):
    await create_user("me-user", display_name="Me User")
    token = (await login(client, "me-user"))["access_token"]

    via_cookie = await client.get("/api/auth/me")
    assert via_cookie.status_code == 200
    assert via_cookie.json()["user_id"] == "me-user"

    # A bearer token is preferred when both are present and must not require CSRF.
    via_bearer = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert via_bearer.status_code == 200


@pytest.mark.asyncio
async def test_cookie_mutation_requires_csrf_header(client, db):
    await create_user("csrf-user")
    await login(client, "csrf-user")

    without_csrf = await client.post(
        "/api/auth/consent", json={"monitoring_enabled": "ALLOWED"}
    )
    assert without_csrf.status_code == 403

    with_csrf = await client.post(
        "/api/auth/consent",
        json={"monitoring_enabled": "ALLOWED"},
        headers=csrf_headers(client),
    )
    assert with_csrf.status_code == 200
    assert with_csrf.json()["monitoring_enabled"] == "ALLOWED"


@pytest.mark.asyncio
async def test_logout_clears_cookies(client, db):
    await create_user("logout-user")
    await login(client, "logout-user")
    response = await client.post("/api/auth/logout", headers=csrf_headers(client))
    assert response.status_code == 200
    assert client.cookies.get("access_token") in (None, "")
    me = await client.get("/api/auth/me")
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_inactive_account_is_rejected(client, db):
    await create_user("disabled-user", is_active=False)
    response = await client.post(
        "/api/auth/login", data={"username": "disabled-user", "password": TEST_PASSWORD}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_consent_transitions_are_audited(client, db):
    await create_user("consent-user", consent="NOT_ASKED")
    token = (await login(client, "consent-user"))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    allowed = await client.post(
        "/api/auth/consent", json={"monitoring_enabled": "ALLOWED"}, headers=headers
    )
    assert allowed.status_code == 200
    assert allowed.json()["monitoring_enabled"] == "ALLOWED"

    declined = await client.post(
        "/api/auth/consent", json={"monitoring_enabled": "DECLINED"}, headers=headers
    )
    assert declined.status_code == 200
    assert declined.json()["monitoring_enabled"] == "DECLINED"

    assert await db.consent_history.count_documents({"user_id": "consent-user"}) == 2
    assert await db.audit_logs.count_documents(
        {"actor_id": "consent-user", "action": "consent.updated"}
    ) == 2


@pytest.mark.asyncio
async def test_withdrawing_consent_revokes_devices(client, db):
    await create_user("revoke-user", consent="ALLOWED")
    await create_device("revoke-user", device_id="device-revoke-01", token="dev_revoke_token")
    token = (await login(client, "revoke-user"))["access_token"]

    response = await client.post(
        "/api/auth/consent",
        json={"monitoring_enabled": "REVOKED"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    device = await db.devices.find_one({"device_id": "device-revoke-01"})
    assert device["status"] == "REVOKED"
    assert device["monitoring_enabled"] is False


@pytest.mark.asyncio
async def test_change_password_requires_current_password(client, db):
    await create_user("pw-user")
    token = (await login(client, "pw-user"))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    wrong = await client.post(
        "/api/auth/change-password",
        json={"current_password": "nope", "new_password": "AnotherStrongPass99"},
        headers=headers,
    )
    assert wrong.status_code == 400

    weak = await client.post(
        "/api/auth/change-password",
        json={"current_password": TEST_PASSWORD, "new_password": "short"},
        headers=headers,
    )
    assert weak.status_code == 400

    changed = await client.post(
        "/api/auth/change-password",
        json={"current_password": TEST_PASSWORD, "new_password": "AnotherStrongPass99"},
        headers=headers,
    )
    assert changed.status_code == 200

    old_login = await client.post(
        "/api/auth/login", data={"username": "pw-user", "password": TEST_PASSWORD}
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/auth/login", data={"username": "pw-user", "password": "AnotherStrongPass99"}
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_forgot_and_reset_password_workflow(client, db):
    await create_user("reset-user", email="reset-user@example.com")

    # 1. Unknown email still returns 200 without disclosing non-existence
    anon_resp = await client.post(
        "/api/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert anon_resp.status_code == 200
    assert "dispatched" in anon_resp.json()["message"]
    assert "dev_reset_link" not in anon_resp.json()

    # 2. Known user returns 200 and dev link in test environment
    user_resp = await client.post(
        "/api/auth/forgot-password",
        json={"email": "reset-user@example.com"},
    )
    assert user_resp.status_code == 200
    dev_link = user_resp.json().get("dev_reset_link")
    assert dev_link and "token=" in dev_link
    token = dev_link.split("token=")[1]

    # 3. Invalid token fails
    invalid_reset = await client.post(
        "/api/auth/reset-password",
        json={"token": "invalid-token-that-does-not-exist", "new_password": "BrandNewSecurePassword123"},
    )
    assert invalid_reset.status_code == 400

    # 4. Weak password fails
    weak_reset = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "short"},
    )
    assert weak_reset.status_code in (400, 422)

    # 5. Valid reset updates password
    valid_reset = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "BrandNewSecurePassword123"},
    )
    assert valid_reset.status_code == 200

    # 6. Token reuse fails
    reuse_reset = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "BrandNewSecurePassword123"},
    )
    assert reuse_reset.status_code == 400

    # 7. Old password no longer works, new password logs in
    old_login = await client.post(
        "/api/auth/login", data={"username": "reset-user", "password": TEST_PASSWORD}
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/auth/login", data={"username": "reset-user", "password": "BrandNewSecurePassword123"}
    )
    assert new_login.status_code == 200
