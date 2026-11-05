"""Collector framework and safe event construction."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ALLOWED_EVENT_TYPES = {
    "process.started",
    "process.stopped",
    "application.foreground_changed",
    "application.usage",
    "session.locked",
    "session.unlocked",
    "session.logged_on",
    "session.logged_off",
    "system.started",
    "system.stopping",
    "system.suspended",
    "system.resumed",
    "file.created",
    "file.modified",
    "file.deleted",
    "file.download_observed",
    "file.access_observed",
    "failed_login.observed",
    "agent.error",
}

ALLOWED_ACTIONS = {
    "ACCESS",
    "DOWNLOAD",
    "UPLOAD",
    "MODIFY",
    "DELETE",
    "SHARE",
    "PERMISSION_CHANGE",
    "EXECUTE",
    "SESSION",
    "SYSTEM",
}

MAX_TEXT = 256


def _clean(value: Optional[str], limit: int = MAX_TEXT) -> Optional[str]:
    if value is None:
        return None
    text = str(value).replace("\x00", "").strip()
    return text[:limit] if text else None


def make_event(
    event_type: str,
    action: str,
    *,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    application: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an endpoint event accepted by the ingestion API.

    Only metadata is included. Callers must never put file contents, keystrokes,
    screenshots, clipboard data or credentials into ``metadata``.
    """
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event_type}")
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported action: {action}")
    moment = timestamp or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    payload: Dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "timestamp": moment.astimezone(timezone.utc).isoformat(),
        "action": action,
        "resource_id": _clean(resource_id),
        "resource_name": _clean(resource_name),
        "application": application or None,
        "metadata": metadata or {},
        "correlation_id": _clean(correlation_id, 128),
    }
    return payload


class Collector:
    """Base class for a best-effort endpoint collector."""

    name = "collector"

    def __init__(self) -> None:
        self.enabled = True
        self.last_error: Optional[str] = None

    def start(self) -> None:
        """Initialise state. Must not raise fatal errors for optional features."""

    def collect(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return []

    def stop(self) -> None:
        """Release resources."""

    def disable(self, reason: str) -> None:
        self.enabled = False
        self.last_error = reason
        logger.warning("%s disabled: %s", self.name, reason)

    def status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "last_error": self.last_error,
        }
