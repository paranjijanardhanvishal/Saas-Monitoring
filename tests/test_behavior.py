"""Behavioural baseline and anomaly detection tests."""

from datetime import datetime, timedelta, timezone

import pytest

from app.behavior.service import analyze_behavior
from app.behavior.schemas import BehaviorAnalysisRequest
from conftest import create_user, login


@pytest.mark.asyncio
async def test_cold_start_creates_profile_without_anomaly(db):
    now = datetime.now(timezone.utc)
    finding = await analyze_behavior(
        BehaviorAnalysisRequest(user_id="cold-user", event_id="cold-event-0001", timestamp=now)
    )
    assert finding.is_anomaly is False
    assert finding.deviation == pytest.approx(1.0)

    profile = await db.behavior_profiles.find_one({"user_id": "cold-user"})
    assert profile is not None
    assert profile["ewma"]["1h"] == pytest.approx(1.0)
    assert await db.anomalies.count_documents({"user_id": "cold-user"}) == 1


@pytest.mark.asyncio
async def test_activity_spike_is_detected_against_adaptive_baseline(db):
    now = datetime.now(timezone.utc)
    await db.behavior_profiles.insert_one(
        {
            "user_id": "spike-user",
            "last_activity_timestamp": now - timedelta(hours=2),
            "ewma": {
                "30m": 0.01,
                "1h": 0.01,
                "2h": 0.01,
                "8h": 0.01,
                "1d": 0.01,
                "7d": 0.01,
                "30d": 0.01,
                "90d": 0.01,
            },
            "updated_at": now - timedelta(hours=2),
        }
    )
    finding = await analyze_behavior(
        BehaviorAnalysisRequest(user_id="spike-user", event_id="spike-event-0001", timestamp=now)
    )
    assert finding.is_anomaly is True
    assert finding.anomaly_type == "ACTIVITY_SPIKE"
    assert finding.deviation > 5.0

    stored = await db.anomalies.find_one({"anomaly_id": finding.anomaly_id})
    assert stored["is_anomaly"] is True


@pytest.mark.asyncio
async def test_behavior_api_requires_event_ownership(client, db):
    await create_user("beh-owner")
    await create_user("beh-other")
    now = datetime.now(timezone.utc)
    await db.events.insert_one(
        {
            "event_id": "beh-event-0001",
            "event_type": "saas.activity",
            "user_id": "beh-owner",
            "action": "ACCESS",
            "source": "endpoint_agent",
            "timestamp": now,
            "ingestion_timestamp": now,
        }
    )
    other = {"Authorization": f"Bearer {(await login(client, 'beh-other'))['access_token']}"}
    denied = await client.post(
        "/api/behavior/analyze",
        json={"user_id": "beh-owner", "event_id": "beh-event-0001"},
        headers=other,
    )
    assert denied.status_code == 403

    owner = {"Authorization": f"Bearer {(await login(client, 'beh-owner'))['access_token']}"}
    allowed = await client.post(
        "/api/behavior/analyze",
        json={"user_id": "beh-owner", "event_id": "beh-event-0001"},
        headers=owner,
    )
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["user_id"] == "beh-owner"

    profiles = await client.get("/api/behavior/profiles", headers=owner)
    assert profiles.status_code == 200
    assert [p["user_id"] for p in profiles.json()] == ["beh-owner"]


@pytest.mark.asyncio
async def test_missing_event_returns_404(client, db):
    await create_user("beh-missing")
    headers = {"Authorization": f"Bearer {(await login(client, 'beh-missing'))['access_token']}"}
    response = await client.post(
        "/api/behavior/analyze",
        json={"user_id": "beh-missing", "event_id": "does-not-exist"},
        headers=headers,
    )
    assert response.status_code == 404
