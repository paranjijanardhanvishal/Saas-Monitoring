from __future__ import annotations

import json

from agent.cli import main
from agent.storage import StateStore


def test_status_reports_enrollment_without_secret(tmp_path, capsys):
    state_dir = tmp_path / "state"
    StateStore(state_dir).save(
        {"device_token": "dev_secret", "device_id": "a" * 64, "user_id": "u1"}
    )
    code = main(["status", "--state-dir", str(state_dir)])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["enrolled"] is True
    assert payload["device"]["device_id"] == "a" * 64
    assert "dev_secret" not in captured.out
    assert "dev_secret" not in captured.err


def test_enroll_without_token_fails_clearly(tmp_path, capsys, caplog):
    caplog.set_level("ERROR", logger="agent.cli")
    code = main(["enroll", "--state-dir", str(tmp_path / "state")])
    capsys.readouterr()
    assert code == 2
    assert "enrollment token" in caplog.text.lower()
    assert not (tmp_path / "state" / "device.json").exists()


def test_uninstall_removes_local_credential(tmp_path, capsys):
    state_dir = tmp_path / "state"
    StateStore(state_dir).save(
        {"device_token": "dev_secret", "device_id": "a" * 64, "user_id": "u1"}
    )
    code = main(["uninstall", "--state-dir", str(state_dir)])
    captured = capsys.readouterr()
    assert code == 0
    assert json.loads(captured.out)["status"] == "state_removed"
    assert not (state_dir / "device.json").exists()
    assert "dev_secret" not in captured.out
