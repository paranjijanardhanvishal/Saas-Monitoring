"""Integration coverage for the isolated, pipeline-backed synthetic demo."""

import pytest

from conftest import create_user, login


@pytest.mark.asyncio
async def test_admin_demo_generation_and_safe_reset(client, db):
    await create_user("demo-admin", role="ADMIN")
    headers = {"Authorization": f"Bearer {(await login(client, 'demo-admin'))['access_token']}"}

    generated = await client.post("/api/demo/generate", headers=headers)
    assert generated.status_code == 201, generated.text
    payload = generated.json()
    assert payload["synthetic"] is True
    assert payload["total_events"] == 27
    assert payload["risk_category"] in ("HIGH", "CRITICAL")
    assert payload["alerts_created"] >= 1

    # Verify event counts across all 5 behavioral profiles
    assert await db.events.count_documents({"metadata.synthetic": True}) == 27
    assert await db.events.count_documents({"user_id": "normal.user"}) == 4
    assert await db.events.count_documents({"user_id": "frequent.user"}) == 8
    assert await db.events.count_documents({"user_id": "suspicious.user"}) == 12
    assert await db.events.count_documents({"user_id": "sensitive.user"}) == 2
    assert await db.events.count_documents({"user_id": "new.user"}) == 1

    # Verify suspicious.user triggered activity spike anomaly
    spike_anomaly = await db.anomalies.find_one({"user_id": "suspicious.user", "is_anomaly": True})
    assert spike_anomaly is not None
    assert spike_anomaly["anomaly_type"] in ("ACTIVITY_SPIKE", "COMPOUND")

    # Verify normal.user and frequent.user have baseline profiles but NO anomalies
    normal_profile = await db.behavior_profiles.find_one({"user_id": "normal.user"})
    assert normal_profile is not None
    assert await db.anomalies.count_documents({"user_id": "normal.user", "is_anomaly": True}) == 0

    frequent_profile = await db.behavior_profiles.find_one({"user_id": "frequent.user"})
    assert frequent_profile is not None
    assert await db.anomalies.count_documents({"user_id": "frequent.user", "is_anomaly": True}) == 0

    # Verify new.user has exactly 1 event and cold-start baseline without false anomaly
    assert await db.anomalies.count_documents({"user_id": "new.user", "is_anomaly": True}) == 0

    # Verify sensitive.user triggered PII detection, risk evaluation, alerts, and incidents
    assert await db.pii_findings.count_documents({"user_id": "sensitive.user"}) >= 1
    assert await db.risk_assessments.count_documents({"user_id": "sensitive.user"}) >= 1
    assert await db.alerts.count_documents({"user_id": "sensitive.user"}) >= 1
    assert await db.incidents.count_documents({"user_id": "sensitive.user"}) >= 1

    # Verify demo status endpoint
    status = await client.get("/api/demo/status", headers=headers)
    assert status.status_code == 200
    assert len(status.json()["runs"]) >= 1

    # Safe reset removes all synthetic records
    reset = await client.delete("/api/demo/reset", headers=headers)
    assert reset.status_code == 200, reset.text
    assert reset.json()["deleted"]["events"] >= 26
    assert await db.events.count_documents({"metadata.synthetic": True}) == 0
    assert await db.users.count_documents({"source": "synthetic_demo"}) == 0
    assert await db.anomalies.count_documents({"user_id": "suspicious.user"}) == 0
    assert await db.pii_findings.count_documents({"user_id": "sensitive.user"}) == 0
