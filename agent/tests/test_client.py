from __future__ import annotations

import pytest

from agent.client import AgentAuthError, AgentClient, AgentError, AgentTransportError


class FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.response

    def close(self):
        self.calls.append({"closed": True})


def test_enroll_sends_no_device_token_and_requires_returned_credential():
    session = FakeSession(FakeResponse(201, {"device_token": "dev_secret", "device_id": "a" * 64}))
    client = AgentClient("https://monitor.example.com/api", session=session)
    data = client.enroll("one-time-token", "a" * 64, "host", "Windows 11", "2.0.0")
    assert data["device_token"] == "dev_secret"
    call = session.calls[0]
    assert call["url"] == "https://monitor.example.com/api/agent/enroll"
    assert "X-Device-Token" not in call["headers"]
    assert call["verify"] is True
    assert call["json"]["enrollment_token"] == "one-time-token"


def test_device_token_is_sent_only_after_enrollment():
    session = FakeSession(FakeResponse(200, {"accepted": 1, "duplicates": 0, "rejected": [], "received": 1}))
    client = AgentClient("http://localhost:8000/api", device_token="dev_secret", session=session)
    client.send_events(
        [
            {
                "event_id": "e" * 16,
                "event_type": "process.started",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "action": "EXECUTE",
            }
        ]
    )
    assert session.calls[0]["headers"]["X-Device-Token"] == "dev_secret"
    assert session.calls[0]["verify"] is True


def test_auth_errors_are_distinct_from_transport_errors():
    session = FakeSession(FakeResponse(403, {"detail": {"status": "consent_required"}}))
    client = AgentClient("http://localhost:8000/api", device_token="dev_secret", session=session)
    with pytest.raises(AgentAuthError) as excinfo:
        client.heartbeat("host", "Windows 11", "2.0.0")
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == {"status": "consent_required"}


def test_server_errors_raise_transport_error_without_body_contents():
    session = FakeSession(FakeResponse(500, {"detail": "internal secret path C:\\Users\\a"}))
    client = AgentClient("http://localhost:8000/api", device_token="dev_secret", session=session)
    with pytest.raises(AgentTransportError) as excinfo:
        client.heartbeat("host", "Windows 11", "2.0.0")
    assert "C:\\Users" not in str(excinfo.value)


def test_empty_batch_does_not_call_the_backend():
    session = FakeSession(FakeResponse(200, {}))
    client = AgentClient("http://localhost:8000/api", session=session)
    assert client.send_events([])["accepted"] == 0
    assert session.calls == []


def test_batch_limit_is_enforced_locally():
    session = FakeSession(FakeResponse(200, {}))
    client = AgentClient("http://localhost:8000/api", session=session)
    with pytest.raises(AgentError):
        client.send_events([{}] * 201)
    assert session.calls == []


def test_non_json_response_is_transport_error():
    session = FakeSession(FakeResponse(200, ValueError("bad json")))
    client = AgentClient("http://localhost:8000/api", session=session)
    with pytest.raises(AgentTransportError):
        client.heartbeat("host", "Windows 11", "2.0.0")


def test_remote_plaintext_backend_is_rejected_at_construction():
    with pytest.raises(ValueError):
        AgentClient("http://monitor.example.com/api")
