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


def test_slack_payload_pii_and_secret_redaction(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/services/secret-token")

    post_mock = Mock()
    post_mock.return_value.raise_for_status = Mock()
    monkeypatch.setattr(slack_service.requests, "post", post_mock)

    alert_with_secrets = {
        "severity": "CRITICAL",
        "user_id": "attacker@corp.internal",
        "title": "Exfiltration of user password=SuperSecret123! and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.test",
        "reason": "Exposed Card 4111-2222-3333-4444 and SSN 000-12-3456 with api_key: key_secret_998877",
        "combined_score": 99.0,
    }

    result = slack_service.send_slack_notification(alert_with_secrets)
    assert result == "sent"
    assert post_mock.call_count == 1
    payload = post_mock.call_args.kwargs["json"]

    payload_str = str(payload)
    # Assert raw PII and secrets are never in the payload
    assert "SuperSecret123!" not in payload_str
    assert "4111-2222-3333-4444" not in payload_str
    assert "000-12-3456" not in payload_str
    assert "key_secret_998877" not in payload_str
    assert "[CARD_REDACTED]" in payload_str
    assert "[SSN_REDACTED]" in payload_str
    assert "[REDACTED]" in payload_str


def test_jira_payload_pii_and_secret_redaction(monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example/rest/api/2/issue")
    monkeypatch.setenv("JIRA_API_TOKEN", "jira-secret")

    post_mock = Mock()
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.content = b'{"key": "SEC-888"}'
    resp.json = Mock(return_value={"key": "SEC-888"})
    post_mock.return_value = resp
    monkeypatch.setattr(jira_service.requests, "post", post_mock)

    incident_with_secrets = {
        "severity": "HIGH",
        "user_id": "analyst-02",
        "title": "Leak of access_token=secret_jwt_xyz and SSN 123-45-6789",
        "reason": "Credit card 5555 4444 3333 2222 used in test",
        "combined_score": 85.0,
    }

    status, key = jira_service.create_jira_issue(incident_with_secrets)
    assert status == "sent"
    assert key == "SEC-888"
    payload = post_mock.call_args.kwargs["json"]

    payload_str = str(payload)
    assert "secret_jwt_xyz" not in payload_str
    assert "123-45-6789" not in payload_str
    assert "5555 4444 3333 2222" not in payload_str
    assert "[CARD_REDACTED]" in payload_str
    assert "[SSN_REDACTED]" in payload_str


def test_duplicate_notification_prevention(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/services/x")
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")

    post = Mock()
    monkeypatch.setattr(slack_service.requests, "post", post)
    monkeypatch.setattr(jira_service.requests, "post", post)

    # Already sent Slack alert
    already_sent_alert = {"severity": "HIGH", "slack_delivery": "sent"}
    assert slack_service.send_slack_notification(already_sent_alert) == "skipped_already_sent"
    assert post.call_count == 0

    # Already created Jira incident
    already_sent_incident = {"severity": "CRITICAL", "jira_delivery": "sent", "jira_issue_key": "SEC-100"}
    status, key = jira_service.create_jira_issue(already_sent_incident)
    assert status == "skipped_already_sent"
    assert key == "SEC-100"
    assert post.call_count == 0


def test_system_health_integration_status_reporting(monkeypatch):
    # 1. Not configured
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_API_URL", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_AUTH_TOKEN", raising=False)

    slack_st = slack_service.get_slack_status()
    jira_st = jira_service.get_jira_status()
    assert slack_st["state"] == "NOT CONFIGURED"
    assert slack_st["configured"] is False
    assert jira_st["state"] == "NOT CONFIGURED"
    assert jira_st["configured"] is False

    # 2. Configured and operational
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/services/token")
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")

    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.content = b'{"key": "SEC-55"}'
    mock_resp.json = Mock(return_value={"key": "SEC-55"})
    post_mock = Mock(return_value=mock_resp)
    monkeypatch.setattr(slack_service.requests, "post", post_mock)
    monkeypatch.setattr(jira_service.requests, "post", post_mock)

    slack_service.send_slack_notification({"severity": "HIGH", "user_id": "u1"})
    jira_service.create_jira_issue({"severity": "HIGH", "user_id": "u1"})

    slack_st_ok = slack_service.get_slack_status()
    jira_st_ok = jira_service.get_jira_status()
    assert slack_st_ok["state"] == "CONFIGURED"
    assert slack_st_ok["configured"] is True
    assert slack_st_ok["last_delivery_at"] is not None

    assert jira_st_ok["state"] == "CONFIGURED"
    assert jira_st_ok["configured"] is True
    assert jira_st_ok["last_issue_key"] == "SEC-55"
    assert jira_st_ok["last_issue_url"] == "https://jira.example/browse/SEC-55"
    assert jira_st_ok["last_delivery_at"] is not None

    # 3. Error state
    post_err = Mock(side_effect=Exception("Connection refused"))
    monkeypatch.setattr(slack_service.requests, "post", post_err)
    monkeypatch.setattr(jira_service.requests, "post", post_err)

    slack_service.send_slack_notification({"severity": "HIGH", "user_id": "u1"})
    jira_service.create_jira_issue({"severity": "HIGH", "user_id": "u1"})

    slack_st_err = slack_service.get_slack_status()
    jira_st_err = jira_service.get_jira_status()
    assert slack_st_err["state"] == "ERROR"
    assert slack_st_err["status"] == "failed"
    assert jira_st_err["state"] == "ERROR"
    assert jira_st_err["status"] == "failed"


@pytest.mark.asyncio
async def test_manual_alert_and_incident_api_dispatch(client, db, monkeypatch):
    from conftest import create_user, login
    await create_user("sec-admin", role="ADMIN")
    admin_token = (await login(client, "sec-admin"))["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/services/valid")
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")

    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.content = b'{"key": "SEC-900"}'
    mock_resp.json = Mock(return_value={"key": "SEC-900"})
    post = Mock(return_value=mock_resp)
    monkeypatch.setattr(slack_service.requests, "post", post)
    monkeypatch.setattr(jira_service.requests, "post", post)

    # 1. Create HIGH alert via API -> triggers Slack
    alert_resp = await client.post(
        "/api/alerts",
        json={
            "severity": "HIGH",
            "title": "Manual High Risk Incident",
            "reason": "Exfiltration suspected",
            "user_id": "sec-admin",
        },
        headers=admin_headers,
    )
    assert alert_resp.status_code == 201
    assert alert_resp.json()["slack_delivery"] == "sent"

    # 2. Create CRITICAL incident via API -> triggers Jira
    incident_resp = await client.post(
        "/api/incidents",
        json={
            "severity": "CRITICAL",
            "title": "Confirmed Data Breach",
            "reason": "Multiple credential leaks",
            "user_id": "sec-admin",
        },
        headers=admin_headers,
    )
    assert incident_resp.status_code == 201
    inc_data = incident_resp.json()
    assert inc_data["jira_delivery"] == "sent"
    assert inc_data["jira_issue_key"] == "SEC-900"
    assert inc_data["jira_issue_url"] == "https://jira.example/browse/SEC-900"

