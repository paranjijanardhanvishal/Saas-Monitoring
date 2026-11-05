"""Alert lifecycle, deduplication, incident correlation and SOC actions."""

from datetime import datetime, timezone

import pytest

from conftest import create_user, login
from app.services.alerts import create_alert, create_alerts_from_risk


@pytest.mark.asyncio
async def test_alert_deduplication_is_deterministic(db):
    first = await create_alert(
        db,
        severity="HIGH",
        title="Sensitive download",
        reason="PII moved to an unmanaged device",
        user_id="dedupe-user",
        event_id="dedupe-event-0001",
        source="risk_engine",
    )
    second = await create_alert(
        db,
        severity="HIGH",
        title="Sensitive download",
        reason="PII moved to an unmanaged device",
        user_id="dedupe-user",
        event_id="dedupe-event-0001",
        source="risk_engine",
    )
    assert str(first["_id"]) == str(second["_id"])
    assert await db.alerts.count_documents({"user_id": "dedupe-user"}) == 1


@pytest.mark.asyncio
async def test_critical_risk_creates_alert_and_incident(db):
    assessment = {
        "risk_id": "risk-critical-0001",
        "user_id": "critical-user",
        "event_id": "critical-event-0001",
        "risk_category": "CRITICAL",
        "combined_score": 95.0,
        "privacy_score": 90.0,
        "behavioral_score": 80.0,
        "endpoint_score": 70.0,
        "risk_factors": ["HIGH_SENSITIVITY_PII", "BEHAVIORAL_ANOMALY"],
        "explanation": ["High-sensitivity PII detected", "Activity spike detected"],
        "saas_app": "google_drive",
        "resource_id": "file-1",
    }
    alerts = await create_alerts_from_risk(db, assessment)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "CRITICAL"
    assert alerts[0]["evidence"][0]["risk_id"] == "risk-critical-0001"

    incidents = await db.incidents.find({"user_id": "critical-user"}).to_list(length=10)
    assert len(incidents) == 1
    assert incidents[0]["severity"] == "CRITICAL"
    assert str(alerts[0]["_id"]) in incidents[0]["related_alerts"]

    # A second critical alert for the same user is linked, not duplicated.
    assessment["risk_id"] = "risk-critical-0002"
    assessment["event_id"] = "critical-event-0002"
    await create_alerts_from_risk(db, assessment)
    incidents = await db.incidents.find({"user_id": "critical-user"}).to_list(length=10)
    assert len(incidents) == 1
    assert len(incidents[0]["related_alerts"]) == 2


@pytest.mark.asyncio
async def test_low_risk_does_not_create_alert(db):
    alerts = await create_alerts_from_risk(
        db,
        {
            "risk_id": "risk-low-0001",
            "user_id": "low-user",
            "event_id": "low-event-0001",
            "risk_category": "LOW",
            "combined_score": 10.0,
        },
    )
    assert alerts == []


@pytest.mark.asyncio
async def test_admin_alert_lifecycle_with_audit(client, db):
    await create_user("alert-admin", role="ADMIN")
    headers = {"Authorization": f"Bearer {(await login(client, 'alert-admin'))['access_token']}"}

    created = await client.post(
        "/api/alerts",
        json={
            "severity": "MEDIUM",
            "title": "Manual review",
            "reason": "Analyst requested review",
            "user_id": "alert-admin",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    alert_id = created.json()["id"]

    acknowledged = await client.patch(
        f"/api/alerts/{alert_id}/status",
        json={"status": "ACKNOWLEDGED", "note": "Taken by analyst"},
        headers=headers,
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "ACKNOWLEDGED"
    assert acknowledged.json()["acknowledged_by"] == "alert-admin"

    noted = await client.post(
        f"/api/alerts/{alert_id}/notes",
        json={"note": "Correlated with endpoint event"},
        headers=headers,
    )
    assert noted.status_code == 200
    actions = [h["action"] for h in noted.json()["history"]]
    assert "created" in actions
    assert "status:ACKNOWLEDGED" in actions
    assert "note" in actions

    assert await db.audit_logs.count_documents(
        {"target_id": alert_id, "target_type": "alert"}
    ) >= 3


@pytest.mark.asyncio
async def test_invalid_alert_id_is_rejected(client, db):
    await create_user("alert-invalid", role="ADMIN")
    headers = {"Authorization": f"Bearer {(await login(client, 'alert-invalid'))['access_token']}"}
    response = await client.get("/api/alerts/not-an-object-id", headers=headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_incident_lifecycle(client, db):
    await create_user("inc-admin", role="ADMIN")
    headers = {"Authorization": f"Bearer {(await login(client, 'inc-admin'))['access_token']}"}

    created = await client.post(
        "/api/incidents",
        json={
            "title": "Suspicious exfiltration",
            "severity": "HIGH",
            "reason": "Large download followed by upload",
            "user_id": "inc-admin",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    incident_id = created.json()["id"]
    assert created.json()["response_history"]

    assigned = await client.patch(
        f"/api/incidents/{incident_id}/assign",
        json={"assigned_to": "inc-admin"},
        headers=headers,
    )
    assert assigned.status_code == 200
    assert assigned.json()["assigned_to"] == "inc-admin"

    status = await client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "CONTAINED", "note": "Device isolated"},
        headers=headers,
    )
    assert status.status_code == 200
    assert status.json()["status"] == "CONTAINED"

    noted = await client.post(
        f"/api/incidents/{incident_id}/notes",
        json={"note": "Awaiting user statement"},
        headers=headers,
    )
    assert noted.status_code == 200
    assert noted.json()["notes"][0]["author"] == "inc-admin"


@pytest.mark.asyncio
async def test_incident_creation_requires_admin(client, db):
    await create_user("inc-user")
    headers = {"Authorization": f"Bearer {(await login(client, 'inc-user'))['access_token']}"}
    response = await client.post(
        "/api/incidents",
        json={"title": "nope", "severity": "LOW", "reason": "nope"},
        headers=headers,
    )
    assert response.status_code == 403
