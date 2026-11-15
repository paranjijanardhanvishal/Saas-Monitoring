"""Tests for the dashboard overview and 24-hour event volume timeline."""

from datetime import datetime, timedelta, timezone

import pytest

from conftest import create_user, login


def _event(event_id: str, user_id: str, timestamp: datetime, **overrides) -> dict:
    document = {
        "event_id": event_id,
        "event_type": "saas.activity",
        "user_id": user_id,
        "source": "endpoint_agent",
        "saas_app": "endpoint",
        "action": "ACCESS",
        "timestamp": timestamp,
        "ingestion_timestamp": timestamp,
        "metadata": {},
    }
    document.update(overrides)
    return document


@pytest.mark.asyncio
async def test_dashboard_hourly_no_events(client, db):
    """When there are no events, the timeline returns exactly 24 zero-filled hourly buckets."""
    await create_user("dash-empty-user")
    user = {"Authorization": f"Bearer {(await login(client, 'dash-empty-user'))['access_token']}"}

    res = await client.get("/api/dashboard/overview", headers=user)
    assert res.status_code == 200
    data = res.json()

    assert data["events"]["last_24h"] == 0
    by_hour = data["events"]["by_hour"]
    assert len(by_hour) == 24

    for item in by_hour:
        assert item["count"] == 0
        assert item["hour"].endswith("Z")
        # Validate ISO 8601 parsing
        dt = datetime.fromisoformat(item["hour"].replace("Z", "+00:00"))
        assert dt.minute == 0
        assert dt.second == 0

    # Ensure continuous 1-hour intervals
    parsed = [datetime.fromisoformat(item["hour"].replace("Z", "+00:00")) for item in by_hour]
    for i in range(1, len(parsed)):
        assert parsed[i] - parsed[i - 1] == timedelta(hours=1)


@pytest.mark.asyncio
async def test_dashboard_hourly_one_event(client, db):
    """A single event appears in exactly one bucket with count 1, and the other 23 buckets are zero."""
    await create_user("dash-single-user")
    user = {"Authorization": f"Bearer {(await login(client, 'dash-single-user'))['access_token']}"}

    now = datetime.now(timezone.utc)
    event_time = now - timedelta(hours=2)
    target_bucket_hour = event_time.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00Z")

    await db.events.insert_one(_event("evt-single-1", "dash-single-user", timestamp=event_time))

    res = await client.get("/api/dashboard/overview", headers=user)
    assert res.status_code == 200
    data = res.json()

    assert data["events"]["last_24h"] == 1
    by_hour = data["events"]["by_hour"]
    assert len(by_hour) == 24

    buckets_with_events = [b for b in by_hour if b["count"] > 0]
    assert len(buckets_with_events) == 1
    assert buckets_with_events[0]["hour"] == target_bucket_hour
    assert buckets_with_events[0]["count"] == 1


@pytest.mark.asyncio
async def test_dashboard_hourly_multiple_events_same_hour(client, db):
    """Multiple events in the same hour aggregate into that single hourly bucket."""
    await create_user("dash-multi-user")
    user = {"Authorization": f"Bearer {(await login(client, 'dash-multi-user'))['access_token']}"}

    now = datetime.now(timezone.utc)
    base_time = (now - timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
    target_bucket_hour = base_time.strftime("%Y-%m-%dT%H:00:00Z")

    events = [
        _event("evt-m-1", "dash-multi-user", timestamp=base_time + timedelta(minutes=5)),
        _event("evt-m-2", "dash-multi-user", timestamp=base_time + timedelta(minutes=25)),
        _event("evt-m-3", "dash-multi-user", timestamp=base_time + timedelta(minutes=50)),
    ]
    await db.events.insert_many(events)

    res = await client.get("/api/dashboard/overview", headers=user)
    assert res.status_code == 200
    data = res.json()

    assert data["events"]["last_24h"] == 3
    by_hour = data["events"]["by_hour"]
    assert len(by_hour) == 24

    buckets_with_events = [b for b in by_hour if b["count"] > 0]
    assert len(buckets_with_events) == 1
    assert buckets_with_events[0]["hour"] == target_bucket_hour
    assert buckets_with_events[0]["count"] == 3


@pytest.mark.asyncio
async def test_dashboard_hourly_across_different_hours(client, db):
    """Events across distinct hours populate their respective buckets, with zeroes in between."""
    await create_user("dash-diff-user")
    user = {"Authorization": f"Bearer {(await login(client, 'dash-diff-user'))['access_token']}"}

    now = datetime.now(timezone.utc)
    t1 = now - timedelta(hours=1)
    t2 = now - timedelta(hours=5)
    t3 = now - timedelta(hours=10)

    b1 = t1.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00Z")
    b2 = t2.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00Z")
    b3 = t3.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00Z")

    events = [
        _event("evt-d-1", "dash-diff-user", timestamp=t1),
        _event("evt-d-2", "dash-diff-user", timestamp=t2),
        _event("evt-d-3", "dash-diff-user", timestamp=t3),
    ]
    await db.events.insert_many(events)

    res = await client.get("/api/dashboard/overview", headers=user)
    assert res.status_code == 200
    data = res.json()

    assert data["events"]["last_24h"] == 3
    by_hour = data["events"]["by_hour"]
    assert len(by_hour) == 24

    hour_map = {b["hour"]: b["count"] for b in by_hour}
    assert hour_map[b1] == 1
    assert hour_map[b2] == 1
    assert hour_map[b3] == 1
    assert sum(hour_map.values()) == 3


@pytest.mark.asyncio
async def test_dashboard_hourly_cutoff_and_zero_fill(client, db):
    """Events older than 24 hours are excluded; hours with zero events remain zero-filled."""
    await create_user("dash-cutoff-user")
    user = {"Authorization": f"Bearer {(await login(client, 'dash-cutoff-user'))['access_token']}"}

    now = datetime.now(timezone.utc)
    old_event = now - timedelta(hours=25)
    recent_event = now - timedelta(hours=4)

    recent_bucket = recent_event.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00Z")

    await db.events.insert_many([
        _event("evt-old-1", "dash-cutoff-user", timestamp=old_event),
        _event("evt-recent-1", "dash-cutoff-user", timestamp=recent_event),
    ])

    res = await client.get("/api/dashboard/overview", headers=user)
    assert res.status_code == 200
    data = res.json()

    assert data["events"]["last_24h"] == 1
    by_hour = data["events"]["by_hour"]
    assert len(by_hour) == 24

    hour_map = {b["hour"]: b["count"] for b in by_hour}
    assert hour_map[recent_bucket] == 1
    assert sum(hour_map.values()) == 1


@pytest.mark.asyncio
async def test_dashboard_hourly_events_across_midnight(client, db):
    """Events crossing the midnight boundary (23:xx and 00:xx) correctly populate their buckets."""
    await create_user("dash-midnight-user")
    user = {"Authorization": f"Bearer {(await login(client, 'dash-midnight-user'))['access_token']}"}

    # First get the timeline to identify the 23:00 and 00:00 buckets in the active 24-hour window
    res_init = await client.get("/api/dashboard/overview", headers=user)
    assert res_init.status_code == 200
    by_hour_init = res_init.json()["events"]["by_hour"]

    bucket_23 = next((b["hour"] for b in by_hour_init if "T23:00:00Z" in b["hour"]), None)
    bucket_00 = next((b["hour"] for b in by_hour_init if "T00:00:00Z" in b["hour"]), None)
    assert bucket_23 is not None
    assert bucket_00 is not None

    dt_23 = datetime.fromisoformat(bucket_23.replace("Z", "+00:00")) + timedelta(minutes=35)
    dt_00 = datetime.fromisoformat(bucket_00.replace("Z", "+00:00")) + timedelta(minutes=15)

    await db.events.insert_many([
        _event("evt-mid-23", "dash-midnight-user", timestamp=dt_23),
        _event("evt-mid-00", "dash-midnight-user", timestamp=dt_00),
    ])

    res = await client.get("/api/dashboard/overview", headers=user)
    assert res.status_code == 200
    data = res.json()

    assert data["events"]["last_24h"] == 2
    by_hour = data["events"]["by_hour"]
    assert len(by_hour) == 24

    hour_map = {b["hour"]: b["count"] for b in by_hour}
    assert hour_map[bucket_23] == 1
    assert hour_map[bucket_00] == 1
    assert sum(hour_map.values()) == 2

