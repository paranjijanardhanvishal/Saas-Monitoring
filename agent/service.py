"""Agent service loop.

Coordinates enrollment, heartbeats, collectors, batching and consent
transitions. The service only sends metadata events and never accepts a
user-supplied identity. On consent withdrawal it stops collecting and clears
any buffered events; on credential revocation it exits and requires explicit
re-enrollment.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from .client import (
    MAX_BATCHES,
    AgentAuthError,
    AgentClient,
    AgentError,
    AgentTransportError,
)
from .collectors import Collector, build_collectors, make_event
from .config import AGENT_VERSION, AgentConfig, os_version_string, stable_device_id
from .storage import StateError, StateStore

logger = logging.getLogger(__name__)

MAX_QUEUE = 5000


@dataclass
class ServiceStats:
    collected: int = 0
    accepted: int = 0
    duplicates: int = 0
    rejected: int = 0
    dropped: int = 0
    send_failures: int = 0
    heartbeats: int = 0
    last_heartbeat: Optional[str] = None
    last_event_at: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "collected": self.collected,
            "accepted": self.accepted,
            "duplicates": self.duplicates,
            "rejected": self.rejected,
            "dropped": self.dropped,
            "send_failures": self.send_failures,
            "heartbeats": self.heartbeats,
            "last_heartbeat": self.last_heartbeat,
            "last_event_at": self.last_event_at,
        }


@dataclass
class ServiceResult:
    monitoring_active: bool
    enrolled: bool
    stats: Dict[str, Any] = field(default_factory=dict)
    collectors: List[Dict[str, Any]] = field(default_factory=list)


class AgentService:
    def __init__(
        self,
        config: AgentConfig,
        *,
        client: Optional[AgentClient] = None,
        store: Optional[StateStore] = None,
        collectors: Optional[List[Collector]] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        self.config = config
        self.store = store or StateStore(config.state_dir)
        self.client = client or AgentClient(config.backend_url)
        self.collectors = collectors if collectors is not None else build_collectors(config)
        self.stop_event = stop_event or threading.Event()
        self._queue: Deque[Dict[str, Any]] = deque(maxlen=MAX_QUEUE)
        self._collectors_started = False
        self._running = False
        self._enrolled = False
        self._device_id: Optional[str] = None
        self._monitoring_active = False
        self._lifecycle_started = False
        self.stats = ServiceStats()

    @property
    def monitoring_active(self) -> bool:
        return self._monitoring_active

    # ------------------------------------------------------------------
    # Enrollment / state
    # ------------------------------------------------------------------
    def prepare(self) -> Dict[str, Any]:
        """Load an existing device credential or enroll with a one-time token."""
        try:
            state = self.store.load()
        except StateError:
            raise
        if state:
            self.client.device_token = state["device_token"]
            self._device_id = state.get("device_id") or stable_device_id()
            self._enrolled = True
            logger.info("Using enrolled device credential for %s", self._device_id[:12])
            return state

        token = self.config.enrollment_token
        if not token:
            raise AgentError(
                "Device is not enrolled. Provide a one-time enrollment token with "
                "--token or AGENT_ENROLLMENT_TOKEN."
            )
        device_id = stable_device_id()
        hostname = socket.gethostname()
        version = os_version_string()
        data = self.client.enroll(
            token,
            device_id,
            hostname,
            version,
            AGENT_VERSION,
        )
        self.client.device_token = data["device_token"]
        state = {
            "device_token": data["device_token"],
            "device_id": data.get("device_id") or device_id,
            "user_id": data.get("user_id"),
            "hostname": hostname,
            "os_version": version,
            "agent_version": AGENT_VERSION,
            "backend_url": self.config.backend_url,
            "enrolled_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store.save(state)
        self._device_id = state["device_id"]
        self._enrolled = True
        logger.info("Device enrolled successfully as %s", self._device_id[:12])
        return state

    def public_status(self) -> Dict[str, Any]:
        try:
            state = self.store.public_state()
            state_error = None
        except StateError as exc:
            state = {}
            state_error = str(exc)
        return {
            "agent_version": AGENT_VERSION,
            "state_dir": str(self.config.state_dir),
            "enrolled": bool(state),
            "state_error": state_error,
            "device": state,
            "backend_url": self.config.backend_url,
            "monitoring_active": self._monitoring_active,
            "queue_depth": len(self._queue),
            "stats": self.stats.as_dict(),
            "collectors": [collector.status() for collector in self.collectors],
        }

    # ------------------------------------------------------------------
    # Collectors
    # ------------------------------------------------------------------
    def start_collectors(self) -> None:
        if self._collectors_started:
            return
        for collector in self.collectors:
            try:
                collector.start()
            except Exception as exc:
                collector.disable(f"Collector start failed: {type(exc).__name__}")
            if not collector.enabled:
                logger.warning("Collector %s disabled: %s", collector.name, collector.last_error)
        self._collectors_started = True

    def stop_collectors(self) -> None:
        for collector in self.collectors:
            try:
                collector.stop()
            except Exception:
                logger.debug("Collector %s stop failed", collector.name, exc_info=True)
        self._collectors_started = False

    def _enqueue(self, events: List[Dict[str, Any]]) -> None:
        if not events:
            return
        capacity = self._queue.maxlen or MAX_QUEUE
        overflow = max(0, len(self._queue) + len(events) - capacity)
        if overflow:
            self.stats.dropped += overflow
            logger.warning("Event queue overflow; dropping %d oldest event(s)", overflow)
        self._queue.extend(events)
        self.stats.collected += len(events)

    def _emit_lifecycle(self, event_type: str) -> None:
        try:
            self._enqueue(
                [
                    make_event(
                        event_type,
                        "SYSTEM",
                        resource_name="workstation",
                        metadata={
                            "agent_version": AGENT_VERSION,
                            "os_version": os_version_string()[:200],
                            "collector": "service",
                        },
                    )
                ]
            )
        except Exception:
            logger.debug("Could not enqueue lifecycle event", exc_info=True)

    def poll(self, now: Optional[datetime] = None) -> int:
        """Run every enabled collector once and buffer resulting events."""
        moment = now or datetime.now(timezone.utc)
        if not self._monitoring_active:
            return 0
        total = 0
        for collector in self.collectors:
            if not collector.enabled:
                continue
            try:
                events = collector.collect(moment) or []
            except Exception as exc:
                collector.last_error = f"Collection failed: {type(exc).__name__}"
                logger.warning("Collector %s failed: %s", collector.name, type(exc).__name__)
                self._enqueue(
                    [
                        make_event(
                            "agent.error",
                            "SYSTEM",
                            resource_name=collector.name,
                            metadata={
                                "collector": collector.name,
                                "error": type(exc).__name__,
                            },
                            timestamp=moment,
                        )
                    ]
                )
                continue
            if events:
                self._enqueue(events)
                total += len(events)
        return total

    # ------------------------------------------------------------------
    # Network operations
    # ------------------------------------------------------------------
    def heartbeat(self) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.heartbeat(
                socket.gethostname(),
                os_version_string(),
                AGENT_VERSION,
                monitoring_active=self._monitoring_active,
            )
        except AgentAuthError as exc:
            self._monitoring_active = False
            logger.error(
                "Device credential rejected (HTTP %s); monitoring stopped. Re-enroll the device.",
                exc.status_code,
            )
            raise
        except AgentTransportError as exc:
            logger.warning("Heartbeat failed: %s", exc)
            return None

        self.stats.heartbeats += 1
        self.stats.last_heartbeat = datetime.now(timezone.utc).isoformat()
        enabled = bool(response.get("monitoring_enabled"))
        if enabled and not self._monitoring_active:
            self._monitoring_active = True
            self.start_collectors()
            logger.info("Monitoring enabled by server consent; collection active")
        elif not enabled and self._monitoring_active:
            self._monitoring_active = False
            self._queue.clear()
            self.stop_collectors()
            logger.warning("Monitoring paused by server (consent not granted); buffered events cleared")
        elif not enabled:
            self._monitoring_active = False
            self._queue.clear()
        return response

    def flush(self) -> bool:
        """Send buffered events in bounded batches. Returns True if fully flushed."""
        if not self._queue:
            return True
        batches = 0
        while self._queue and batches < MAX_BATCHES:
            batch_size = min(len(self._queue), max(1, int(self.config.event_batch_size)))
            batch = [self._queue.popleft() for _ in range(batch_size)]
            try:
                result = self.client.send_events(batch)
            except AgentAuthError as exc:
                # Put the batch back only if this is a recoverable transport
                # condition; auth failures are terminal or consent-related.
                if exc.status_code == 401:
                    logger.error("Device credential rejected while sending events; stopping")
                    raise
                self._monitoring_active = False
                self._queue.clear()
                self.stop_collectors()
                logger.warning("Event ingestion rejected (HTTP 403); monitoring paused until consent/account is restored")
                return False
            except AgentTransportError as exc:
                for event in reversed(batch):
                    self._queue.appendleft(event)
                self.stats.send_failures += 1
                logger.warning("Could not send event batch: %s", exc)
                return False
            accepted = int(result.get("accepted") or 0)
            duplicates = int(result.get("duplicates") or 0)
            rejected = result.get("rejected") or []
            self.stats.accepted += accepted
            self.stats.duplicates += duplicates
            self.stats.rejected += len(rejected)
            if accepted:
                self.stats.last_event_at = datetime.now(timezone.utc).isoformat()
            batches += 1
        return not self._queue

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run_once(self) -> ServiceResult:
        """Heartbeat once, poll all collectors, flush once. Used for diagnostics.

        A rejected device credential (HTTP 401) is terminal and propagates so
        the CLI can exit non-zero and the operator knows to re-enroll. A 403
        consent/account condition is handled as a pause by :meth:`flush`.
        """
        self.prepare()
        self.heartbeat()
        if self._monitoring_active:
            self.start_collectors()
            self.poll()
            self.flush()
        return ServiceResult(
            monitoring_active=self._monitoring_active,
            enrolled=self._enrolled,
            stats=self.stats.as_dict(),
            collectors=[collector.status() for collector in self.collectors],
        )

    def run(self, max_seconds: Optional[float] = None) -> ServiceResult:
        self.prepare()
        self._running = True
        started = time.monotonic()
        last_heartbeat = 0.0
        next_poll = started
        last_flush = started
        heartbeat_interval = max(10, int(self.config.heartbeat_interval))
        poll_interval = max(1, int(self.config.poll_interval))
        flush_interval = max(1, min(5, poll_interval))
        fatal: Optional[BaseException] = None

        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                if max_seconds is not None and now - started >= max_seconds:
                    break
                if now - last_heartbeat >= heartbeat_interval:
                    try:
                        self.heartbeat()
                    except AgentAuthError as exc:
                        fatal = exc
                        break
                    last_heartbeat = time.monotonic()
                    if self._monitoring_active and not self._lifecycle_started:
                        self._emit_lifecycle("system.started")
                        self._lifecycle_started = True

                if self._monitoring_active and now >= next_poll:
                    self.poll()
                    next_poll = time.monotonic() + poll_interval

                if self._monitoring_active and (
                    len(self._queue) >= max(1, int(self.config.event_batch_size))
                    or time.monotonic() - last_flush >= flush_interval
                ):
                    try:
                        self.flush()
                    except AgentAuthError:
                        break
                    last_flush = time.monotonic()

                self.stop_event.wait(timeout=0.5)
        except AgentError as exc:
            fatal = exc
            logger.error("Agent service stopped: %s", exc)
        finally:
            self._running = False
            if self._lifecycle_started and self._monitoring_active:
                self._emit_lifecycle("system.stopping")
                try:
                    self.flush()
                except (AgentAuthError, AgentError):
                    pass
            self.stop_collectors()
            try:
                self.client.close()
            except Exception:
                pass
        if fatal:
            raise fatal
        return ServiceResult(
            monitoring_active=self._monitoring_active,
            enrolled=self._enrolled,
            stats=self.stats.as_dict(),
            collectors=[collector.status() for collector in self.collectors],
        )
