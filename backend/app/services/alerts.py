"""Alert and incident generation with deduplication and evidence linkage."""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

SEVERITY_BY_RISK = {
    "LOW": "LOW",
    "MEDIUM": "MEDIUM",
    "HIGH": "HIGH",
    "CRITICAL": "CRITICAL",
}


def _dedupe_key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


async def create_alert(
    db,
    *,
    severity: str,
    title: str,
    reason: str,
    user_id: Optional[str] = None,
    device_id: Optional[str] = None,
    saas_app: Optional[str] = None,
    resource_id: Optional[str] = None,
    event_id: Optional[str] = None,
    risk_id: Optional[str] = None,
    risk_score: Optional[float] = None,
    privacy_signal: Optional[float] = None,
    behavior_signal: Optional[float] = None,
    endpoint_signal: Optional[float] = None,
    source: str = "risk_engine",
    evidence: Optional[list[dict[str, Any]]] = None,
    dedupe_scope: Optional[str] = None,
) -> dict[str, Any]:
    """Create an alert exactly once per (user, event, rule).

    Returns the existing alert when the same deterministic key already exists.
    """
    now = datetime.now(timezone.utc)
    scope = dedupe_scope or event_id or risk_id or f"{now.date().isoformat()}"
    key = _dedupe_key(user_id or "unknown", scope, title, source)

    document = {
        "severity": severity,
        "title": title[:200],
        "user_id": user_id,
        "device_id": device_id,
        "saas_app": saas_app,
        "resource_id": resource_id,
        "reason": reason[:2000],
        "privacy_signal": privacy_signal,
        "behavior_signal": behavior_signal,
        "endpoint_signal": endpoint_signal,
        "risk_score": risk_score,
        "status": "OPEN",
        "source": source,
        "event_id": event_id,
        "risk_id": risk_id,
        "dedupe_key": key,
        "evidence": evidence or [],
        "history": [{"timestamp": now, "actor": "system", "action": "created"}],
        "timestamp": now,
        "updated_at": now,
        "acknowledged_at": None,
        "acknowledged_by": None,
    }
    try:
        result = await db.alerts.insert_one(document)
        document["_id"] = result.inserted_id
        return document
    except DuplicateKeyError:
        existing = await db.alerts.find_one({"dedupe_key": key})
        if existing:
            return existing
        raise


async def create_alerts_from_risk(db, assessment: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate alerts only for HIGH/CRITICAL risk assessments."""
    category = (assessment.get("risk_category") or "LOW").upper()
    if category not in {"HIGH", "CRITICAL"}:
        return []

    factors = assessment.get("risk_factors") or []
    title = f"{category.title()} risk activity detected"
    if "BEHAVIORAL_ANOMALY" in factors:
        title = f"{category.title()} behavioral anomaly detected"
    elif "HIGH_SENSITIVITY_PII" in factors:
        title = f"{category.title()} sensitive data exposure detected"

    explanation = assessment.get("explanation") or []
    reason = "; ".join(explanation) if explanation else "Combined risk threshold exceeded."

    evidence = [
        {
            "type": "risk_assessment",
            "risk_id": assessment.get("risk_id"),
            "event_id": assessment.get("event_id"),
            "combined_score": assessment.get("combined_score"),
            "risk_factors": factors,
        }
    ]

    alert = await create_alert(
        db,
        severity=SEVERITY_BY_RISK.get(category, "MEDIUM"),
        title=title,
        reason=reason,
        user_id=assessment.get("user_id"),
        saas_app=assessment.get("saas_app"),
        resource_id=assessment.get("resource_id"),
        event_id=assessment.get("event_id"),
        risk_id=assessment.get("risk_id"),
        risk_score=assessment.get("combined_score"),
        privacy_signal=assessment.get("privacy_score"),
        behavior_signal=assessment.get("behavioral_score"),
        endpoint_signal=assessment.get("endpoint_score"),
        source="risk_engine",
        evidence=evidence,
        dedupe_scope=assessment.get("event_id"),
    )

    if category == "CRITICAL":
        await ensure_incident_for_alert(db, alert)
    return [alert]


async def ensure_incident_for_alert(db, alert: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Attach a CRITICAL alert to an open incident, creating one if needed.

    Correlation is limited to the same user and a 24 hour window. No unrelated
    accounts are grouped.
    """
    user_id = alert.get("user_id")
    if not user_id:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    existing = await db.incidents.find_one(
        {
            "user_id": user_id,
            "status": {"$in": ["OPEN", "INVESTIGATING"]},
            "created_time": {"$gte": cutoff},
        },
        sort=[("created_time", -1)],
    )
    alert_id = str(alert.get("_id"))
    now = datetime.now(timezone.utc)
    if existing:
        await db.incidents.update_one(
            {"_id": existing["_id"]},
            {
                "$addToSet": {"related_alerts": alert_id},
                "$set": {"updated_at": now},
                "$push": {
                    "response_history": f"Linked alert {alert_id}",
                    "history": {
                        "timestamp": now,
                        "actor": "system",
                        "action": "alert_linked",
                        "detail": alert_id,
                    },
                },
            },
        )
        return existing

    document = {
        "title": f"Critical incident: {alert.get('title', 'security alert')}"[:200],
        "severity": "CRITICAL",
        "status": "OPEN",
        "user_id": user_id,
        "saas_app": alert.get("saas_app"),
        "resource_id": alert.get("resource_id"),
        "reason": alert.get("reason", "Critical alert requires investigation.")[:4000],
        "risk_score": alert.get("risk_score"),
        "related_alerts": [alert_id],
        "related_events": [alert.get("event_id")] if alert.get("event_id") else [],
        "assigned_to": None,
        "evidence": alert.get("evidence", []),
        "notes": [],
        "created_time": now,
        "updated_at": now,
        "response_history": ["Incident auto-created from critical alert"],
        "history": [
            {
                "timestamp": now,
                "actor": "system",
                "action": "created",
                "detail": f"Created from alert {alert_id}",
            }
        ],
    }
    result = await db.incidents.insert_one(document)
    document["_id"] = result.inserted_id
    return document
