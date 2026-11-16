"""Modular Slack/Jira notifications and ticket creation.

Integrations are disabled unless the required environment variables are set.
Nothing is reported as delivered when no endpoint is configured.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

from app.services.jira import (
    create_jira_issue,
    get_jira_status,
    is_jira_configured as _jira_configured_svc,
)
from app.services.slack import (
    get_slack_status,
    is_slack_configured as _slack_configured_svc,
    send_slack_notification,
)

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 5


def _slack_configured() -> bool:
    return _slack_configured_svc()


def _jira_configured() -> bool:
    return _jira_configured_svc()


def send_slack_alert(risk_assessment: dict, response_model: dict = None) -> str:
    action_taken = response_model.get("action_taken") if isinstance(response_model, dict) else None
    response_status = response_model.get("response_status") if isinstance(response_model, dict) else None
    return send_slack_notification(
        risk_assessment,
        action_taken=action_taken,
        response_status=response_status,
    )


def create_jira_ticket(risk_assessment: dict, response_model: dict = None) -> str:
    action_taken = response_model.get("action_taken") if isinstance(response_model, dict) else None
    status, _ = create_jira_issue(
        risk_assessment,
        action_taken=action_taken,
    )
    return status
