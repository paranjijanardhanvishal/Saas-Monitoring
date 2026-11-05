"""Server-side derivation of endpoint and SaaS access-pattern risk signals.

Clients cannot submit these numbers. Weights are documented prototype policy
values, not learned model outputs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

ENDPOINT_EVENT_WEIGHTS = {
    "file.deleted": 45,
    "file.download_observed": 35,
    "file.created": 10,
    "file.modified": 20,
    "file.access_observed": 20,
    "failed_login.observed": 70,
    "process.started": 5,
    "process.stopped": 3,
    "application.foreground_changed": 4,
    "session.locked": 2,
    "session.unlocked": 2,
    "system.started": 3,
    "system.stopping": 1,
    "system.resumed": 2,
    "application.usage": 5,
}

SENSITIVE_EXTENSIONS = {
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".csv",
    ".key", ".pem", ".pfx", ".p12", ".sql", ".bak", ".zip",
}

SAAS_ACTION_WEIGHTS = {
    "PERMISSION_CHANGE": 80,
    "SHARE": 65,
    "DELETE": 55,
    "DOWNLOAD": 40,
    "UPLOAD": 35,
    "MODIFY": 20,
    "ACCESS": 10,
}


def _extension(filename: Optional[str]) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def endpoint_signal_for_event(event: dict[str, Any]) -> float:
    score = float(ENDPOINT_EVENT_WEIGHTS.get(event.get("event_type", ""), 0))
    metadata = event.get("metadata") or {}
    if _extension(event.get("resource_name")) in SENSITIVE_EXTENSIONS:
        score += 15
    if metadata.get("outside_expected_hours"):
        score += 10
    if (event.get("application") or {}).get("name", "").lower() in {
        "powershell.exe", "cmd.exe", "wscript.exe", "cscript.exe", "psexec.exe"
    }:
        score += 10
    return min(100.0, score)


def access_signal_for_event(event: dict[str, Any]) -> float:
    source = event.get("source", "")
    if source != "saas_proxy":
        return 0.0
    return float(SAAS_ACTION_WEIGHTS.get(str(event.get("action", "")), 0))


async def recent_context_scores(
    db, user_id: str, event: Optional[dict[str, Any]] = None, lookback_minutes: int = 60
) -> tuple[Optional[float], Optional[float]]:
    """Return max endpoint/access signals from recent attributed events.

    A signal is ``None`` when no telemetry of that kind exists for the user.
    Absence of endpoint telemetry is not the same as a measured endpoint score
    of zero, and an unattributed SaaS proxy event is not evidence about this
    user's access patterns. Callers renormalise the documented weights over
    the signals that are actually available.
    """
    endpoint: Optional[float] = None
    access: Optional[float] = None

    def observe(item: dict[str, Any]) -> None:
        nonlocal endpoint, access
        source = item.get("source")
        if source == "saas_proxy":
            access = max(access or 0.0, access_signal_for_event(item))
        elif source == "endpoint_agent":
            endpoint = max(endpoint or 0.0, endpoint_signal_for_event(item))

    if event:
        observe(event)
    if db is None:
        return endpoint, access
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    try:
        cursor = (
            db.events.find({"user_id": user_id, "timestamp": {"$gte": cutoff}})
            .sort("timestamp", -1)
            .limit(100)
        )
        recent = await cursor.to_list(length=100)
    except Exception:
        return endpoint, access
    for item in recent:
        observe(item)
    return (
        min(100.0, endpoint) if endpoint is not None else None,
        min(100.0, access) if access is not None else None,
    )
