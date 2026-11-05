from __future__ import annotations

import json
from collections import deque

import pytest

from agent.client import AgentAuthError, AgentTransportError
from agent.collectors.base import Collector, make_event
from agent.config import AgentConfig
from agent.service import AgentService
from agent.storage import StateStore


class FakeClient:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.device_token = None
        self.enrolled = []
        self.sent = []
        self.heartbeat_calls = []
        self.closed = False
        self.auth_error = None
        self.send_error = None
        self.heartbeat_error = None

    def enroll(self, token, device_id, hostname, os_version, agent_version):
        self.enrolled.append((token, device_id, hostname, os_version, agent_version))
        return {"device_token": "dev_secret", "device_id": device_id, "user_id": "u1"}

    def heartbeat(self, hostname, os_version, agent_version, monitoring_active=True):
        if self.heartbeat_error:
            raise self.heartbeat_error
        if self.auth_error:
            raise self.auth_error
        self.heartbeat_calls.append(monitoring_active)
        return {"monitoring_enabled": self.enabled, "status": "active"}

    def send_events(self, events):
        if self.send_error:
            raise self.send_error
        self.sent.extend(events)
        return {"accepted": len(events), "duplicates": 0, "rejected": [], "received": len(events)}

    def close(self):
        self.closed = True


class FakeCollector(Collector):
    name = "fake"

    def __init__(self, events):
        super().__init__()
        self.batch = list(events)
        self.start_calls = 0
        self.stop_calls = 0

    def start(self):
        self.start_calls += 1

    def collect(self, now=None):
        return list(self.batch)

    def stop(self):
        self.stop_calls += 1


def make_config(tmp_path, token=None):
    config = AgentConfig()
    config.state_dir = tmp_path / "state"
    config.backend_url = "http://localhost:8000/api"
    config.enrollment_token = token
    config.event_batch_size = 100
    return config.validated()


def test_prepare_enrolls_once_and_persists_device_credential(tmp_path):
    config = make_config(tmp_path, token="one-time")
    client = FakeClient()
    store = StateStore(config.state_dir)
    service = AgentService(config, client=client, store=store, collectors=[])

    state = service.prepare()
    assert state["device_token"] == "dev_secret"
    assert client.device_token == "dev_secret"
    assert len(client.enrolled) == 1
    assert client.enrolled[0][0] == "one-time"
    assert store.load()["device_token"] == "dev_secret"

    second = AgentService(config, client=FakeClient(), store=store, collectors=[])
    second.prepare()
    assert second.client.enrolled == []
    assert second.client.device_token == "dev_secret"


def test_prepare_requires_a_token_when_not_enrolled(tmp_path):
    config = make_config(tmp_path)
    service = AgentService(config, client=FakeClient(), collectors=[])
    with pytest.raises(Exception) as excinfo:
        service.prepare()
    assert "enrollment token" in str(excinfo.value).lower()


def test_public_status_never_contains_the_device_token(tmp_path):
    config = make_config(tmp_path)
    store = StateStore(config.state_dir)
    store.save({"device_token": "dev_secret", "device_id": "a" * 64, "user_id": "u1"})
    service = AgentService(config, client=FakeClient(), store=store, collectors=[])
    serialized = json.dumps(service.public_status())
    assert "dev_secret" not in serialized
    assert "a" * 64 in serialized


def test_run_once_sends_collected_metadata(tmp_path):
    config = make_config(tmp_path)
    store = StateStore(config.state_dir)
    store.save({"device_token": "dev_secret", "device_id": "a" * 64, "user_id": "u1"})
    client = FakeClient(enabled=True)
    collector = FakeCollector(
        [
            make_event("process.started", "EXECUTE", resource_name="notepad.exe"),
            make_event("session.locked", "SESSION"),
        ]
    )
    service = AgentService(config, client=client, store=store, collectors=[collector])

    result = service.run_once()
    assert result.monitoring_active is True
    assert collector.start_calls == 1
    assert len(client.sent) == 2
    assert result.stats["accepted"] == 2
    assert service.stats.collected == 2


def test_disabled_consent_does_not_start_collectors(tmp_path):
    config = make_config(tmp_path)
    store = StateStore(config.state_dir)
    store.save({"device_token": "dev_secret", "device_id": "a" * 64, "user_id": "u1"})
    collector = FakeCollector([make_event("process.started", "EXECUTE")])
    service = AgentService(config, client=FakeClient(enabled=False), store=store, collectors=[collector])

    result = service.run_once()
    assert result.monitoring_active is False
    assert collector.start_calls == 0
    assert len(service._queue) == 0


def test_consent_withdrawal_clears_buffer_and_stops_collectors(tmp_path):
    config = make_config(tmp_path)
    store = StateStore(config.state_dir)
    store.save({"device_token": "dev_secret", "device_id": "a" * 64, "user_id": "u1"})
    client = FakeClient(enabled=True)
    collector = FakeCollector([make_event("process.started", "EXECUTE")])
    service = AgentService(config, client=client, store=store, collectors=[collector])
    service.run_once()
    assert collector.start_calls == 1

    client.enabled = False
    service.heartbeat()
    assert service.monitoring_active is False
    assert collector.stop_calls == 1
    assert len(service._queue) == 0


def test_ingestion_403_pauses_monitoring_without_crashing(tmp_path):
    config = make_config(tmp_path)
    store = StateStore(config.state_dir)
    store.save({"device_token": "dev_secret", "device_id": "a" * 64, "user_id": "u1"})
    client = FakeClient(enabled=True)
    client.send_error = AgentAuthError("consent required", 403, {"status": "consent_required"})
    collector = FakeCollector([make_event("process.started", "EXECUTE")])
    service = AgentService(config, client=client, store=store, collectors=[collector])

    result = service.run_once()
    assert result.monitoring_active is False
    assert len(service._queue) == 0
    assert collector.stop_calls == 1


def test_revoked_device_credential_is_fatal(tmp_path):
    config = make_config(tmp_path)
    store = StateStore(config.state_dir)
    store.save({"device_token": "dev_secret", "device_id": "a" * 64, "user_id": "u1"})
    client = FakeClient(enabled=True)
    client.auth_error = AgentAuthError("revoked", 401)
    service = AgentService(config, client=client, store=store, collectors=[])

    with pytest.raises(AgentAuthError):
        service.run_once()
    assert service.monitoring_active is False
    assert client.sent == []


def test_transport_failure_keeps_events_for_retry(tmp_path):
    config = make_config(tmp_path)
    store = StateStore(config.state_dir)
    store.save({"device_token": "dev_secret", "device_id": "a" * 64, "user_id": "u1"})
    client = FakeClient(enabled=True)
    client.send_error = AgentTransportError("offline")
    collector = FakeCollector([make_event("process.started", "EXECUTE")])
    service = AgentService(config, client=client, store=store, collectors=[collector])

    service.run_once()
    assert len(service._queue) == 1
    assert service.stats.send_failures == 1

    client.send_error = None
    assert service.flush() is True
    assert len(client.sent) == 1


def test_bounded_queue_counts_dropped_events(tmp_path):
    config = make_config(tmp_path)
    store = StateStore(config.state_dir)
    service = AgentService(config, client=FakeClient(), store=store, collectors=[])
    service._queue = deque(maxlen=2)
    service._enqueue(
        [
            make_event("process.started", "EXECUTE"),
            make_event("process.started", "EXECUTE"),
            make_event("process.started", "EXECUTE"),
        ]
    )
    assert len(service._queue) == 2
    assert service.stats.dropped == 1
