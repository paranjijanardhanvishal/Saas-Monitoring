"""Modular Slack and Jira integration tests. No external network calls are made."""

from unittest.mock import Mock
import pytest

from app.integrations import alerts as integrations
from app.services import jira as jira_service
from app.services import slack as slack_service
from app.services.alerts import create_alerts_from_risk, ensure_incident_for_alert


def test_unconfigured_integrations_are_skipped(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("JIRA_API_URL", raising=False)
    monkeypatch.delenv("JIRA_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    assert integrations.send_slack_alert({}, {}) == "skipped_not_configured"
    assert integrations.create_jira_ticket({}, {}) == "skipped_not_configured"
    assert not slack_service.is_slack_configured()
    assert not jira_service.is_jira_configured()
    assert slack_service.get_slack_status()["status"] == "not_configured"
    assert jira_service.get_jira_status()["status"] == "not_configured"


def test_insecure_urls_are_refused(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "http://insecure.example/hook")
    monkeypatch.setenv("JIRA_API_URL", "http://insecure.example/api")
    monkeypatch.setenv("JIRA_AUTH_TOKEN", "token")
    assert integrations.send_slack_alert({}, {}) == "skipped_insecure_url"
    assert integrations.create_jira_ticket({}, {}) == "skipped_insecure_url"


def test_configured_integrations_use_tls_validation(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/services/x")
    monkeypatch.setenv("JIRA_API_URL", "https://jira.example/rest/api/2/issue")
    monkeypatch.setenv("JIRA_AUTH_TOKEN", "token")

    response = Mock()
    response.raise_for_status = Mock()
    response.content = b'{"key": "SEC-101"}'
    response.json = Mock(return_value={"key": "SEC-101"})
    post = Mock(return_value=response)
    monkeypatch.setattr(integrations.requests, "post", post)

    risk = {
        "risk_category": "HIGH",
        "user_id": "u1",
        "event_id": "e1",
        "combined_score": 85,
        "explanation": ["reason"],
    }
    assert integrations.send_slack_alert(risk, {"action_taken": "WARN"}) == "sent"
    assert integrations.create_jira_ticket(risk, {"action_taken": "WARN"}) == "sent"
    assert post.call_count == 2
    for call in post.call_args_list:
        assert call.kwargs["verify"] is True


def test_slack_filters_low_severity(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/services/x")
    res = slack_service.send_slack_notification({"severity": "LOW", "user_id": "u1"})
    assert res == "skipped_low_severity"
    res = slack_service.send_slack_notification({"risk_category": "MEDIUM", "user_id": "u1"})
    assert res == "skipped_low_severity"


def test_jira_filters_low_severity(monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    status, key = jira_service.create_jira_issue({"severity": "LOW", "user_id": "u1"})
    assert status == "skipped_low_severity"
    assert key is None


def test_jira_supports_basic_auth_with_email(monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example")
    monkeypatch.setenv("JIRA_EMAIL", "admin@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "secret-token")
    monkeypatch.setenv("JIRA_PROJECT_KEY", "SEC")

    response = Mock()
    response.raise_for_status = Mock()
    response.content = b'{"key": "SEC-99"}'
    response.json = Mock(return_value={"key": "SEC-99"})
    post = Mock(return_value=response)
    monkeypatch.setattr(jira_service.requests, "post", post)

    status, key = jira_service.create_jira_issue({
        "severity": "CRITICAL",
        "user_id": "analyst-1",
        "title": "Data Leakage",
        "combined_score": 92.5,
    })
    assert status == "sent"
    assert key == "SEC-99"
    headers = post.call_args.kwargs["headers"]
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")
    payload = post.call_args.kwargs["json"]
    assert payload["fields"]["project"]["key"] == "SEC"


def test_slack_and_jira_error_handling(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/services/x")
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example")
    monkeypatch.setenv("JIRA_API_TOKEN", "secret-token")

    post_fail = Mock(side_effect=Exception("Connection timed out"))
    monkeypatch.setattr(slack_service.requests, "post", post_fail)
    monkeypatch.setattr(jira_service.requests, "post", post_fail)

    slack_res = slack_service.send_slack_notification({"severity": "CRITICAL", "user_id": "u1"})
    assert slack_res == "failed"
    assert slack_service.get_slack_status()["status"] == "failed"

    jira_status, key = jira_service.create_jira_issue({"severity": "CRITICAL", "user_id": "u1"})
    assert jira_status == "failed"
    assert key is None
    assert jira_service.get_jira_status()["status"] == "failed"


@pytest.mark.asyncio
async def test_alert_pipeline_slack_and_jira_integration(db, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/services/x")
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example")
    monkeypatch.setenv("JIRA_API_TOKEN", "secret-token")

    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.content = b'{"key": "SEC-777"}'
    mock_resp.json = Mock(return_value={"key": "SEC-777"})
    post = Mock(return_value=mock_resp)
    monkeypatch.setattr(slack_service.requests, "post", post)
    monkeypatch.setattr(jira_service.requests, "post", post)

    assessment = {
        "risk_id": "risk-integ-001",
        "user_id": "pipeline-user",
        "event_id": "event-integ-001",
        "risk_category": "CRITICAL",
        "combined_score": 96.0,
        "privacy_score": 90.0,
        "behavioral_score": 85.0,
        "endpoint_score": 75.0,
        "risk_factors": ["HIGH_SENSITIVITY_PII"],
        "explanation": ["Exfiltration risk"],
    }

    alerts = await create_alerts_from_risk(db, assessment)
    assert len(alerts) == 1
    assert alerts[0]["slack_delivery"] == "sent"
    assert alerts[0]["slack_sent_at"] is not None

    incidents = await db.incidents.find({"user_id": "pipeline-user"}).to_list(length=10)
    assert len(incidents) == 1
    assert incidents[0]["jira_delivery"] == "sent"
    assert incidents[0]["jira_issue_key"] == "SEC-777"

    # Second call for the same assessment: deduplication prevents duplicate notifications
    initial_call_count = post.call_count
    await create_alerts_from_risk(db, assessment)
    # The duplicate alert was returned from DB without re-posting to Slack/Jira
    assert post.call_count == initial_call_count


@pytest.mark.asyncio
async def test_pipeline_resilient_to_integration_failure(db, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/services/x")
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example")
    monkeypatch.setenv("JIRA_API_TOKEN", "secret-token")

    post_fail = Mock(side_effect=Exception("Network drop"))
    monkeypatch.setattr(slack_service.requests, "post", post_fail)
    monkeypatch.setattr(jira_service.requests, "post", post_fail)

    assessment = {
        "risk_id": "risk-fail-001",
        "user_id": "fail-user",
        "event_id": "event-fail-001",
        "risk_category": "CRITICAL",
        "combined_score": 98.0,
        "explanation": ["Critical violation"],
    }

    # Pipeline MUST NOT raise; alert and incident documents must still be persisted
    alerts = await create_alerts_from_risk(db, assessment)
    assert len(alerts) == 1
    assert alerts[0]["slack_delivery"] == "failed"

    incidents = await db.incidents.find({"user_id": "fail-user"}).to_list(length=10)
    assert len(incidents) == 1
    assert incidents[0]["jira_delivery"] == "failed"
