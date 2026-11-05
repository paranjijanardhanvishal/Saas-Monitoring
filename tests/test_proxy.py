"""SaaS proxy event-mapping tests (no network interception)."""

from app.models.event import ActionEnum
from app.proxy.event_mapper import EventMapper


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


def test_sanitize_headers_redacts_credentials():
    headers = {
        "Authorization": "Bearer token123",
        "Cookie": "session=secret",
        "X-Api-Key": "key",
        "Set-Cookie": "a=b",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    sanitized = EventMapper.sanitize_headers(headers)
    assert sanitized["Authorization"] == "[REDACTED]"
    assert sanitized["Cookie"] == "[REDACTED]"
    assert sanitized["X-Api-Key"] == "[REDACTED]"
    assert sanitized["Set-Cookie"] == "[REDACTED]"
    assert sanitized["Content-Type"] == "application/json"
    assert sanitized["Accept"] == "*/*"


def test_create_event_from_request_has_no_trusted_identity():
    headers = {"Authorization": "Bearer test-token"}
    event = EventMapper.create_event_from_request(
        method="GET",
        url="https://www.googleapis.com/drive/v3/files/123?alt=media",
        headers=headers,
        client_ip="203.0.113.9",
        status_code=200,
        content_type="application/pdf",
        request_size=0,
        response_size=1024,
    )

    assert event.saas_app == "google_drive"
    assert event.action == ActionEnum.DOWNLOAD
    assert event.resource_id == "123"
    assert event.user_id is None
    assert event.device_id is None
    assert event.session_id.startswith("session_")
    assert event.metadata["status_code"] == 200
    assert event.metadata["response_size"] == 1024
    assert event.metadata["headers"]["Authorization"] == "[REDACTED]"
    assert event.metadata["identity_verified"] is False
    assert "test-token" not in str(event.model_dump())


def test_session_identity_is_stable_and_opaque():
    first = EventMapper.get_identity_from_headers({"Authorization": "Bearer abc"})
    second = EventMapper.get_identity_from_headers({"authorization": "bearer abc"})
    third = EventMapper.get_identity_from_headers({"Authorization": "Bearer xyz"})
    assert first == second
    assert first != third
    assert "abc" not in first
