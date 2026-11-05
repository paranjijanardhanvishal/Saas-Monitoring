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
    assert payload["normal_events"] == 12
    assert payload["risk_category"] == "CRITICAL"
    assert payload["alerts_created"] == 1

    assert await db.events.count_documents({"metadata.synthetic": True}) == 13
    assert await db.pii_findings.count_documents({"user_id": "demo_mia_hr"}) == 1
    assert await db.alerts.count_documents({"user_id": "demo_mia_hr"}) == 1
    assert await db.incidents.count_documents({"user_id": "demo_mia_hr"}) == 1

    status = await client.get("/api/demo/status", headers=headers)
    assert status.status_code == 200
    assert len(status.json()["runs"]) == 1

    reset = await client.delete("/api/demo/reset", headers=headers)
    assert reset.status_code == 200, reset.text
    assert reset.json()["deleted"]["events"] == 13
    assert await db.events.count_documents({"metadata.synthetic": True}) == 0
    assert await db.users.count_documents({"source": "synthetic_demo"}) == 0
