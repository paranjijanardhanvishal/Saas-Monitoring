from typing import List, Tuple, Dict, Any

def generate_risk_explanation(
    privacy_score: float, 
    behavioral_score: float, 
    privacy_finding: Dict[str, Any] | None, 
    anomaly_finding: Dict[str, Any] | None
) -> Tuple[List[str], List[str]]:
    """
    Generates structured risk factors and human-readable explanations based on findings.
    """
    risk_factors = []
    explanation = []
    
    # Privacy Assessment
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
        
    # Behavioral Assessment
    if anomaly_finding:
        if anomaly_finding.get("is_anomaly", False):
            risk_factors.append("BEHAVIORAL_ANOMALY")
            explanation.append(f"Behavioral anomaly detected: {anomaly_finding.get('reason', 'Unknown anomaly')}")
            
            # Specific anomaly types
            anomaly_type = anomaly_finding.get("anomaly_type")
            if anomaly_type == "ACTIVITY_SPIKE":
                risk_factors.append("ACTIVITY_SPIKE")
        else:
            explanation.append("Activity rate is consistent with historical baselines.")
    else:
        explanation.append("No behavioral anomaly history available for this event.")
        
    return risk_factors, explanation
