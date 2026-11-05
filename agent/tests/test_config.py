from __future__ import annotations

import pytest

from agent.config import AgentConfig, stable_device_id, validate_backend_url


def test_https_backend_is_accepted():
    assert validate_backend_url("https://monitor.example.com/api/") == "https://monitor.example.com/api"


def test_loopback_http_is_allowed_for_development():
    assert validate_backend_url("http://localhost:8000/api") == "http://localhost:8000/api"
    assert validate_backend_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"


def test_plaintext_remote_backend_is_rejected():
    with pytest.raises(ValueError):
        validate_backend_url("http://monitor.example.com/api")


def test_invalid_scheme_and_missing_host_are_rejected():
    with pytest.raises(ValueError):
        validate_backend_url("ftp://monitor.example.com")
    with pytest.raises(ValueError):
        validate_backend_url("https:///api")


def test_stable_device_id_is_deterministic_and_not_secret():
    first = stable_device_id()
    second = stable_device_id()
    assert first == second
    assert len(first) == 64
    assert all(ch in "0123456789abcdef" for ch in first)


def test_default_config_has_safe_intervals():
    config = AgentConfig()
    assert config.heartbeat_interval >= 10
    assert config.poll_interval >= 1
    assert config.event_batch_size <= 200
    assert config.backend_url.startswith(("http://", "https://"))


def test_http_loopback_dev_switch_is_not_a_tls_bypass():
    # The only transport relaxation is loopback HTTP; TLS verification itself
    # is always enabled in the client.
    with pytest.raises(ValueError):
        validate_backend_url("http://192.168.1.10:8000/api")
