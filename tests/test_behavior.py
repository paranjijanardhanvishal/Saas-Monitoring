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


@pytest.mark.asyncio
async def test_all_eight_ewma_windows_update(db):
    base_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    # Cold start initial event
    f1 = await analyze_behavior(
        BehaviorAnalysisRequest(user_id="user-8w", event_id="ev-8w-1", timestamp=base_time)
    )
    assert len(f1.ewma) == 8
    expected_windows = {"30m", "1h", "2h", "8h", "1d", "7d", "30d", "90d"}
    assert set(f1.ewma.keys()) == expected_windows

    # Second event 10 seconds later (current_rate = 3600 / 10 = 360.0)
    t2 = base_time + timedelta(seconds=10)
    await analyze_behavior(
        BehaviorAnalysisRequest(user_id="user-8w", event_id="ev-8w-2", timestamp=t2)
    )
    profile = await db.behavior_profiles.find_one({"user_id": "user-8w"})
    assert profile is not None
    assert set(profile["ewma"].keys()) == expected_windows

    # With high rate 360, shorter window (30m, lambda=0.5) adapts faster than long window (90d, lambda=0.01)
    assert (
        profile["ewma"]["30m"]
        > profile["ewma"]["1h"]
        > profile["ewma"]["2h"]
        > profile["ewma"]["8h"]
        > profile["ewma"]["1d"]
        > profile["ewma"]["7d"]
        > profile["ewma"]["30d"]
        > profile["ewma"]["90d"]
    )


@pytest.mark.asyncio
async def test_multi_window_anomaly_scoring(db):
    now = datetime.now(timezone.utc)
    # Pre-populate profile with baseline 1.0 across all windows, 10s prior
    await db.behavior_profiles.insert_one(
        {
            "user_id": "multi-win-user",
            "last_activity_timestamp": now - timedelta(seconds=10),
            "ewma": {w: 1.0 for w in ["30m", "1h", "2h", "8h", "1d", "7d", "30d", "90d"]},
            "access_count": 10,
            "download_count": 0,
            "delete_count": 0,
            "recent_downloads": [],
            "updated_at": now - timedelta(seconds=10),
        }
    )
    # Rapid second event now -> delta_t = 10s, rate = 3600 / 10 = 360.0, deviation = 360x
    f = await analyze_behavior(
        BehaviorAnalysisRequest(user_id="multi-win-user", event_id="ev-mw-1", timestamp=now)
    )
    assert f.is_anomaly is True
    assert f.anomaly_type == "ACTIVITY_SPIKE"
    assert "30m" in f.window_deviations
    assert "90d" in f.window_deviations
    assert len(f.window_deviations) == 8
    assert f.deviation > 5.0


@pytest.mark.asyncio
async def test_action_specific_counters(db):
    user_id = "counter-user"
    base_time = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Access event
    await analyze_behavior(
        BehaviorAnalysisRequest(user_id=user_id, event_id="ev-c-1", timestamp=base_time),
        event={"action": "ACCESS", "event_type": "file.access"},
    )
    p = await db.behavior_profiles.find_one({"user_id": user_id})
    assert p["access_count"] == 1
    assert p["download_count"] == 0
    assert p["delete_count"] == 0

    # 2. Download event
    await analyze_behavior(
        BehaviorAnalysisRequest(user_id=user_id, event_id="ev-c-2", timestamp=base_time + timedelta(seconds=5)),
        event={"action": "DOWNLOAD", "event_type": "file.download"},
    )
    p = await db.behavior_profiles.find_one({"user_id": user_id})
    assert p["access_count"] == 1
    assert p["download_count"] == 1
    assert p["delete_count"] == 0
    assert len(p["recent_downloads"]) == 1

    # 3. Delete event
    await analyze_behavior(
        BehaviorAnalysisRequest(user_id=user_id, event_id="ev-c-3", timestamp=base_time + timedelta(seconds=10)),
        event={"action": "DELETE", "event_type": "file.delete"},
    )
    p = await db.behavior_profiles.find_one({"user_id": user_id})
    assert p["access_count"] == 1
    assert p["download_count"] == 1
    assert p["delete_count"] == 1


@pytest.mark.asyncio
async def test_download_burst_detection_over_50(db):
    user_id = "burst-user"
    start_time = datetime(2026, 3, 1, 14, 0, 0, tzinfo=timezone.utc)

    # 51 downloads in 2 minutes
    finding = None
    for i in range(51):
        t = start_time + timedelta(seconds=i * 2)
        finding = await analyze_behavior(
            BehaviorAnalysisRequest(user_id=user_id, event_id=f"burst-ev-{i}", timestamp=t),
            event={"action": "DOWNLOAD", "event_type": "file.download"},
        )

    assert finding is not None
    assert finding.burst_detected is True
    assert finding.burst_count == 51
    assert finding.is_anomaly is True
    assert finding.anomaly_type in {"DOWNLOAD_BURST", "COMPOUND_BURST"}
    assert "download burst" in finding.reason.lower()


@pytest.mark.asyncio
async def test_download_burst_exactly_50(db):
    user_id = "boundary-50-user"
    start_time = datetime(2026, 3, 1, 14, 0, 0, tzinfo=timezone.utc)

    # Exactly 50 downloads in 3 minutes (should NOT trigger burst anomaly: rule is >50)
    finding = None
    for i in range(50):
        t = start_time + timedelta(seconds=i * 3)
        finding = await analyze_behavior(
            BehaviorAnalysisRequest(user_id=user_id, event_id=f"b50-ev-{i}", timestamp=t),
            event={"action": "DOWNLOAD", "event_type": "file.download"},
        )

    assert finding is not None
    assert finding.burst_detected is False
    assert finding.burst_count == 50
    assert finding.anomaly_type != "DOWNLOAD_BURST"


@pytest.mark.asyncio
async def test_download_burst_outside_window(db):
    user_id = "spaced-user"
    start_time = datetime(2026, 3, 1, 14, 0, 0, tzinfo=timezone.utc)

    # 51 downloads spread over 20 minutes (each 24 seconds apart)
    # In any rolling 5-minute (300-second) window, at most 300/24 = 12-13 downloads exist
    finding = None
    for i in range(51):
        t = start_time + timedelta(seconds=i * 24)
        finding = await analyze_behavior(
            BehaviorAnalysisRequest(user_id=user_id, event_id=f"spaced-ev-{i}", timestamp=t),
            event={"action": "DOWNLOAD", "event_type": "file.download"},
        )

    assert finding is not None
    assert finding.burst_detected is False
    assert finding.burst_count < 20


@pytest.mark.asyncio
async def test_backward_compatibility_with_legacy_profile(db):
    user_id = "legacy-user"
    now = datetime.now(timezone.utc)
    # Legacy document created before Phase 4 fields existed
    await db.behavior_profiles.insert_one(
        {
            "user_id": user_id,
            "last_activity_timestamp": now - timedelta(minutes=10),
            "ewma": {
                "30m": 1.0,
                "1h": 1.0,
                "2h": 1.0,
                "8h": 1.0,
                "1d": 1.0,
                "7d": 1.0,
                "30d": 1.0,
                "90d": 1.0,
            },
            "updated_at": now - timedelta(minutes=10),
        }
    )

    # Analyzing with this profile must not raise KeyError or ValidationError
    finding = await analyze_behavior(
        BehaviorAnalysisRequest(user_id=user_id, event_id="legacy-ev-1", timestamp=now),
        event={"action": "DOWNLOAD", "event_type": "file.download"},
    )
    assert finding is not None
    assert finding.burst_detected is False
    assert finding.burst_count == 1

    updated = await db.behavior_profiles.find_one({"user_id": user_id})
    assert updated["download_count"] == 1
    assert updated["access_count"] == 0
    assert updated["delete_count"] == 0
    assert len(updated["recent_downloads"]) == 1


@pytest.mark.asyncio
async def test_download_burst_risk_and_alert_integration(db):
    from app.risk.service import analyze_risk
    from app.risk.schemas import RiskAssessmentRequest
    from app.services.alerts import create_alerts_from_risk

    user_id = "risk-burst-user"
    now = datetime.now(timezone.utc)

    # Seed an event and a high-sensitivity PII finding for the sensitive files being downloaded
    await db.events.insert_one(
        {
            "event_id": "rburst-ev-51",
            "event_type": "file.download",
            "user_id": user_id,
            "action": "DOWNLOAD",
            "source": "endpoint_agent",
            "timestamp": now + timedelta(seconds=102),
            "ingestion_timestamp": now + timedelta(seconds=102),
        }
    )
    await db.pii_findings.insert_one(
        {
            "finding_id": "pii-burst-001",
            "event_id": "rburst-ev-51",
            "user_id": user_id,
            "sensitivity_score": 90.0,
            "category": "CONFIDENTIAL",
        }
    )

    # Generate burst anomaly finding (>50 downloads)
    finding = None
    for i in range(52):
        t = now + timedelta(seconds=i * 2)
        finding = await analyze_behavior(
            BehaviorAnalysisRequest(user_id=user_id, event_id=f"rburst-ev-{i}", timestamp=t),
            event={"action": "DOWNLOAD", "event_type": "file.download"},
        )

    assert finding.burst_detected is True

    # Risk evaluation
    req = RiskAssessmentRequest(
        user_id=user_id,
        event_id="rburst-ev-51",
        privacy_finding_id="pii-burst-001",
        anomaly_id=finding.anomaly_id,
        timestamp=now + timedelta(seconds=104),
    )
    assessment = await analyze_risk(req)
    assert assessment.behavioral_score >= 90.0
    assert assessment.privacy_score == 90.0
    assert "DOWNLOAD_BURST" in assessment.risk_factors
    assert assessment.risk_category in {"HIGH", "CRITICAL"}

    # Alert creation
    alerts = await create_alerts_from_risk(db, assessment.model_dump())
    assert len(alerts) >= 1
    assert alerts[0]["severity"] in {"HIGH", "CRITICAL"}
    assert "download burst" in alerts[0]["reason"].lower()
