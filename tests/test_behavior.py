import pytest
from datetime import datetime, timezone, timedelta
from app.behavior.activity_rate import calculate_activity_rate
from app.behavior.ewma import calculate_new_ewma, update_all_ewma_windows, initialize_ewma_windows, LAMBDA_CONFIG
from app.behavior.anomaly_detector import detect_anomaly, ANOMALY_DEVIATION_THRESHOLD
from app.main import app
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

client = TestClient(app)

def test_activity_rate_calculation():
    # 1 hour apart -> 1 activity / hour
    assert calculate_activity_rate(3600, 0) == 1.0
    
    # 30 mins apart -> 2 activities / hour
    assert calculate_activity_rate(1800, 0) == 2.0
    
    # 2 hours apart -> 0.5 activity / hour
    assert calculate_activity_rate(7200, 0) == 0.5

def test_zero_elapsed_time_protection():
    # Exactly same time -> should cap at 1s, which gives 3600/hr
    assert calculate_activity_rate(100, 100) == 3600.0
    
    # 0.5s apart -> should cap at 1s -> 3600/hr
    assert calculate_activity_rate(100.5, 100) == 3600.0

def test_ewma_mathematical_formula():
    """
    Mathematical test from prompt:
    previous_EWMA = 2
    current_rate = 10
    lambda = 0.5
    Expected: EWMA_new = 0.5(10) + 0.5(2) = 6
    """
    assert calculate_new_ewma(current_rate=10, previous_ewma=2, lambda_val=0.5) == 6.0

def test_lambda_validation():
    # Ensure all configured lambdas are 0 < lambda <= 1
    for window, l_val in LAMBDA_CONFIG.items():
        assert 0 < l_val <= 1.0
    
    # All 8 windows exist
    expected_windows = {"30m", "1h", "2h", "8h", "1d", "7d", "30d", "90d"}
    assert set(LAMBDA_CONFIG.keys()) == expected_windows

def test_ewma_initialization():
    initial_rate = 5.0
    ewma_dict = initialize_ewma_windows(initial_rate)
    for window in LAMBDA_CONFIG.keys():
        assert ewma_dict[window] == 5.0

def test_update_all_ewma_windows():
    prev = {w: 2.0 for w in LAMBDA_CONFIG.keys()}
    new_ewma = update_all_ewma_windows(10.0, prev)
    
    # For 30m, lambda is 0.5
    assert new_ewma["30m"] == 6.0
    
    # For 1h, lambda is 0.4 -> 0.4(10) + 0.6(2) = 4 + 1.2 = 5.2
    assert abs(new_ewma["1h"] - 5.2) < 0.001

def test_burst_scenario_anomaly():
    """
    Burst activity produces a stronger temporal signal than stable activity.
    """
    # Scenario A: Stable activity (1 activity per hour -> rate = 1.0)
    baseline_stable = {"1h": 1.0}
    # User does another activity 1 hour later (rate = 1.0)
    finding_stable = detect_anomaly("userA", "e1", datetime.now(timezone.utc), 1.0, baseline_stable)
    assert finding_stable.is_anomaly is False
    
    # Scenario B: Burst activity (almost simultaneously -> rate = 3600.0)
    baseline_burst = {"1h": 1.0} # Normal historic baseline is 1
    # User does another activity 1 second later (rate = 3600)
    finding_burst = detect_anomaly("userB", "e2", datetime.now(timezone.utc), 3600.0, baseline_burst)
    assert finding_burst.is_anomaly is True
    assert finding_burst.deviation == 3600.0
    assert "Activity rate exceeded adaptive baseline" in finding_burst.reason

@pytest.mark.asyncio
async def test_api_behavior_analyze_cold_start(mocker):
    mock_get_profile = mocker.patch('app.behavior.service.get_user_profile')
    mock_get_profile.return_value = None # Cold start
    
    mock_save_profile = mocker.patch('app.behavior.service.save_user_profile')
    mock_save_profile.return_value = AsyncMock()
    
    mock_save_anomaly = mocker.patch('app.behavior.service.save_anomaly_finding')
    mock_save_anomaly.return_value = AsyncMock()
    
    response = client.post("/api/behavior/analyze", json={
        "user_id": "new_user",
        "event_id": "event_1"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["is_anomaly"] is False # Cold start shouldn't immediately flag
    assert data["activity_rate"] == 1.0
    
    # EWMA was initialized with 1.0
    assert data["ewma"]["30m"] == 1.0
    assert data["ewma"]["90d"] == 1.0

@pytest.mark.asyncio
async def test_api_behavior_analyze_timezone_regression(mocker):
    """
    Regression test for Step 4 Activity Rate:
    Ensure that naive local-time/UTC objects from MongoDB don't artificially 
    inflate elapsed time due to tzinfo discrepancies during current_ts calculation.
    """
    from app.behavior.schemas import BehaviorProfileModel
    from datetime import datetime, timezone, timedelta
    
    # 1. Mock DB returning a naive datetime that represents UTC time (e.g. from Motor)
    naive_db_time = datetime.utcnow()
    mock_profile = BehaviorProfileModel(
        user_id="tz_user",
        last_activity_timestamp=naive_db_time,
        ewma={"30m": 1.0, "1h": 1.0}
    )
    
    mock_get_profile = mocker.patch('app.behavior.service.get_user_profile')
    mock_get_profile.return_value = mock_profile
    
    mock_save_profile = mocker.patch('app.behavior.service.save_user_profile')
    mock_save_profile.return_value = AsyncMock()
    
    mock_save_anomaly = mocker.patch('app.behavior.service.save_anomaly_finding')
    mock_save_anomaly.return_value = AsyncMock()
    
    # 2. Simulate request just 60 seconds later, with timezone-aware UTC datetime
    # (Pydantic naturally parses requests into tz-aware objects if they have Z or +00:00)
    aware_req_time = naive_db_time.replace(tzinfo=timezone.utc) + timedelta(seconds=60)
    
    response = client.post("/api/behavior/analyze", json={
        "user_id": "tz_user",
        "event_id": "event_tz",
        "timestamp": aware_req_time.isoformat()
    })
    
    assert response.status_code == 201
    data = response.json()
    
    # 3. Expected rate: 3600 / 60 seconds = 60.0
    # Before the bug fix, it would be extremely low (like 0.177) due to IST offset.
    assert abs(data["activity_rate"] - 60.0) < 0.1
    
    # Because 60.0 is way above 1.0, it should trigger an anomaly
    assert data["is_anomaly"] is True

