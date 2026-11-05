# Configuration defaults for the combined risk engine.
# Privacy and behavioural weights preserve the original two-signal prototype
# behaviour when contextual signals are unavailable.

PRIVACY_WEIGHT = 0.5
BEHAVIORAL_WEIGHT = 0.5

# Documented four-signal weights used when endpoint/SaaS context is present.
MULTI_SIGNAL_WEIGHTS = {
    "privacy": 0.30,
    "behavior": 0.30,
    "endpoint": 0.22,
    "access": 0.18,
}

RISK_THRESHOLDS = {
    "LOW": 20,
    "MEDIUM": 50,
    "HIGH": 80,
    # CRITICAL is >= 80
}


def normalize_behavioral_deviation(deviation: float) -> float:
    """Map a deviation ratio to a 0-100 score.

    deviation <= 1.0 -> 0, deviation >= 10.0 -> 100, linear in between.
    """
    if deviation is None or deviation <= 1.0:
        return 0.0
    score = (deviation - 1.0) * (100.0 / 9.0)
    return min(100.0, score)


def calculate_combined_risk(
    privacy_score: float,
    behavioral_score: float,
    p_weight: float = PRIVACY_WEIGHT,
    b_weight: float = BEHAVIORAL_WEIGHT,
) -> float:
    if abs((p_weight + b_weight) - 1.0) > 0.001:
        raise ValueError("Weights must sum to 1.0")
    combined = (p_weight * privacy_score) + (b_weight * behavioral_score)
    return min(100.0, max(0.0, combined))


def calculate_multi_signal_risk(signals: dict[str, float | None]) -> tuple[float, dict[str, float], float]:
    """Combine available signals with renormalised documented weights.

    ``signals`` maps privacy/behavior/endpoint/access to 0-100 values, or None
    when the signal is unavailable (for example no PII finding for an event).
    Returns (combined_score, weights_used, confidence) where confidence is the
    sum of the configured weights that were available.
    """
    present = {
        name: max(0.0, min(100.0, float(value)))
        for name, value in signals.items()
        if value is not None and name in MULTI_SIGNAL_WEIGHTS
    }
    if not present:
        return 0.0, {}, 0.0

    available_weight = sum(MULTI_SIGNAL_WEIGHTS[name] for name in present)
    if available_weight <= 0:
        return 0.0, {}, 0.0
    weights_used = {
        name: round(MULTI_SIGNAL_WEIGHTS[name] / available_weight, 4) for name in present
    }
    combined = sum(present[name] * weights_used[name] for name in present)
    return round(min(100.0, max(0.0, combined)), 2), weights_used, round(available_weight, 2)


def determine_overall_risk_category(combined_score: float) -> str:
    if combined_score < RISK_THRESHOLDS["LOW"]:
        return "LOW"
    if combined_score < RISK_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    if combined_score < RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    return "CRITICAL"
