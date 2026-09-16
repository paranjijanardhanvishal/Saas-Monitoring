import pytest
from app.privacy.sensitivity import classify_entity_sensitivity, calculate_sensitivity_score, determine_risk_category
from app.privacy.presidio_analyzer import get_analyzer
from app.main import app
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

client = TestClient(app)

def test_classify_entity_sensitivity():
    assert classify_entity_sensitivity("CREDIT_CARD") == "HIGH"
    assert classify_entity_sensitivity("AADHAAR") == "HIGH"
    assert classify_entity_sensitivity("EMAIL_ADDRESS") == "MODERATE"
    assert classify_entity_sensitivity("PHONE_NUMBER") == "MODERATE"
    assert classify_entity_sensitivity("PERSON") == "LOW"
    assert classify_entity_sensitivity("IP_ADDRESS") == "LOW"
    assert classify_entity_sensitivity("SOMETHING_ELSE") == "UNKNOWN"

def test_calculate_sensitivity_score():
    # 1 Low = 1
    assert calculate_sensitivity_score(0, 0, 1) == 1
    # 1 Moderate = 5
    assert calculate_sensitivity_score(0, 1, 0) == 5
    # 1 High = 10
    assert calculate_sensitivity_score(1, 0, 0) == 10
    
    # 1 High + 2 Moderate + 3 Low = 10 + 10 + 3 = 23
    assert calculate_sensitivity_score(1, 2, 3) == 23
    
    # Cap at 100
    assert calculate_sensitivity_score(15, 0, 0) == 100
    assert calculate_sensitivity_score(0, 25, 0) == 100

def test_determine_risk_category():
    assert determine_risk_category(19) == "SAFE"
    assert determine_risk_category(20) == "SENSITIVE"
    assert determine_risk_category(59) == "SENSITIVE"
    assert determine_risk_category(60) == "HIGH_RISK"
    assert determine_risk_category(100) == "HIGH_RISK"

def test_presidio_analyzer_init():
    analyzer = get_analyzer()
    assert analyzer is not None
    # Check if custom recognizers were added
    recognizer_names = [r.name for r in analyzer.registry.recognizers]
    assert "aadhaar_recognizer" in recognizer_names
    assert "password_recognizer" in recognizer_names

@pytest.mark.asyncio
async def test_privacy_analysis_api_no_pii(mocker):
    mock_db = mocker.patch('app.privacy.service.get_database')
    mock_db.return_value.pii_findings.insert_one = AsyncMock()
    
    response = client.post("/api/privacy/analyze", json={
        "text": "This is a safe text with no personal information.",
        "file_id": "test_file_1"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["sensitivity_score"] == 0
    assert data["category"] == "SAFE"
    assert len(data["entities"]) == 0

@pytest.mark.asyncio
async def test_privacy_analysis_api_with_pii(mocker):
    mock_db = mocker.patch('app.privacy.service.get_database')
    mock_db.return_value.pii_findings.insert_one = AsyncMock()
    
    test_text = "Contact me at testuser@example.com or call 555-0199. My Aadhaar is 1234 5678 9012 and my password: secret."
    
    response = client.post("/api/privacy/analyze", json={
        "text": test_text,
        "file_id": "test_file_2"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["category"] in ["SENSITIVE", "HIGH_RISK"]
    
    # Check that raw PII is not in the response
    assert "testuser@example.com" not in str(data)
    assert "1234 5678 9012" not in str(data)
    assert "secret" not in str(data)
    
    # Check entities
    entity_types = [e["entity_type"] for e in data["entities"]]
    assert "EMAIL_ADDRESS" in entity_types
    assert "AADHAAR" in entity_types
    assert "PASSWORD" in entity_types
