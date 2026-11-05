"""SaaS proxy ingestion and event read API tests."""

from datetime import datetime, timedelta, timezone

import pytest

from conftest import create_user, login


def _proxy_event(event_id: str = "proxy-event-0001", **overrides) -> dict:
    payload = {
        "event_id": event_id,
        "event_type": "saas.activity",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "DOWNLOAD",
        "saas_app": "google_drive",
        "resource_id": "drive-file-1",
        "resource_name": "budget.xlsx",
        "metadata": {"bytes": 1024},
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_proxy_ingestion_requires_key(client, db):
    missing = await client.post("/api/events", json=_proxy_event())
    assert missing.status_code == 401
    wrong = await client.post(
        "/api/events", json=_proxy_event(), headers={"X-Ingestion-Key": "wrong"}
    )
    assert wrong.status_code == 401


@pytest.mark.asyncio
async def test_proxy_ingestion_clears_untrusted_identity(client, db):
    payload = _proxy_event(user_id="victim-user", device_id="victim-device", source="endpoint_agent")
    response = await client.post(
        "/api/events", json=payload, headers={"X-Ingestion-Key": "test-ingestion-key"}
    )
    assert response.status_code == 201, response.text
    assert response.json()["identity_verified"] is False

    stored = await db.events.find_one({"event_id": "proxy-event-0001"})
    assert stored["user_id"] is None
    assert stored["device_id"] is None
    assert stored["source"] == "saas_proxy"
    assert stored["metadata"]["identity_verified"] is False


@pytest.mark.asyncio
async def test_proxy_ingestion_is_idempotent(client, db):
    headers = {"X-Ingestion-Key": "test-ingestion-key"}
    first = await client.post("/api/events", json=_proxy_event(), headers=headers)
    second = await client.post("/api/events", json=_proxy_event(), headers=headers)
    assert first.status_code == 201
    assert second.json()["duplicate"] is True
    assert await db.events.count_documents({"event_id": "proxy-event-0001"}) == 1


@pytest.mark.asyncio
async def test_proxy_ingestion_rejects_bad_timestamps(client, db):
    headers = {"X-Ingestion-Key": "test-ingestion-key"}
    future = _proxy_event(
        timestamp=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    )
    assert (await client.post("/api/events", json=future, headers=headers)).status_code == 400

    old = _proxy_event(
        timestamp=(datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    )
    assert (await client.post("/api/events", json=old, headers=headers)).status_code == 400


@pytest.mark.asyncio
async def test_event_read_requires_authentication(client, db):
    assert (await client.get("/api/events")).status_code == 401


@pytest.mark.asyncio
async def test_event_filters_and_search(client, db):
    await create_user("filter-user")
    await create_user("filter-admin", role="ADMIN")
    headers = {"X-Ingestion-Key": "test-ingestion-key"}
    await client.post("/api/events", json=_proxy_event("filter-event-0001"), headers=headers)
    await client.post(
        "/api/events",
        json=_proxy_event("filter-event-0002", action="UPLOAD", resource_name="secret.docx"),
        headers=headers,
    )

    admin = {"Authorization": f"Bearer {(await login(client, 'filter-admin'))['access_token']}"}
    by_action = await client.get("/api/events?action=UPLOAD", headers=admin)
    assert [e["event_id"] for e in by_action.json()] == ["filter-event-0002"]

    by_query = await client.get("/api/events?q=budget", headers=admin)
    assert [e["event_id"] for e in by_query.json()] == ["filter-event-0001"]

    bad_range = await client.get(
        "/api/events?start=2026-02-01T00:00:00Z&end=2026-01-01T00:00:00Z", headers=admin
    )
    assert bad_range.status_code == 400
