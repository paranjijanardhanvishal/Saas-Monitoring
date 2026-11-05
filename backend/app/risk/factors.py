from typing import Any, Dict, List, Optional, Tuple


def generate_risk_explanation(
    privacy_score: float,
    behavioral_score: float,
    privacy_finding: Optional[Dict[str, Any]],
    anomaly_finding: Optional[Dict[str, Any]],
    endpoint_score: Optional[float] = None,
    access_score: Optional[float] = None,
    event: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], List[str]]:
    """Generate structured factors and human-readable explanations.

    Explanations are derived only from stored findings; nothing is invented.
    """
    risk_factors: List[str] = []
    explanation: List[str] = []

    if privacy_finding:
        if privacy_score >= 60:
            risk_factors.append("HIGH_SENSITIVITY_PII")
            explanation.append("High privacy sensitivity detected (critical data exposure risk).")
        elif privacy_score >= 20:
            risk_factors.append("MODERATE_SENSITIVITY_PII")
            explanation.append("Moderate privacy sensitivity detected.")
        else:
            explanation.append("Minimal or safe privacy context.")
    else:
        explanation.append("No privacy analysis available for this event.")

    if anomaly_finding:
        if anomaly_finding.get("role_mismatch", False):
            risk_factors.append("ROLE_POLICY_MISMATCH")
            explanation.append(
                anomaly_finding.get(
                    "role_reason",
                    "Observed activity did not match the user's assigned business-role profile.",
                )
            )
        if anomaly_finding.get("is_anomaly", False):
            risk_factors.append("BEHAVIORAL_ANOMALY")
            explanation.append(
                f"Behavioral anomaly detected: {anomaly_finding.get('reason', 'Unknown anomaly')}"
            )
            if anomaly_finding.get("anomaly_type") == "ACTIVITY_SPIKE":
                risk_factors.append("ACTIVITY_SPIKE")
        else:
            explanation.append("Activity rate is consistent with historical baselines.")
    else:
        explanation.append("No behavioral anomaly history available for this event.")

    if endpoint_score is not None:
        if endpoint_score >= 60:
            risk_factors.append("HIGH_ENDPOINT_RISK_SIGNAL")
            explanation.append("Endpoint event matched high-risk file/application behaviour.")
        elif endpoint_score >= 30:
            risk_factors.append("ELEVATED_ENDPOINT_RISK_SIGNAL")
            explanation.append("Endpoint activity contributed an elevated risk signal.")
        elif endpoint_score > 0:
            explanation.append("Endpoint activity contributed a low risk signal.")
        else:
            explanation.append("No endpoint risk signal for this event.")

    if access_score is not None:
        if access_score >= 60:
            risk_factors.append("SENSITIVE_SAAS_ACCESS_PATTERN")
            explanation.append("SaaS action is associated with elevated data-movement risk.")
        elif access_score >= 30:
            risk_factors.append("ELEVATED_SAAS_ACCESS_PATTERN")
            explanation.append("SaaS action contributed an elevated access-pattern signal.")

    if event:
        event_type = event.get("event_type")
        if event_type:
            explanation.append(f"Source event type: {event_type}.")
    return risk_factors, explanation
