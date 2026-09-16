import pytest
import logging
from app.integrations.alerts import send_slack_alert, create_jira_ticket

def test_slack_alert_mock(caplog):
    caplog.set_level(logging.INFO)
    risk_assessment = {"risk_category": "HIGH", "user_id": "test_user"}
    response_model = {"action_taken": "WARN", "response_status": "EXECUTED"}
    
    # By default, without env vars, it uses mock mode
    result = send_slack_alert(risk_assessment, response_model)
    assert result is True
    assert "[SIMULATED SLACK ALERT]" in caplog.text

def test_jira_ticket_mock(caplog):
    caplog.set_level(logging.INFO)
    risk_assessment = {"risk_category": "CRITICAL", "user_id": "test_user", "combined_score": 90}
    response_model = {"action_taken": "SIMULATED_BLOCK", "response_status": "SIMULATED"}
    
    result = create_jira_ticket(risk_assessment, response_model)
    assert result is True
    assert "[SIMULATED JIRA TICKET]" in caplog.text
