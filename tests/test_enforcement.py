import pytest
from app.enforcement.schemas import ActionTypeEnum, ResponseStatusEnum
from app.enforcement.policy import determine_response_action, generate_response_reason
from app.main import app
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

client = TestClient(app)

def test_policy_mapping():
    assert determine_response_action("LOW") == ActionTypeEnum.LOG
    assert determine_response_action("MEDIUM") == ActionTypeEnum.ALERT
    assert determine_response_action("HIGH") == ActionTypeEnum.WARN
    assert determine_response_action("CRITICAL") == ActionTypeEnum.SIMULATED_BLOCK
    
    # Fallback
    assert determine_response_action("UNKNOWN_CATEGORY") == ActionTypeEnum.LOG

def test_reason_generation():
    assert "recorded" in generate_response_reason(ActionTypeEnum.LOG, "LOW").lower()
    assert "alert" in generate_response_reason(ActionTypeEnum.ALERT, "MEDIUM").lower()
    assert "warning" in generate_response_reason(ActionTypeEnum.WARN, "HIGH").lower()
    assert "simulated" in generate_response_reason(ActionTypeEnum.SIMULATED_BLOCK, "CRITICAL").lower()

@pytest.mark.asyncio
async def test_api_enforcement_respond_success(mocker):
    mock_db = mocker.patch('app.enforcement.service.get_database')
    
    # Mock finding risk assessment
    mock_db.return_value.risk_assessments.find_one = AsyncMock(return_value={
        "risk_id": "r_1",
        "user_id": "u_1",
        "event_id": "e_1",
        "risk_category": "CRITICAL"
    })
    
    # Mock duplicate check -> none exists
    mock_db.return_value.enforcement_responses.find_one = AsyncMock(return_value=None)
    mock_db.return_value.enforcement_responses.insert_one = AsyncMock()
    
    response = client.post("/api/enforcement/respond", json={
        "risk_id": "r_1"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["risk_id"] == "r_1"
    assert data["user_id"] == "u_1"
    assert data["event_id"] == "e_1"
    assert data["risk_category"] == "CRITICAL"
    assert data["action_taken"] == "SIMULATED_BLOCK"
    assert data["response_status"] == "SIMULATED"

@pytest.mark.asyncio
async def test_api_enforcement_respond_duplicate(mocker):
    mock_db = mocker.patch('app.enforcement.service.get_database')
    
    mock_db.return_value.risk_assessments.find_one = AsyncMock(return_value={"risk_id": "r_2"})
    
    # Mock duplicate check -> already exists
    mock_db.return_value.enforcement_responses.find_one = AsyncMock(return_value={
        "response_id": "resp_1",
        "risk_id": "r_2",
        "user_id": "u_2",
        "event_id": "e_2",
        "risk_category": "MEDIUM",
        "action_taken": "ALERT",
        "response_status": "EXECUTED",
        "reason": "Security alert"
    })
    
    response = client.post("/api/enforcement/respond", json={
        "risk_id": "r_2"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["response_status"] == "ALREADY_HANDLED"
    assert data["action_taken"] == "ALERT"

@pytest.mark.asyncio
async def test_api_enforcement_respond_not_found(mocker):
    mock_db = mocker.patch('app.enforcement.service.get_database')
    
    # Risk assessment not found
    mock_db.return_value.risk_assessments.find_one = AsyncMock(return_value=None)
    
    response = client.post("/api/enforcement/respond", json={
        "risk_id": "nonexistent"
    })
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
