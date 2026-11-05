from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from agent.collectors.base import make_event
from agent.collectors.windows import (
    FailedLoginCollector,
    FileCollector,
    ForegroundCollector,
    ProcessCollector,
    SessionCollector,
    UsageCollector,
)

BASE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_make_event_rejects_unknown_types_and_actions():
    with pytest.raises(ValueError):
        make_event("shell.command", "EXECUTE")
    with pytest.raises(ValueError):
        make_event("process.started", "READ")


def test_make_event_strips_nul_and_bounds_text():
    event = make_event(
        "process.started",
        "EXECUTE",
        resource_name="bad\x00name" + "x" * 400,
        metadata={"collector": "test"},
        timestamp=BASE,
    )
    assert "\x00" not in event["resource_name"]
    assert len(event["resource_name"]) <= 256
    assert event["timestamp"].startswith("2026-01-01T12:00:00")


def test_process_collector_baseline_start_and_stop():
    processes = {10: {"pid": 10, "name": "explorer.exe", "create_time": 100.0}}
    collector = ProcessCollector(provider=lambda: dict(processes))
    collector.start()
    assert collector.collect(BASE) == []

    processes[20] = {"pid": 20, "name": "notepad.exe", "create_time": 200.0}
    events = collector.collect(BASE + timedelta(seconds=5))
    assert [e["event_type"] for e in events] == ["process.started"]
    assert events[0]["application"]["name"] == "notepad.exe"

    processes.pop(10)
    events = collector.collect(BASE + timedelta(seconds=10))
    assert [e["event_type"] for e in events] == ["process.stopped"]
    assert events[0]["resource_name"] == "explorer.exe"


def test_process_collector_treats_pid_reuse_as_new_process():
    processes = {10: {"pid": 10, "name": "old.exe", "create_time": 100.0}}
    collector = ProcessCollector(provider=lambda: dict(processes))
    collector.start()
    processes[10] = {"pid": 10, "name": "new.exe", "create_time": 999.0}
    events = collector.collect(BASE)
    assert [e["event_type"] for e in events] == ["process.started"]
    assert events[0]["resource_name"] == "new.exe"


def test_process_collector_caps_event_bursts():
    processes = {}
    collector = ProcessCollector(provider=lambda: dict(processes), max_events_per_poll=2)
    collector.start()
    for pid in range(1, 6):
        processes[pid] = {"pid": pid, "name": f"p{pid}.exe", "create_time": float(pid)}
    assert len(collector.collect(BASE)) == 2


def test_foreground_collector_emits_only_on_actual_change():
    current = {"pid": 1, "name": "a.exe"}
    collector = ForegroundCollector(provider=lambda: dict(current) if current else None)
    assert collector.collect(BASE) == []
    assert collector.collect(BASE + timedelta(seconds=1)) == []

    current = {"pid": 2, "name": "b.exe"}
    events = collector.collect(BASE + timedelta(seconds=10))
    assert len(events) == 1
    assert events[0]["event_type"] == "application.foreground_changed"
    assert events[0]["metadata"]["previous_name"] == "a.exe"
    assert events[0]["metadata"]["previous_foreground_seconds"] >= 9


def test_usage_collector_aggregates_and_flushes_on_change():
    current = {"pid": 1, "name": "a.exe"}
    collector = UsageCollector(provider=lambda: dict(current) if current else None, report_interval=30)
    assert collector.collect(BASE) == []
    assert collector.collect(BASE + timedelta(seconds=20)) == []
    events = collector.collect(BASE + timedelta(seconds=31))
    assert len(events) == 1
    assert events[0]["event_type"] == "application.usage"
    assert events[0]["metadata"]["seconds"] == 31

    assert collector.collect(BASE + timedelta(seconds=32)) == []
    current = {"pid": 2, "name": "b.exe"}
    events = collector.collect(BASE + timedelta(seconds=40))
    assert len(events) == 1
    assert events[0]["resource_name"] == "a.exe"
    assert events[0]["metadata"]["seconds"] == 1


def test_session_collector_tracks_lock_transitions():
    states = iter(["unlocked", "locked", "locked", "unlocked"])
    collector = SessionCollector(provider=lambda: next(states, None))
    assert collector.collect(BASE) == []
    assert [e["event_type"] for e in collector.collect(BASE)] == ["session.locked"]
    assert collector.collect(BASE) == []
    assert [e["event_type"] for e in collector.collect(BASE)] == ["session.unlocked"]


def test_failed_login_collector_deduplicates_events():
    rows = [
        {
            "timestamp": (BASE - timedelta(minutes=1)).isoformat(),
            "account": "alice",
            "logon_type": "3",
            "ip_address": "10.0.0.5",
            "status": "0xc000006d",
            "sub_status": "0xc000006a",
        }
    ]
    calls = []

    def reader(since, limit=50):
        calls.append(limit)
        return rows if limit > 1 else []

    collector = FailedLoginCollector(reader=reader)
    collector.start()
    events = collector.collect(BASE)
    assert len(events) == 1
    assert events[0]["event_type"] == "failed_login.observed"
    assert events[0]["metadata"]["account"] == "alice"
    assert collector.collect(BASE) == []
    assert calls[0] == 1


def test_failed_login_collector_disables_without_security_log_access():
    def reader(since, limit=50):
        raise PermissionError("access denied")

    collector = FailedLoginCollector(reader=reader)
    collector.start()
    assert collector.enabled is False
    assert "not accessible" in (collector.last_error or "").lower()
    assert collector.collect(BASE) == []


def test_file_collector_emits_names_not_full_paths(tmp_path):
    collector = FileCollector([tmp_path])
    target = tmp_path / "quarterly-report.xlsx"
    collector._handle("created", str(target))
    events = collector.collect(BASE)
    assert len(events) == 1
    assert events[0]["event_type"] == "file.created"
    assert events[0]["resource_name"] == "quarterly-report.xlsx"
    assert events[0]["metadata"]["extension"] == ".xlsx"
    serialized = json.dumps(events[0])
    assert str(tmp_path) not in serialized
    assert collector.collect(BASE) == []


def test_file_collector_ignores_temporary_and_state_files(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    collector = FileCollector([tmp_path], state_dir=state_dir)
    collector._handle("created", str(tmp_path / "upload.part"))
    collector._handle("created", str(tmp_path / "~$draft.docx"))
    collector._handle("created", str(state_dir / "device.json"))
    assert collector.collect(BASE) == []


def test_file_collector_deleted_and_moved_events(tmp_path):
    collector = FileCollector([tmp_path])
    source = tmp_path / "old.txt"
    destination = tmp_path / "new.txt"
    collector._handle("deleted", str(source))
    collector._handle("moved", str(source), str(destination))
    events = collector.collect(BASE)
    assert [e["event_type"] for e in events] == ["file.deleted", "file.modified", "file.created"]
    assert events[0]["action"] == "DELETE"
    assert events[-1]["resource_name"] == "new.txt"


def test_file_collector_uses_polling_fallback_snapshot(tmp_path):
    collector = FileCollector([tmp_path])
    target = tmp_path / "one.txt"
    target.write_text("metadata only", encoding="utf-8")
    collector._snapshot = collector._scan()
    assert collector._snapshot
    target.write_text("changed", encoding="utf-8")
    collector._poll(BASE)
    events = collector.collect(BASE)
    assert any(event["resource_name"] == "one.txt" for event in events)
    assert all("content" not in json.dumps(event) for event in events)
