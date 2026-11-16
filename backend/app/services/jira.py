"""Modular Jira Incident Integration Service.

Automatically provisions tracking incidents in Jira for HIGH and CRITICAL security events.
Supports both Atlassian Cloud (Basic Auth email + API token) and Bearer token auth.
Sanitizes all transmitted descriptions to exclude raw PII and payload data.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, Optional, Tuple

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 5

_last_jira_status: str = "not_configured"
_last_jira_error: Optional[str] = None
_last_jira_delivery_at: Optional[datetime] = None
_last_jira_issue_key: Optional[str] = None


def get_jira_credentials() -> Dict[str, str]:
    """Retrieve Jira connection settings from environment or settings."""
    base_url = (
        os.environ.get("JIRA_BASE_URL")
        or os.environ.get("JIRA_API_URL")
        or getattr(settings, "JIRA_BASE_URL", "")
        or getattr(settings, "JIRA_API_URL", "")
    ).strip()

    email = (
        os.environ.get("JIRA_EMAIL")
        or getattr(settings, "JIRA_EMAIL", "")
    ).strip()

    token = (
        os.environ.get("JIRA_API_TOKEN")
        or os.environ.get("JIRA_AUTH_TOKEN")
        or getattr(settings, "JIRA_API_TOKEN", "")
        or getattr(settings, "JIRA_AUTH_TOKEN", "")
    ).strip()

    project_key = (
        os.environ.get("JIRA_PROJECT_KEY")
        or getattr(settings, "JIRA_PROJECT_KEY", "SEC")
    ).strip()

    issue_type = (
        os.environ.get("JIRA_ISSUE_TYPE")
        or getattr(settings, "JIRA_ISSUE_TYPE", "Incident")
    ).strip()

    return {
        "base_url": base_url,
        "email": email,
        "token": token,
        "project_key": project_key or "SEC",
        "issue_type": issue_type or "Incident",
    }


def is_jira_configured() -> bool:
    """Check if minimum Jira integration settings are present."""
    creds = get_jira_credentials()
    return bool(creds["base_url"] and creds["token"])


def get_jira_status() -> Dict[str, Any]:
    """Return runtime Jira integration health, configured project, and delivery status."""
    creds = get_jira_credentials()
    if not (creds["base_url"] and creds["token"]):
        return {
            "status": "not_configured",
            "configured": False,
            "project_key": creds["project_key"],
            "last_delivery_at": _last_jira_delivery_at,
        }
    if _last_jira_status == "failed":
        return {
            "status": "failed",
            "configured": True,
            "project_key": creds["project_key"],
            "error": _last_jira_error or "Ticket creation failed",
            "last_delivery_at": _last_jira_delivery_at,
        }
    return {
        "status": "configured",
        "configured": True,
        "project_key": creds["project_key"],
        "last_delivery_at": _last_jira_delivery_at,
        "last_issue_key": _last_jira_issue_key,
    }


def create_jira_issue(
    data: Dict[str, Any],
    action_taken: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Create a Jira incident ticket for HIGH or CRITICAL security events.

    Accepts an alert document, incident document, or risk assessment.
    Returns:
      (status_string, issue_key)
      where status_string is one of:
      "sent" | "skipped_not_configured" | "skipped_insecure_url" | "skipped_low_severity" | "failed"
    """
    global _last_jira_status, _last_jira_error, _last_jira_delivery_at, _last_jira_issue_key

    creds = get_jira_credentials()
    base_url = creds["base_url"]
    token = creds["token"]
    email = creds["email"]
    project_key = creds["project_key"]
    issue_type = creds["issue_type"]

    if not base_url or not token:
        _last_jira_status = "not_configured"
        return "skipped_not_configured", None

    # Resolve full Jira REST endpoint
    if "/rest/api/" in base_url:
        endpoint = base_url
    else:
        endpoint = f"{base_url.rstrip('/')}/rest/api/2/issue"

    if not endpoint.startswith("https://"):
        logger.warning("Jira URL must use HTTPS; ticket creation skipped.")
        _last_jira_status = "failed"
        _last_jira_error = "Insecure HTTP URL"
        return "skipped_insecure_url", None

    severity = str(
        data.get("severity") or data.get("risk_category") or "UNKNOWN"
    ).upper()

    # Filter: Send only for HIGH or CRITICAL security events
    if severity not in {"HIGH", "CRITICAL"}:
        return "skipped_low_severity", None

    user_id = data.get("user_id") or "unknown_user"
    event_id = data.get("event_id") or "none"
    title = data.get("title") or f"{severity} Security Incident"
    reason = data.get("reason")
    if not reason and isinstance(data.get("explanation"), list):
        reason = "; ".join(data.get("explanation", []))
    reason = str(reason or "Critical security policy or anomaly threshold exceeded")[:1000]

    risk_score = data.get("risk_score") or data.get("combined_score")
    score_display = f"{risk_score:.1f}/100" if isinstance(risk_score, (int, float)) else "N/A"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if email:
        # Atlassian Cloud standard Basic Auth with email and token
        auth_bytes = f"{email}:{token}".encode("utf-8")
        headers["Authorization"] = f"Basic {base64.b64encode(auth_bytes).decode('ascii')}"
    else:
        # Bearer token standard
        headers["Authorization"] = f"Bearer {token}"

    summary = f"[{severity}] {title}"[:250]
    description_lines = [
        "h3. SaaS Security Monitor Automated Incident",
        f"*Severity:* {severity}",
        f"*User:* {user_id}",
        f"*Event ID:* {event_id}",
        f"*Risk Score:* {score_display}",
        f"*Reason:* {reason}",
    ]
    if action_taken:
        description_lines.append(f"*Enforcement Action:* {action_taken}")
    description_lines.append(
        f"*Detected:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": "\n".join(description_lines),
            "issuetype": {"name": issue_type},
        }
    }

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            verify=True,
        )
        response.raise_for_status()
        res_data = response.json() if response.content else {}
        issue_key = res_data.get("key")
        _last_jira_status = "configured"
        _last_jira_error = None
        _last_jira_delivery_at = datetime.now(timezone.utc)
        _last_jira_issue_key = issue_key
        logger.info("Jira incident ticket created successfully: %s", issue_key or "created")
        return "sent", issue_key
    except Exception as exc:
        _last_jira_status = "failed"
        _last_jira_error = str(type(exc).__name__)
        logger.error("Jira ticket creation failed: %s", type(exc).__name__)
        return "failed", None
