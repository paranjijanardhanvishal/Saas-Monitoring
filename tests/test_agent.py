"""Endpoint agent enrollment, device auth, ingestion and revocation tests."""

from datetime import datetime, timezone

import pytest

from conftest import create_device, create_user, login


async def _issue_token(client, token: str, user_id: str | None = None) -> str:
    url = "/api/agent/enrollment-token"
    if user_id:
        url += f"?user_id={user_id}"
    response = await client.post(url, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    return response.json()["enrollment_token"]


async def _enroll(client, enrollment_token: str, device_id: str = "device-agent-0001") -> str:
    response = await client.post(
        "/api/agent/enroll",
        json={
            "enrollment_token": enrollment_token,
            "device_id": device_id,
            "hostname": "WORKSTATION-01",
            "os_version": "Windows 11 Pro",
            "agent_version": "2.0.0",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["device_token"]


def _endpoint_event(event_id: str = "endpoint-event-0001", **overrides) -> dict:
    payload = {
        "event_id": event_id,
        "event_type": "process.started",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "EXECUTE",
        "resource_name": "notepad.exe",
        "application": {"name": "Notepad", "pid": 1234},
        "metadata": {"path": "C:/Windows/System32/notepad.exe"},
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_enrollment_requires_consent_and_authentication(client, db):
    await create_user("no-consent", consent="NOT_ASKED")
    token = (await login(client, "no-consent"))["access_token"]
    response = await client.post(
        "/api/agent/enrollment-token", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 409

    # Clear the login cookies so this request is genuinely anonymous.
    client.cookies.clear()
    anonymous = await client.post("/api/agent/enrollment-token")
    assert anonymous.status_code == 401


@pytest.mark.asyncio
async def test_only_self_or_admin_can_issue_enrollment_tokens(client, db):
    await create_user("enroll-user", consent="ALLOWED")
    await create_user("enroll-other", consent="ALLOWED")
    await create_user("enroll-admin", role="ADMIN", consent="ALLOWED")
    user_token = (await login(client, "enroll-user"))["access_token"]
    admin_token = (await login(client, "enroll-admin"))["access_token"]

    denied = await client.post(
        "/api/agent/enrollment-token?user_id=enroll-other",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert denied.status_code == 403

    allowed = await client.post(
        "/api/agent/enrollment-token?user_id=enroll-other",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["user_id"] == "enroll-other"


@pytest.mark.asyncio
async def test_full_enrollment_heartbeat_and_ingestion_flow(client, db):
    await create_user("agent-user", consent="ALLOWED")
    token = (await login(client, "agent-user"))["access_token"]
    enrollment = await _issue_token(client, token)
    device_token = await _enroll(client, enrollment)

    # Only a hash of the device token is stored.
    device = await db.devices.find_one({"device_id": "device-agent-0001"})
    assert device["status"] == "ACTIVE"
    assert device["token_hash"] != device_token
    assert device_token not in str(device)

    headers = {"X-Device-Token": device_token}
    heartbeat = await client.post(
        "/api/agent/heartbeat",
        json={
            "hostname": "WORKSTATION-01",
            "os_version": "Windows 11 Pro",
            "agent_version": "2.0.0",
        },
        headers=headers,
    )
    assert heartbeat.status_code == 200, heartbeat.text
    assert heartbeat.json()["status"] == "active"
    assert heartbeat.json()["monitoring_enabled"] is True

    ingest = await client.post(
        "/api/agent/events", json=[_endpoint_event()], headers=headers
    )
    assert ingest.status_code == 200, ingest.text
    assert ingest.json()["accepted"] == 1
    assert ingest.json()["rejected"] == []

    stored = await db.events.find_one({"event_id": "endpoint-event-0001"})
    assert stored["user_id"] == "agent-user"
    assert stored["device_id"] == "device-agent-0001"
    assert stored["source"] == "endpoint_agent"

    # The device owner sees their event through the read API.
    read = await client.get(
        f"/api/events/{stored['event_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert read.status_code == 200


@pytest.mark.asyncio
async def test_enrollment_token_is_single_use(client, db):
    await create_user("single-user", consent="ALLOWED")
    token = (await login(client, "single-user"))["access_token"]
    enrollment = await _issue_token(client, token)
    await _enroll(client, enrollment, device_id="device-single-01")

    second = await client.post(
        "/api/agent/enroll",
        json={
            "enrollment_token": enrollment,
            "device_id": "device-single-02",
            "hostname": "SECOND",
            "os_version": "Windows 11",
            "agent_version": "2.0.0",
        },
    )
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_device_token_is_rejected_without_active_enrollment(client, db):
    response = await client.post(
        "/api/agent/heartbeat",
        json={"hostname": "h", "os_version": "o", "agent_version": "2.0.0"},
        headers={"X-Device-Token": "not-a-real-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_agent_cannot_forge_identity_fields(client, db):
    await create_user("forge-user", consent="ALLOWED")
    token = (await login(client, "forge-user"))["access_token"]
    device_token = await _enroll(client, await _issue_token(client, token))

    forged = _endpoint_event(user_id="victim", source="saas_proxy")
    response = await client.post(
        "/api/agent/events", json=[forged], headers={"X-Device-Token": device_token}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unsupported_event_types_are_rejected_per_item(client, db):
    await create_user("unsupported-user", consent="ALLOWED")
    token = (await login(client, "unsupported-user"))["access_token"]
    device_token = await _enroll(client, await _issue_token(client, token), device_id="device-unsup-01")

    response = await client.post(
        "/api/agent/events",
        json=[_endpoint_event("unsupported-1", event_type="keystroke.captured")],
        headers={"X-Device-Token": device_token},
    )
    assert response.status_code == 200
    assert response.json()["accepted"] == 0
    assert response.json()["rejected"][0]["reason"] == "unsupported event_type"


@pytest.mark.asyncio
async def test_revoked_device_cannot_submit(client, db):
    await create_user("revoked-user", consent="ALLOWED")
    await create_user("revoked-admin", role="ADMIN")
    await create_device("revoked-user", device_id="device-revoked-01", token="dev_revoked_token")
    admin = {"Authorization": f"Bearer {(await login(client, 'revoked-admin'))['access_token']}"}

    revoke = await client.post(
        "/api/agent/devices/device-revoked-01/revoke?reason=administrative",
        headers=admin,
    )
    assert revoke.status_code == 200

    denied = await client.post(
        "/api/agent/heartbeat",
        json={"hostname": "h", "os_version": "o", "agent_version": "2.0.0"},
        headers={"X-Device-Token": "dev_revoked_token"},
    )
    assert denied.status_code == 403

    devices = await client.get("/api/agent/devices", headers=admin)
    assert devices.status_code == 200
    assert devices.json()[0]["status"] == "REVOKED"


@pytest.mark.asyncio
async def test_withdrawn_consent_pauses_heartbeat_and_blocks_ingestion(client, db):
    await create_user("paused-user", consent="ALLOWED")
    await create_device("paused-user", device_id="device-paused-01", token="dev_paused_token")
    token = (await login(client, "paused-user"))["access_token"]

    await client.post(
        "/api/auth/consent",
        json={"monitoring_enabled": "DECLINED"},
        headers={"Authorization": f"Bearer {token}"},
    )

    heartbeat = await client.post(
        "/api/agent/heartbeat",
        json={"hostname": "h", "os_version": "o", "agent_version": "2.0.0"},
        headers={"X-Device-Token": "dev_paused_token"},
    )
    # Consent withdrawal revokes the device, so the credential is no longer valid.
    assert heartbeat.status_code == 403

    ingest = await client.post(
        "/api/agent/events",
        json=[_endpoint_event()],
        headers={"X-Device-Token": "dev_paused_token"},
    )
    assert ingest.status_code == 403


@pytest.mark.asyncio
async def test_device_listing_is_admin_only(client, db):
    await create_user("dev-list-user", consent="ALLOWED")
    token = (await login(client, "dev-list-user"))["access_token"]
    response = await client.get(
        "/api/agent/devices", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
