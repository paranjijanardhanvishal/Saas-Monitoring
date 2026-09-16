# Configuration Defaults
# The research paper emphasizes combining privacy and behavioral analysis 
# but does not explicitly provide numerical weights for the combined risk score.
# These values are prototype defaults.

PRIVACY_WEIGHT = 0.5
BEHAVIORAL_WEIGHT = 0.5

# Thresholds for overall risk categories (Prototype defaults)
RISK_THRESHOLDS = {
    "LOW": 20,
    "MEDIUM": 50,
    "HIGH": 80,
    # CRITICAL is >= 80
}

def normalize_behavioral_deviation(deviation: float) -> float:
    """
    Step 4 provides a deviation ratio (current_rate / EWMA_baseline).
    We normalize this deviation to a 0-100 score.
    Prototype mapping:
    - deviation <= 1.0 -> 0 (No anomaly)
    - deviation >= 10.0 -> 100 (Critical spike)
    - Linear scaling in between.
    """
    if deviation <= 1.0:
        return 0.0
    
    score = (deviation - 1.0) * (100.0 / 9.0)
    return min(100.0, score)

def calculate_combined_risk(privacy_score: float, behavioral_score: float, p_weight: float = PRIVACY_WEIGHT, b_weight: float = BEHAVIORAL_WEIGHT) -> float:
    """
    Calculates combined risk score (0-100).
    Ensures weights sum to 1.0.
    """
    if abs((p_weight + b_weight) - 1.0) > 0.001:
        raise ValueError("Weights must sum to 1.0")
        
    combined = (p_weight * privacy_score) + (b_weight * behavioral_score)
    return min(100.0, max(0.0, combined))

def determine_overall_risk_category(combined_score: float) -> str:
    """
    Maps combined score to an overall risk category.
    """
    if combined_score < RISK_THRESHOLDS["LOW"]:
        return "LOW"
    elif combined_score < RISK_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    elif combined_score < RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    else:
        return "CRITICAL"
