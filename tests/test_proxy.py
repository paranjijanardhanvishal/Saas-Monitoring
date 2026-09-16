import pytest
from app.proxy.event_mapper import EventMapper
from app.models.event import ActionEnum

def test_identify_saas():
    assert EventMapper.identify_saas("www.googleapis.com") == "google_drive"
    assert EventMapper.identify_saas("api.google.com") == "google_drive"
    assert EventMapper.identify_saas("example.com") == "unknown_saas"

def test_map_action():
    assert EventMapper.map_action("GET", "/files/123/download", "", "google_drive") == ActionEnum.DOWNLOAD
    assert EventMapper.map_action("GET", "/files", "", "google_drive") == ActionEnum.ACCESS
    assert EventMapper.map_action("POST", "/upload/drive/v3/files", "", "google_drive") == ActionEnum.UPLOAD
    assert EventMapper.map_action("DELETE", "/files/123", "", "google_drive") == ActionEnum.DELETE
    assert EventMapper.map_action("PATCH", "/files/123/permissions", "", "google_drive") == ActionEnum.PERMISSION_CHANGE

def test_sanitize_headers():
    headers = {
        "Authorization": "Bearer token123",
        "Cookie": "session=secret",
        "Content-Type": "application/json",
        "Accept": "*/*"
    }
    sanitized = EventMapper.sanitize_headers(headers)
    assert sanitized["Authorization"] == "[REDACTED]"
    assert sanitized["Cookie"] == "[REDACTED]"
    assert sanitized["Content-Type"] == "application/json"
    assert sanitized["Accept"] == "*/*"

def test_create_event_from_request():
    headers = {"Authorization": "Bearer test"}
    event = EventMapper.create_event_from_request(
        method="GET",
        url="https://www.googleapis.com/drive/v3/files/123?alt=media",
        headers=headers,
        status_code=200,
        content_type="application/pdf",
        request_size=0,
        response_size=1024
    )
    
    assert event.source == "google_drive"
    assert event.action == ActionEnum.DOWNLOAD
    assert event.user_id == "unknown" # as per current implementation
    assert event.metadata is not None
    assert event.metadata["status_code"] == 200
    assert event.metadata["response_size"] == 1024
    assert event.metadata["headers"]["Authorization"] == "[REDACTED]"
