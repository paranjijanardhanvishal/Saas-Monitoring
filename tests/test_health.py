from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import AsyncMock

client = TestClient(app)

def test_health_check_disconnected(mocker):
    # Test health check when DB is disconnected
    mocker.patch('app.api.health.db_client.client', None)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "unhealthy"

def test_health_check_connected(mocker):
    # Mock successful ping
    mock_client = mocker.MagicMock()
    mock_client.admin.command = AsyncMock(return_value=True)
    mocker.patch('app.api.health.db_client.client', mock_client)
    
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
