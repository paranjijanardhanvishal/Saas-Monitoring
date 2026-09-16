import requests
import time

BASE_URL = "http://127.0.0.1:8000/api"
USER_ID = "demo_user_final"

print("--- END TO END SYNTHETIC DEMO ---")

# 1. Generate Event
event_payload = {
    "event_id": "demo_evt_001",
    "user_id": USER_ID,
    "saas_app": "Google Drive",
    "action": "DOWNLOAD",
    "resource_id": "file_789",
    "ip_address": "192.168.1.100"
}
print(f"1. Creating Event: {event_payload}")
r = requests.post(f"{BASE_URL}/events", json=event_payload)
if r.status_code != 201:
    print(f"Error: {r.text}")
r.raise_for_status()
event = r.json()
event_id = event["event_id"]
print(f"-> Event ID: {event_id}\n")

# 2. Privacy Analysis
privacy_payload = {
    "text": "User downloaded a file containing phone numbers like 555-1234 and email john.doe@example.com",
    "event_id": event_id
}
print(f"2. Privacy Analysis: {privacy_payload}")
r = requests.post(f"{BASE_URL}/privacy/analyze", json=privacy_payload)
r.raise_for_status()
privacy = r.json()
privacy_id = privacy["finding_id"]
print(f"-> Privacy Score: {privacy['sensitivity_score']} (ID: {privacy_id})\n")

# 3. Behavioral Analysis
behavior_payload = {
    "user_id": USER_ID,
    "event_id": event_id
}
print(f"3. Behavioral Analysis: {behavior_payload}")
r = requests.post(f"{BASE_URL}/behavior/analyze", json=behavior_payload)
r.raise_for_status()
behavior = r.json()
anomaly_id = behavior["anomaly_id"]
print(f"-> Activity Rate: {behavior['activity_rate']}, Anomaly: {behavior['is_anomaly']} (ID: {anomaly_id})\n")

# 4. Risk Assessment
risk_payload = {
    "user_id": USER_ID,
    "event_id": event_id,
    "privacy_finding_id": privacy_id,
    "anomaly_id": anomaly_id
}
print(f"4. Risk Assessment: {risk_payload}")
r = requests.post(f"{BASE_URL}/risk/analyze", json=risk_payload)
r.raise_for_status()
risk = r.json()
risk_id = risk["risk_id"]
print(f"-> Combined Score: {risk['combined_score']} [{risk['risk_category']}] (ID: {risk_id})")
print(f"-> Explanations: {risk['explanation']}\n")

# 5. Enforcement/Response
enforce_payload = {
    "risk_id": risk_id,
    "user_id": USER_ID,
    "risk_category": risk["risk_category"],
    "action": "BLOCK" # Simulate proxy dropping it
}
print(f"5. Enforcement Response: {enforce_payload}")
r = requests.post(f"{BASE_URL}/enforcement/respond", json=enforce_payload)
r.raise_for_status()
enf = r.json()
print(f"-> Enforced Action: {enf['action_taken']} ({enf['response_status']})\n")

print("--- DEMO COMPLETE ---")
