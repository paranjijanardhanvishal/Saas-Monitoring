"""Windows endpoint collectors.

Every collector observes *metadata only*: process names, foreground
application names, session lock state, failed-logon metadata and file
names/sizes inside explicitly configured directories. File contents,
keystrokes, screenshots, clipboard data and browser history are never read.

Collectors are best-effort. Optional capabilities (the Security event log,
``watchdog``) degrade to an explicit disabled state instead of fabricating
events.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Tuple

from .base import Collector, make_event
from .windows_native import (
    get_foreground_process,
    get_session_state,
    read_failed_logins,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_EVENTS = 50
DEFAULT_QUEUE_LIMIT = 2000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(moment: Optional[datetime]) -> datetime:
    if moment is None:
        return _now()
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _clean_name(value: Any, limit: int = 128) -> Optional[str]:
    if value is None:
        return None
    text = str(value).replace("\x00", "").strip()
    return text[:limit] if text else None


def default_process_provider() -> Dict[int, Dict[str, Any]]:
    """Return ``{pid: {pid, name, create_time}}`` for running processes."""
    import psutil

    result: Dict[int, Dict[str, Any]] = {}
    for process in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            info = process.info
            pid = int(info.get("pid"))
            if pid <= 0:
                continue
            result[pid] = {
                "pid": pid,
                "name": _clean_name(info.get("name") or "unknown") or "unknown",
                "create_time": float(info.get("create_time") or 0.0),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
            continue
    return result


class ProcessCollector(Collector):
    """Observe process start/stop transitions.

    The first poll establishes a baseline and emits nothing, so starting the
    agent does not replay every already-running process as a new event.
    """

    name = "process"

    def __init__(
        self,
        provider: Optional[Callable[[], Dict[int, Dict[str, Any]]]] = None,
        max_events_per_poll: int = DEFAULT_MAX_EVENTS,
    ):
        super().__init__()
        self._provider = provider or default_process_provider
        self._max_events = max_events_per_poll
        self._known: Dict[int, Dict[str, Any]] = {}
        self._primed = False

    def start(self) -> None:
        try:
            self._known = dict(self._provider())
            self._primed = True
        except Exception as exc:  # pragma: no cover - platform dependent
            self.disable(f"Process enumeration unavailable: {type(exc).__name__}")

    def collect(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        moment = _as_utc(now)
        try:
            current = self._provider()
        except Exception as exc:
            self.last_error = f"Process enumeration failed: {type(exc).__name__}"
            logger.warning("Process enumeration failed: %s", type(exc).__name__)
            return []
        if not self._primed:
            self._known = dict(current)
            self._primed = True
            return []

        events: List[Dict[str, Any]] = []
        started: List[Dict[str, Any]] = []
        for pid, info in current.items():
            previous = self._known.get(pid)
            if previous is None or previous.get("create_time") != info.get("create_time"):
                started.append(info)
        stopped = [info for pid, info in self._known.items() if pid not in current]

        for info in started[: self._max_events]:
            pid = info["pid"]
            opened = float(info.get("create_time") or 0.0)
            events.append(
                make_event(
                    "process.started",
                    "EXECUTE",
                    resource_id=f"pid:{pid}:{int(opened)}",
                    resource_name=info.get("name"),
                    application={"name": info.get("name"), "pid": pid},
                    metadata={
                        "pid": pid,
                        "create_time_epoch": round(opened, 3),
                        "collector": self.name,
                    },
                    timestamp=moment,
                )
            )
        for info in stopped[: self._max_events]:
            pid = info["pid"]
            started_at = float(info.get("create_time") or 0.0)
            duration = None
            if started_at > 0:
                duration = max(0, int(time.time() - started_at))
            events.append(
                make_event(
                    "process.stopped",
                    "SYSTEM",
                    resource_id=f"pid:{pid}:{int(started_at)}",
                    resource_name=info.get("name"),
                    application={"name": info.get("name"), "pid": pid},
                    metadata={
                        "pid": pid,
                        "duration_seconds": duration,
                        "collector": self.name,
                    },
                    timestamp=moment,
                )
            )

        self._known = dict(current)
        return events

    def stop(self) -> None:
        self._known.clear()


class ForegroundCollector(Collector):
    """Observe foreground application changes (window titles are not read)."""

    name = "foreground"

    def __init__(
        self,
        provider: Callable[[], Optional[Dict[str, Any]]] = get_foreground_process,
    ):
        super().__init__()
        self._provider = provider
        self._current: Optional[Dict[str, Any]] = None
        self._changed_at: Optional[datetime] = None

    def collect(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        moment = _as_utc(now)
        try:
            current = self._provider()
        except Exception as exc:
            self.last_error = f"Foreground lookup failed: {type(exc).__name__}"
            return []
        if not current:
            return []
        name = _clean_name(current.get("name"))
        try:
            pid = int(current.get("pid"))
        except (TypeError, ValueError):
            return []
        if not name:
            return []

        previous = self._current
        if (
            previous is not None
            and previous.get("pid") == pid
            and previous.get("name") == name
        ):
            return []

        duration = None
        if self._changed_at is not None:
            duration = max(0, int((moment - self._changed_at).total_seconds()))
        self._current = {"pid": pid, "name": name}
        self._changed_at = moment
        if previous is None:
            # Baseline the first observation; a foreground change is emitted
            # only after the user actually switches application.
            return []
        return [
            make_event(
                "application.foreground_changed",
                "ACCESS",
                resource_id=f"app:{hashlib.sha256(name.lower().encode('utf-8')).hexdigest()[:16]}",
                resource_name=name,
                application={"name": name, "pid": pid},
                metadata={
                    "previous_name": previous.get("name"),
                    "previous_pid": previous.get("pid"),
                    "previous_foreground_seconds": duration,
                    "collector": self.name,
                },
                timestamp=moment,
            )
        ]

    def stop(self) -> None:
        self._current = None
        self._changed_at = None


class UsageCollector(Collector):
    """Aggregate foreground application usage into periodic metadata events."""

    name = "usage"

    def __init__(
        self,
        provider: Callable[[], Optional[Dict[str, Any]]] = get_foreground_process,
        report_interval: int = 300,
        max_sample_seconds: int = 120,
    ):
        super().__init__()
        self._provider = provider
        self._report_interval = max(30, int(report_interval))
        self._max_sample = max(5, int(max_sample_seconds))
        self._current: Optional[Dict[str, Any]] = None
        self._last_sample: Optional[datetime] = None
        self._window_start: Optional[datetime] = None
        self._seconds = 0.0
        self._samples = 0

    def _flush(self, moment: datetime) -> List[Dict[str, Any]]:
        if not self._current or self._seconds < 1:
            self._seconds = 0.0
            self._samples = 0
            self._window_start = moment
            return []
        name = self._current.get("name") or "unknown"
        pid = self._current.get("pid")
        event = make_event(
            "application.usage",
            "ACCESS",
            resource_id=f"app:{hashlib.sha256(str(name).lower().encode('utf-8')).hexdigest()[:16]}",
            resource_name=name,
            application={"name": name, "pid": pid},
            metadata={
                "seconds": int(self._seconds),
                "samples": self._samples,
                "collector": self.name,
            },
            timestamp=moment,
        )
        self._seconds = 0.0
        self._samples = 0
        self._window_start = moment
        return [event]

    def collect(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        moment = _as_utc(now)
        try:
            current = self._provider()
        except Exception as exc:
            self.last_error = f"Usage sampling failed: {type(exc).__name__}"
            return []

        if self._last_sample is None:
            self._last_sample = moment
            self._window_start = moment
            if current and current.get("name"):
                self._current = {
                    "name": _clean_name(current.get("name")),
                    "pid": current.get("pid"),
                }
            return []

        delta = (moment - self._last_sample).total_seconds()
        delta = min(max(delta, 0.0), float(self._max_sample))
        self._last_sample = moment

        name = _clean_name(current.get("name")) if current else None
        if not name:
            # Locked/no foreground: flush what was already observed rather
            # than attributing idle time to the last application.
            events = self._flush(moment)
            self._current = None
            return events

        if self._current is None:
            self._current = {"name": name, "pid": current.get("pid")}
            self._window_start = moment
            return []

        if name != self._current.get("name"):
            events = self._flush(moment)
            self._current = {"name": name, "pid": current.get("pid")}
            return events

        self._seconds += delta
        self._samples += 1
        if (
            self._window_start is not None
            and (moment - self._window_start).total_seconds() >= self._report_interval
        ):
            return self._flush(moment)
        return []

    def stop(self) -> None:
        self._current = None
        self._last_sample = None
        self._window_start = None
        self._seconds = 0.0
        self._samples = 0


class SessionCollector(Collector):
    """Observe workstation lock/unlock transitions for the input desktop."""

    name = "session"

    def __init__(
        self,
        provider: Callable[[], Optional[str]] = get_session_state,
    ):
        super().__init__()
        self._provider = provider
        self._last: Optional[str] = None

    def collect(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        moment = _as_utc(now)
        try:
            state = self._provider()
        except Exception as exc:
            self.last_error = f"Session state unavailable: {type(exc).__name__}"
            return []
        if state not in {"locked", "unlocked"}:
            return []
        previous = self._last
        if previous is None:
            self._last = state
            return []
        if state == previous:
            return []
        self._last = state
        event_type = "session.locked" if state == "locked" else "session.unlocked"
        return [
            make_event(
                event_type,
                "SESSION",
                resource_name="workstation",
                metadata={"state": state, "collector": self.name},
                timestamp=moment,
            )
        ]

    def stop(self) -> None:
        self._last = None


class FailedLoginCollector(Collector):
    """Observe Windows Security event 4625 (failed logon) metadata.

    Reading the Security log normally requires an elevated context. When it is
    unavailable the collector disables itself and reports the reason instead of
    synthesising failed-login events.
    """

    name = "failed_login"

    def __init__(
        self,
        reader: Callable[..., List[Dict[str, Any]]] = read_failed_logins,
        lookback_seconds: int = 300,
    ):
        super().__init__()
        self._reader = reader
        self._lookback = max(60, int(lookback_seconds))
        self._last_check = _now() - timedelta(seconds=self._lookback)
        self._seen: Deque[str] = deque(maxlen=2000)

    def start(self) -> None:
        # Probe immediately so an unelevated agent reports a clear status.
        try:
            self._reader(self._last_check, limit=1)
        except PermissionError as exc:
            self.disable(
                "Security event log is not accessible; run the agent elevated to "
                f"enable failed-login monitoring ({type(exc).__name__})"
            )
        except Exception as exc:
            self.disable(f"Failed-login monitor unavailable: {type(exc).__name__}")

    def collect(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        moment = _as_utc(now)
        try:
            rows = self._reader(self._last_check, limit=50)
        except PermissionError:
            self.disable("Security event log access was lost")
            return []
        except Exception as exc:
            self.last_error = f"Failed-login read failed: {type(exc).__name__}"
            return []

        newest = self._last_check
        events: List[Dict[str, Any]] = []
        for row in rows:
            timestamp = row.get("timestamp") if isinstance(row, dict) else None
            parsed = self._last_check
            if timestamp:
                try:
                    parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    parsed = parsed.astimezone(timezone.utc)
                except ValueError:
                    parsed = moment
            account = _clean_name(row.get("account") or "unknown", 128) or "unknown"
            key = "|".join(
                str(row.get(field) or "")
                for field in ("timestamp", "account", "logon_type", "ip_address", "status", "sub_status")
            )
            if key in self._seen:
                continue
            self._seen.append(key)
            newest = max(newest, parsed)
            events.append(
                make_event(
                    "failed_login.observed",
                    "ACCESS",
                    resource_name=account,
                    metadata={
                        "account": account,
                        "logon_type": _clean_name(row.get("logon_type"), 16),
                        "ip_address": _clean_name(row.get("ip_address"), 64),
                        "status": _clean_name(row.get("status"), 32),
                        "sub_status": _clean_name(row.get("sub_status"), 32),
                        "detection_source": "windows_security_4625",
                        "collector": self.name,
                    },
                    timestamp=min(parsed, moment),
                )
            )
        self._last_check = max(newest, moment - timedelta(days=1))
        return events

    def stop(self) -> None:
        self._seen.clear()


class FileCollector(Collector):
    """Observe file metadata inside configured directories.

    Uses ``watchdog`` when available and falls back to a bounded polling
    snapshot. Directory trees, file names and sizes are observed; file contents
    are never opened or transmitted. This is not global file-access visibility.
    """

    name = "file"

    _IGNORED_SUFFIXES = {".tmp", ".part", ".crdownload", ".partial", ".lock"}
    _IGNORED_PREFIXES = ("~$", ".~")

    def __init__(
        self,
        watch_dirs: Iterable[Path],
        state_dir: Optional[Path] = None,
        debounce_seconds: float = 2.0,
        max_events_per_poll: int = 100,
        recursive: bool = True,
        max_scanned_files: int = 10000,
    ):
        super().__init__()
        self._watch_dirs = [Path(path) for path in watch_dirs]
        self._state_dir = Path(state_dir).resolve() if state_dir else None
        self._debounce = max(0.0, float(debounce_seconds))
        self._max_events = max(1, int(max_events_per_poll))
        self._recursive = recursive
        self._max_scanned = max(100, int(max_scanned_files))
        self._queue: Deque[Dict[str, Any]] = deque(maxlen=DEFAULT_QUEUE_LIMIT)
        self._lock = threading.Lock()
        self._observer: Any = None
        self._mode: Optional[str] = None
        self._snapshot: Dict[str, Tuple[float, int]] = {}
        self._last_modified: Dict[str, float] = {}
        self._dropped = 0
        self._last_poll: Optional[datetime] = None

    def _is_candidate(self, path: Path) -> bool:
        if not path.name:
            return False
        if path.name.startswith(self._IGNORED_PREFIXES):
            return False
        if path.suffix.lower() in self._IGNORED_SUFFIXES:
            return False
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if self._state_dir and (resolved == self._state_dir or self._state_dir in resolved.parents):
            return False
        return True

    def _enqueue(self, event_type: str, path: Path, *, size: Optional[int] = None) -> None:
        if event_type not in {"file.created", "file.modified", "file.deleted"}:
            raise ValueError(f"Unsupported file event: {event_type}")
        if not self._is_candidate(path):
            return
        key = os.path.normcase(str(path))
        if event_type == "file.modified":
            now_mono = time.monotonic()
            previous = self._last_modified.get(key)
            if previous is not None and now_mono - previous < self._debounce:
                return
            self._last_modified[key] = now_mono
            if len(self._last_modified) > 5000:
                self._last_modified.clear()
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        metadata: Dict[str, Any] = {
            "extension": (path.suffix.lower()[:16] or None),
            "directory_name": (path.parent.name[:64] or None),
            "collector": self.name,
        }
        if size is not None and size >= 0:
            metadata["size_bytes"] = int(size)
        action = "DELETE" if event_type == "file.deleted" else "MODIFY"
        event = make_event(
            event_type,
            action,
            resource_id=f"file:{digest}",
            resource_name=path.name,
            metadata=metadata,
            timestamp=_now(),
        )
        with self._lock:
            if len(self._queue) >= self._queue.maxlen:
                self._dropped += 1
            self._queue.append(event)

    def _handle(self, event_type: str, source: str, destination: Optional[str] = None) -> None:
        """Map a watchdog event into one or more metadata events."""
        try:
            path = Path(source)
            if event_type in {"created", "modified"}:
                size = None
                try:
                    size = path.stat().st_size
                except OSError:
                    pass
                mapped = "file.created" if event_type == "created" else "file.modified"
                self._enqueue(mapped, path, size=size)
            elif event_type == "deleted":
                self._enqueue("file.deleted", path)
            elif event_type == "moved":
                self._enqueue("file.modified", path)
                if destination:
                    target = Path(destination)
                    size = None
                    try:
                        size = target.stat().st_size
                    except OSError:
                        pass
                    self._enqueue("file.created", target, size=size)
        except Exception as exc:  # pragma: no cover - defensive
            self.last_error = f"File event mapping failed: {type(exc).__name__}"

    def start(self) -> None:
        usable = []
        for directory in self._watch_dirs:
            try:
                if directory.is_dir() and directory.resolve() != self._state_dir:
                    usable.append(directory)
            except OSError:
                continue
        self._watch_dirs = usable
        if not usable:
            self.disable("No existing watch directories are configured")
            return
        if os.name != "nt":
            self.disable("File monitoring is implemented for Windows endpoints")
            return
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception:
            self._mode = "poll"
            self._snapshot = self._scan()
            self._last_poll = _now()
            logger.info("watchdog is not installed; using bounded file polling")
            return

        collector = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):  # type: ignore[override]
                if not event.is_directory:
                    collector._handle("created", event.src_path)

            def on_modified(self, event):  # type: ignore[override]
                if not event.is_directory:
                    collector._handle("modified", event.src_path)

            def on_deleted(self, event):  # type: ignore[override]
                if not event.is_directory:
                    collector._handle("deleted", event.src_path)

            def on_moved(self, event):  # type: ignore[override]
                if not event.is_directory:
                    collector._handle("moved", event.src_path, getattr(event, "dest_path", None))

        try:
            observer = Observer()
            handler = _Handler()
            for directory in usable:
                observer.schedule(handler, str(directory), recursive=self._recursive)
            observer.daemon = True
            observer.start()
        except Exception as exc:
            self._mode = "poll"
            self._snapshot = self._scan()
            self._last_poll = _now()
            logger.warning("watchdog could not start; using polling: %s", type(exc).__name__)
            return
        self._observer = observer
        self._mode = "watchdog"
        logger.info("File metadata monitoring active for %d director%s", len(usable), "y" if len(usable) == 1 else "ies")

    def _scan(self) -> Dict[str, Tuple[float, int]]:
        snapshot: Dict[str, Tuple[float, int]] = {}
        for directory in self._watch_dirs:
            if self._recursive:
                iterator = os.walk(directory)
            else:
                try:
                    iterator = [(str(directory), [], [entry.name for entry in os.scandir(directory) if entry.is_file()])]
                except OSError:
                    continue
            for root, _dirs, files in iterator:
                for name in files:
                    if len(snapshot) >= self._max_scanned:
                        return snapshot
                    path = Path(root) / name
                    if not self._is_candidate(path):
                        continue
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    snapshot[os.path.normcase(str(path))] = (stat.st_mtime, stat.st_size)
        return snapshot

    def collect(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        moment = _as_utc(now)
        if self._mode == "poll":
            self._poll(moment)
        with self._lock:
            drained = []
            while self._queue and len(drained) < self._max_events:
                drained.append(self._queue.popleft())
        return drained

    def _poll(self, moment: datetime) -> None:
        current = self._scan()
        for key, (mtime, size) in current.items():
            previous = self._snapshot.get(key)
            path = Path(key)
            if previous is None:
                self._enqueue("file.created", path, size=size)
            elif previous[0] != mtime or previous[1] != size:
                self._enqueue("file.modified", path, size=size)
        for key in self._snapshot:
            if key not in current:
                self._enqueue("file.deleted", Path(key))
        self._snapshot = current
        self._last_poll = moment

    def stop(self) -> None:
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:  # pragma: no cover - defensive
                pass
            self._observer = None
        with self._lock:
            self._queue.clear()
        self._snapshot.clear()
        self._last_modified.clear()

    def status(self) -> Dict[str, Any]:
        data = super().status()
        data.update(
            {
                "mode": self._mode,
                "watch_directory_count": len(self._watch_dirs),
                "queued": len(self._queue),
                "dropped": self._dropped,
            }
        )
        return data
