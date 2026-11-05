"""Optional Slack/Jira integration tests. No external calls are made."""

from unittest.mock import Mock

from app.integrations import alerts as integrations


def test_unconfigured_integrations_are_skipped(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("JIRA_API_URL", raising=False)
    monkeypatch.delenv("JIRA_AUTH_TOKEN", raising=False)
    assert integrations.send_slack_alert({}, {}) == "skipped_not_configured"
    assert integrations.create_jira_ticket({}, {}) == "skipped_not_configured"


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
