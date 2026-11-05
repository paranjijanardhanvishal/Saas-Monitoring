"""Optional Slack/Jira notifications.

Integrations are disabled unless the required environment variables are set.
Nothing is reported as delivered when no endpoint is configured.
"""

import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 5


def _slack_configured() -> bool:
    return bool(os.getenv("SLACK_WEBHOOK_URL", "").strip())


def _jira_configured() -> bool:
    return bool(
        os.getenv("JIRA_API_URL", "").strip()
        and os.getenv("JIRA_AUTH_TOKEN", "").strip()
    )


def send_slack_alert(risk_assessment: dict, response_model: dict) -> str:
    if not _slack_configured():
        return "skipped_not_configured"

    webhook = os.environ["SLACK_WEBHOOK_URL"].strip()
    if not webhook.startswith("https://"):
        logger.warning("SLACK_WEBHOOK_URL must use HTTPS; notification skipped")
        return "skipped_insecure_url"

    payload = {
        "text": f"Security alert: {risk_assessment.get('risk_category')} risk detected",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Security Alert: {risk_assessment.get('risk_category')} Risk Detected*\n\n"
                        f"*User:* {risk_assessment.get('user_id')}\n"
                        f"*Event ID:* {risk_assessment.get('event_id')}\n"
                        f"*Combined Score:* {risk_assessment.get('combined_score')}\n"
                        f"*Action Taken:* {response_model.get('action_taken')} "
                        f"({response_model.get('response_status')})\n\n"
                        f"*Explanations:* {', '.join(risk_assessment.get('explanation', []))}"
                    ),
                },
            }
        ],
    }
    try:
        response = requests.post(webhook, json=payload, timeout=REQUEST_TIMEOUT_SECONDS, verify=True)
        response.raise_for_status()
        return "sent"
    except requests.RequestException as exc:
        logger.error("Slack notification failed: %s", type(exc).__name__)
        return "failed"


def create_jira_ticket(risk_assessment: dict, response_model: dict) -> str:
    if not _jira_configured():
        return "skipped_not_configured"

    api_url = os.environ["JIRA_API_URL"].strip()
    token = os.environ["JIRA_AUTH_TOKEN"].strip()
    if not api_url.startswith("https://"):
        logger.warning("JIRA_API_URL must use HTTPS; ticket creation skipped")
        return "skipped_insecure_url"

    payload: Dict[str, Any] = {
        "fields": {
            "project": {"key": os.getenv("JIRA_PROJECT_KEY", "SEC")},
            "summary": (
                f"Security Incident: {risk_assessment.get('risk_category')} risk "
                f"for {risk_assessment.get('user_id')}"
            ),
            "description": (
                f"Risk Score: {risk_assessment.get('combined_score')}\n"
                f"Action: {response_model.get('action_taken')}\n"
                f"Details: {', '.join(risk_assessment.get('explanation', []))}"
            ),
            "issuetype": {"name": os.getenv("JIRA_ISSUE_TYPE", "Incident")},
        }
    }
    try:
        response = requests.post(
            api_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
            verify=True,
        )
        response.raise_for_status()
        return "sent"
    except requests.RequestException as exc:
        logger.error("Jira ticket creation failed: %s", type(exc).__name__)
        return "failed"
