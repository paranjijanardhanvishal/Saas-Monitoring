import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.event import EventModel, ActionEnum
import uuid
from unittest.mock import AsyncMock

client = TestClient(app)

def test_post_event(mocker):
    # Mock log_event so we don't actually hit the database
    mock_log_event = mocker.patch('app.api.events.log_event', new_callable=AsyncMock)
    
    event_data = {
        "event_id": str(uuid.uuid4()),
        "user_id": "test_user",
        "file_id": "123",
        "action": ActionEnum.ACCESS,
        "source": "google_drive",
        "metadata": {"http_method": "GET"}
    }
    
    response = client.post("/api/events", json=event_data)
    assert response.status_code == 201
    assert response.json()["status"] == "success"
    mock_log_event.assert_called_once()
