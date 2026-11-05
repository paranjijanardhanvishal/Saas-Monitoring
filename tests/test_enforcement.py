"""Administrator-confirmed enforcement and rollback tests."""

from datetime import datetime, timezone

import pytest

from conftest import create_device, create_user, login


async def _seed_risk(db, risk_id: str, user_id: str, category: str = "CRITICAL") -> dict:
    document = {
        "risk_id": risk_id,
        "user_id": user_id,
        "event_id": f"event-{risk_id}",
        "risk_category": category,
        "combined_score": 92.0,
        "privacy_score": 90.0,
        "behavioral_score": 70.0,
        "endpoint_score": 60.0,
        "access_score": 40.0,
        "explanation": ["Sensitive data exposure"],
        "risk_factors": ["HIGH_SENSITIVITY_PII"],
        "timestamp": datetime.now(timezone.utc),
    }
    await db.risk_assessments.insert_one(document)
    return document


@pytest.mark.asyncio
async def test_enforcement_is_admin_only(client, db):
    await create_user("enf-user")
    await create_user("enf-admin", role="ADMIN")
    await _seed_risk(db, "risk-enf-0001", "enf-user")
    user = {"Authorization": f"Bearer {(await login(client, 'enf-user'))['access_token']}"}
    admin = {"Authorization": f"Bearer {(await login(client, 'enf-admin'))['access_token']}"}

    assert (
        await client.post(
            "/api/enforcement/respond", json={"risk_id": "risk-enf-0001"}, headers=user
        )
    ).status_code == 403
    assert (
        await client.get("/api/enforcement/recommendation/risk-enf-0001", headers=user)
    ).status_code == 403

    recommendation = await client.get(
        "/api/enforcement/recommendation/risk-enf-0001", headers=admin
    )
    assert recommendation.status_code == 200
    assert recommendation.json()["recommended_action"] == "RESTRICT_USER"
    assert recommendation.json()["requires_confirmation"] is True


@pytest.mark.asyncio
async def test_active_action_requires_explicit_confirmation(client, db):
    await create_user("enf-target", consent="ALLOWED")
    await create_user("enf-admin2", role="ADMIN")
    await _seed_risk(db, "risk-enf-0002", "enf-target")
    admin = {"Authorization": f"Bearer {(await login(client, 'enf-admin2'))['access_token']}"}

    unconfirmed = await client.post(
        "/api/enforcement/respond",
        json={"risk_id": "risk-enf-0002", "action": "RESTRICT_USER", "confirm": False},
        headers=admin,
    )
    assert unconfirmed.status_code == 409

    user = await db.users.find_one({"user_id": "enf-target"})
    assert user["enforcement_status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_restrict_user_revokes_devices_and_rollback_restores(client, db):
    await create_user("enf-restrict", consent="ALLOWED")
    await create_user("enf-admin3", role="ADMIN")
    await create_device("enf-restrict", device_id="device-enf-01", token="dev_enf_token")
    await _seed_risk(db, "risk-enf-0003", "enf-restrict")
    admin_headers = {
        "Authorization": f"Bearer {(await login(client, 'enf-admin3'))['access_token']}"
    }

    response = await client.post(
        "/api/enforcement/respond",
        json={
            "risk_id": "risk-enf-0003",
            "action": "RESTRICT_USER",
            "confirm": True,
            "reason": "Confirmed data exfiltration",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["response_status"] == "EXECUTED"
    assert body["revoked_devices"] == 1
    assert "user:enf-restrict" in body["targets"]

    user = await db.users.find_one({"user_id": "enf-restrict"})
    assert user["enforcement_status"] == "RESTRICTED"
    device = await db.devices.find_one({"device_id": "device-enf-01"})
    assert device["status"] == "REVOKED"

    # Restricted users can no longer authenticate device heartbeats.
    blocked = await client.post(
        "/api/agent/heartbeat",
        json={"hostname": "h", "os_version": "o", "agent_version": "2.0.0"},
        headers={"X-Device-Token": "dev_enf_token"},
    )
    assert blocked.status_code == 403

    # Duplicate execution is reported, not silently repeated.
    duplicate = await client.post(
        "/api/enforcement/respond",
        json={"risk_id": "risk-enf-0003", "confirm": True},
        headers=admin_headers,
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["response_status"] == "ALREADY_HANDLED"

    rollback = await client.post(
        f"/api/enforcement/responses/{body['response_id']}/rollback",
        json={"reason": "False positive confirmed"},
        headers=admin_headers,
    )
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["response_status"] == "ROLLED_BACK"

    user = await db.users.find_one({"user_id": "enf-restrict"})
    assert user["enforcement_status"] == "ACTIVE"
    # Revoked devices must re-enroll; rollback does not resurrect credentials.
    device = await db.devices.find_one({"device_id": "device-enf-01"})
    assert device["status"] == "REVOKED"

    second_rollback = await client.post(
        f"/api/enforcement/responses/{body['response_id']}/rollback",
        json={"reason": "again"},
        headers=admin_headers,
    )
    assert second_rollback.status_code == 409


@pytest.mark.asyncio
async def test_revoke_devices_action_and_non_active_action(client, db):
    await create_user("enf-revoke", consent="ALLOWED")
    await create_user("enf-admin4", role="ADMIN")
    await create_device("enf-revoke", device_id="device-enf-02", token="dev_enf_token_2")
    await _seed_risk(db, "risk-enf-0004", "enf-revoke", category="HIGH")
    await _seed_risk(db, "risk-enf-0005", "enf-revoke", category="MEDIUM")
    admin = {"Authorization": f"Bearer {(await login(client, 'enf-admin4'))['access_token']}"}

    revoked = await client.post(
        "/api/enforcement/respond",
        json={
            "risk_id": "risk-enf-0004",
            "action": "REVOKE_DEVICES",
            "confirm": True,
        },
        headers=admin,
    )
    assert revoked.status_code == 201
    assert revoked.json()["revoked_devices"] == 1
    assert (await db.users.find_one({"user_id": "enf-revoke"}))["enforcement_status"] == "ACTIVE"

    warned = await client.post(
        "/api/enforcement/respond",
        json={"risk_id": "risk-enf-0005", "action": "WARN"},
        headers=admin,
    )
    assert warned.status_code == 201
    assert warned.json()["action_taken"] == "WARN"
    assert await db.alerts.count_documents({"risk_id": "risk-enf-0005"}) == 1

    responses = await client.get("/api/enforcement/responses", headers=admin)
    assert responses.status_code == 200
    assert {r["risk_id"] for r in responses.json()} == {"risk-enf-0004", "risk-enf-0005"}

    rollback_warn = await client.post(
        f"/api/enforcement/responses/{warned.json()['response_id']}/rollback",
        json={"reason": "not reversible"},
        headers=admin,
    )
    assert rollback_warn.status_code == 409


@pytest.mark.asyncio
async def test_unknown_risk_returns_404(client, db):
    await create_user("enf-admin5", role="ADMIN")
    admin = {"Authorization": f"Bearer {(await login(client, 'enf-admin5'))['access_token']}"}
    response = await client.post(
        "/api/enforcement/respond", json={"risk_id": "missing"}, headers=admin
    )
    assert response.status_code == 404
