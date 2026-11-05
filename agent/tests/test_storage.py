from __future__ import annotations

import json

import pytest

from agent.storage import StateError, StateStore


def test_save_load_and_clear_roundtrip(tmp_path):
    store = StateStore(tmp_path / "state")
    payload = {"device_token": "dev_secret", "device_id": "a" * 64, "user_id": "u1"}
    store.save(payload)
    assert store.load() == payload
    assert store.public_state() == {"device_id": "a" * 64, "user_id": "u1"}
    assert store.clear() is True
    assert store.load() is None
    assert store.clear() is False


def test_save_refuses_missing_token(tmp_path):
    store = StateStore(tmp_path)
    with pytest.raises(StateError):
        store.save({"device_id": "a" * 64})


def test_corrupt_state_is_reported_without_echoing_contents(tmp_path):
    store = StateStore(tmp_path)
    store.path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(StateError) as excinfo:
        store.load()
    assert "not-json" not in str(excinfo.value)


def test_incomplete_state_requires_reenrollment(tmp_path):
    store = StateStore(tmp_path)
    store.path.write_text(json.dumps({"device_id": "a" * 64}), encoding="utf-8")
    with pytest.raises(StateError):
        store.load()
