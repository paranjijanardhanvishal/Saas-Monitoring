import pytest
from app.risk.scoring import calculate_combined_risk, determine_overall_risk_category, normalize_behavioral_deviation
from app.risk.factors import generate_risk_explanation
from app.main import app
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

client = TestClient(app)

def test_score_normalization():
    # Behavioral deviation normalization
    assert normalize_behavioral_deviation(1.0) == 0.0
    assert normalize_behavioral_deviation(0.5) == 0.0
    assert normalize_behavioral_deviation(10.0) == 100.0
    assert normalize_behavioral_deviation(100.0) == 100.0
    
    # 5.5 is halfway between 1 and 10, so score should be 50
    assert abs(normalize_behavioral_deviation(5.5) - 50.0) < 0.001

def test_weight_validation():
    with pytest.raises(ValueError):
        calculate_combined_risk(50, 50, p_weight=0.6, b_weight=0.6)

def test_combined_score_calculation():
    # Both 20
    assert calculate_combined_risk(20.0, 20.0, 0.5, 0.5) == 20.0
    
    # Privacy driven
    assert calculate_combined_risk(80.0, 10.0, 0.5, 0.5) == 45.0
    
    # Behavior driven
    assert calculate_combined_risk(10.0, 90.0, 0.5, 0.5) == 50.0
    
    # Very high
    assert calculate_combined_risk(90.0, 95.0, 0.5, 0.5) == 92.5
    
    # Different weights
    assert calculate_combined_risk(100.0, 0.0, 0.8, 0.2) == 80.0

def test_risk_categories():
    assert determine_overall_risk_category(19.0) == "LOW"
    assert determine_overall_risk_category(49.0) == "MEDIUM"
    assert determine_overall_risk_category(79.0) == "HIGH"
    assert determine_overall_risk_category(80.0) == "CRITICAL"
    assert determine_overall_risk_category(100.0) == "CRITICAL"

def test_risk_factors_generation():
    privacy_finding = {"sensitivity_score": 65.0}
    anomaly_finding = {"is_anomaly": True, "reason": "Activity spike", "anomaly_type": "ACTIVITY_SPIKE"}
    
    factors, expl = generate_risk_explanation(65.0, 100.0, privacy_finding, anomaly_finding)
    assert "HIGH_SENSITIVITY_PII" in factors
    assert "ACTIVITY_SPIKE" in factors
    assert "BEHAVIORAL_ANOMALY" in factors

@pytest.mark.asyncio
async def test_api_risk_analyze_combined(mocker):
    mock_db = mocker.patch('app.risk.service.get_database')
    
    # Mock privacy finding
    mock_db.return_value.pii_findings.find_one = AsyncMock(return_value={"sensitivity_score": 80.0})
    
    # Mock anomaly finding
    mock_db.return_value.anomalies.find_one = AsyncMock(return_value={"deviation": 10.0, "is_anomaly": True, "anomaly_type": "ACTIVITY_SPIKE"})
    
    mock_db.return_value.risk_assessments.insert_one = AsyncMock()
    
    response = client.post("/api/risk/analyze", json={
        "user_id": "test_user",
        "event_id": "test_event",
        "privacy_finding_id": "p_id",
        "anomaly_id": "a_id"
    })
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["privacy_score"] == 80.0
    assert data["behavioral_score"] == 100.0
    assert data["combined_score"] == 90.0
    assert data["risk_category"] == "CRITICAL"
    assert data["is_partial_assessment"] is False
    assert "HIGH_SENSITIVITY_PII" in data["risk_factors"]
    assert "ACTIVITY_SPIKE" in data["risk_factors"]

@pytest.mark.asyncio
async def test_api_risk_analyze_partial(mocker):
    mock_db = mocker.patch('app.risk.service.get_database')
    
    # Mock NO privacy finding, but mock an anomaly finding
    mock_db.return_value.pii_findings.find_one = AsyncMock(return_value=None)
    mock_db.return_value.anomalies.find_one = AsyncMock(return_value={"deviation": 5.5, "is_anomaly": True, "anomaly_type": "ACTIVITY_SPIKE"})
    mock_db.return_value.risk_assessments.insert_one = AsyncMock()
    
    response = client.post("/api/risk/analyze", json={
        "user_id": "test_user2",
        "event_id": "test_event2",
        "anomaly_id": "a_id"
    })
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["privacy_score"] == 0.0
    assert data["behavioral_score"] == 50.0
    assert data["combined_score"] == 25.0
    assert data["risk_category"] == "MEDIUM"
    assert data["is_partial_assessment"] is True
