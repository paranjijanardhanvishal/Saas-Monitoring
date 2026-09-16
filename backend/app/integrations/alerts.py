import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
JIRA_API_URL = os.getenv("JIRA_API_URL", "")
JIRA_AUTH_TOKEN = os.getenv("JIRA_AUTH_TOKEN", "")

def send_slack_alert(risk_assessment: dict, response_model: dict):
    """
    Sends a structured alert to Slack for HIGH/CRITICAL risks.
    Uses a mock/simulation mode if SLACK_WEBHOOK_URL is not configured.
    """
    payload = {
        "text": f"🚨 *Security Alert: {risk_assessment.get('risk_category')} Risk Detected* 🚨",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🚨 *Security Alert: {risk_assessment.get('risk_category')} Risk Detected* 🚨\n\n"
                            f"*User:* {risk_assessment.get('user_id')}\n"
                            f"*Event ID:* {risk_assessment.get('event_id')}\n"
                            f"*Combined Score:* {risk_assessment.get('combined_score')}\n"
                            f"*Action Taken:* {response_model.get('action_taken')} ({response_model.get('response_status')})\n\n"
                            f"*Explanations:* {', '.join(risk_assessment.get('explanation', []))}"
                }
            }
        ]
    }
    
    if not SLACK_WEBHOOK_URL:
        logger.info(f"[SIMULATED SLACK ALERT] {json.dumps(payload)}")
        return True
        
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")
        return False

def create_jira_ticket(risk_assessment: dict, response_model: dict):
    """
    Creates a Jira incident ticket for HIGH/CRITICAL risks.
    Uses a mock/simulation mode if JIRA_API_URL is not configured.
    """
    payload = {
        "fields": {
            "project": {"key": "SEC"},
            "summary": f"Security Incident: {risk_assessment.get('risk_category')} Risk for {risk_assessment.get('user_id')}",
            "description": f"Risk Score: {risk_assessment.get('combined_score')}\nAction: {response_model.get('action_taken')}\nDetails: {', '.join(risk_assessment.get('explanation', []))}",
            "issuetype": {"name": "Incident"}
        }
    }
    
    if not JIRA_API_URL or not JIRA_AUTH_TOKEN:
        logger.info(f"[SIMULATED JIRA TICKET] {json.dumps(payload)}")
        return True
        
    try:
        headers = {
            "Authorization": f"Bearer {JIRA_AUTH_TOKEN}",
            "Content-Type": "application/json"
        }
        response = requests.post(JIRA_API_URL, json=payload, headers=headers, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to create Jira ticket: {e}")
        return False
