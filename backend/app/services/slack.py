"""Modular Slack Notification Service.

Sends formatted security alert notifications to a configured Slack incoming webhook
for HIGH and CRITICAL security events. Adheres to IEEE base paper privacy constraints
by transmitting derived metadata only, never raw PII or intercept content.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, Optional

import requests

from app.core.config import settings
from app.services.sanitizer import sanitize_for_external

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 5

_last_slack_status: str = "not_configured"
_last_slack_error: Optional[str] = None
_last_slack_delivery_at: Optional[datetime] = None


def get_slack_webhook_url() -> str:
    """Resolve Slack webhook URL from environment or settings."""
    if "SLACK_WEBHOOK_URL" in os.environ:
        return os.environ["SLACK_WEBHOOK_URL"].strip()
    return getattr(settings, "SLACK_WEBHOOK_URL", "").strip()


def is_slack_configured() -> bool:
    """Check if Slack incoming webhook is configured."""
    return bool(get_slack_webhook_url())


def get_slack_status() -> Dict[str, Any]:
    """Return runtime Slack integration health and delivery status."""
    url = get_slack_webhook_url()
    if not url:
        return {
            "status": "not_configured",
            "state": "NOT CONFIGURED",
            "configured": False,
            "last_delivery_at": _last_slack_delivery_at,
        }
    if _last_slack_status == "failed":
        return {
            "status": "failed",
            "state": "ERROR",
            "configured": True,
            "error": _last_slack_error or "Delivery failed",
            "last_delivery_at": _last_slack_delivery_at,
        }
    return {
        "status": "configured",
        "state": "CONFIGURED",
        "configured": True,
        "last_delivery_at": _last_slack_delivery_at,
    }


def send_slack_notification(
    data: Dict[str, Any],
    action_taken: Optional[str] = None,
    response_status: Optional[str] = None,
) -> str:
    """Send formatted Slack alert for HIGH or CRITICAL security events.

    Accepts an alert document or risk assessment dictionary.
    Returns:
      "sent" | "skipped_not_configured" | "skipped_insecure_url" | "skipped_low_severity" | "skipped_already_sent" | "failed"
    """
    global _last_slack_status, _last_slack_error, _last_slack_delivery_at

    # Deduplication check: prevent duplicate notifications for already dispatched alerts
    if data.get("slack_delivery") == "sent":
        return "skipped_already_sent"

    url = get_slack_webhook_url()
    if not url:
        _last_slack_status = "not_configured"
        return "skipped_not_configured"

    if not url.startswith("https://"):
        logger.warning("SLACK_WEBHOOK_URL must use HTTPS; notification skipped.")
        _last_slack_status = "failed"
        _last_slack_error = "Insecure HTTP URL"
        return "skipped_insecure_url"

    severity = str(
        data.get("severity") or data.get("risk_category") or "UNKNOWN"
    ).upper()

    # Filter: Send only for HIGH or CRITICAL security events
    if severity not in {"HIGH", "CRITICAL"}:
        return "skipped_low_severity"

    user_id = sanitize_for_external(data.get("user_id") or "unknown_user", max_length=64)
    event_id = sanitize_for_external(data.get("event_id") or "none", max_length=64)
    title = sanitize_for_external(data.get("title") or f"{severity} Risk Alert", max_length=150)
    raw_reason = data.get("reason")
    if not raw_reason and isinstance(data.get("explanation"), list):
        raw_reason = "; ".join(data.get("explanation", []))
    reason = sanitize_for_external(raw_reason or "Policy violation or anomaly threshold exceeded", max_length=300)

    risk_score = data.get("risk_score") or data.get("combined_score")
    score_display = f"{risk_score:.1f}/100" if isinstance(risk_score, (int, float)) else "N/A"

    fields_text = [
        f"*User:* `{user_id}`",
        f"*Severity:* `{severity}`",
        f"*Risk Score:* `{score_display}`",
        f"*Event ID:* `{event_id}`",
    ]
    if action_taken:
        clean_action = sanitize_for_external(action_taken, max_length=64)
        status_suffix = f" ({sanitize_for_external(response_status, max_length=32)})" if response_status else ""
        fields_text.append(f"*Action Taken:* `{clean_action}{status_suffix}`")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 Security Alert: {severity} Risk Detected",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}*\n{reason}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(fields_text),
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"SaaS Security Monitor · Automated Alert · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                }
            ],
        },
    ]

    payload = {
        "text": f"🚨 Security Alert: {severity} risk detected for user {user_id}",
        "blocks": blocks,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
            verify=True,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        _last_slack_status = "configured"
        _last_slack_error = None
        _last_slack_delivery_at = datetime.now(timezone.utc)
        logger.info("Slack alert successfully delivered for event %s (severity: %s)", event_id, severity)
        return "sent"
    except Exception as exc:
        _last_slack_status = "failed"
        _last_slack_error = str(type(exc).__name__)
        logger.error("Slack alert delivery failed for event %s: %s", event_id, type(exc).__name__)
        return "failed"
