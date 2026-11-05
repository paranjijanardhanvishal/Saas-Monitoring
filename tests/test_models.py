"""Unit tests for request/model validation boundaries."""

import pytest
from pydantic import ValidationError

from app.models.device import EnrollmentRequest, HeartbeatRequest
from app.models.event import EndpointEventIn, EventModel
from app.models.user import ConsentUpdate, UserCreate


def test_event_type_rejects_uppercase_or_spaces():
    with pytest.raises(ValidationError):
        EventModel(event_id="event-0001", event_type="Process Started", action="ACCESS")


def test_endpoint_event_forbids_client_supplied_trusted_fields():
    with pytest.raises(ValidationError):
        EndpointEventIn(
            event_id="event-0001",
            event_type="process.started",
            timestamp="2026-01-01T00:00:00Z",
            action="EXECUTE",
            user_id="victim",
        )
    with pytest.raises(ValidationError):
        EndpointEventIn(
            event_id="event-0001",
            event_type="process.started",
            timestamp="2026-01-01T00:00:00Z",
            action="EXECUTE",
            source="saas_proxy",
        )


def test_endpoint_event_accepts_supported_payload():
    event = EndpointEventIn(
        event_id="event-0001",
        event_type="process.started",
        timestamp="2026-01-01T00:00:00Z",
        action="EXECUTE",
        resource_name="notepad.exe",
    )
    assert event.event_type == "process.started"


def test_consent_cannot_be_reset_to_not_asked():
    with pytest.raises(ValidationError):
        ConsentUpdate(monitoring_enabled="NOT_ASKED")
    assert ConsentUpdate(monitoring_enabled="ALLOWED").monitoring_enabled == "ALLOWED"


def test_user_create_password_bounds():
    with pytest.raises(ValidationError):
        UserCreate(user_id="abc", email="a@example.com", password="short")
    user = UserCreate(user_id="abc", email="A@Example.com", password="CorrectHorseBattery42")
    assert user.role == "USER"


def test_heartbeat_forbids_extra_fields():
    with pytest.raises(ValidationError):
        HeartbeatRequest(
            hostname="h",
            os_version="o",
            agent_version="2.0.0",
            user_id="victim",
        )


def test_enrollment_request_requires_reasonable_ids():
    with pytest.raises(ValidationError):
        EnrollmentRequest(
            enrollment_token="short",
            device_id="short",
            hostname="h",
            os_version="o",
            agent_version="1",
        )
