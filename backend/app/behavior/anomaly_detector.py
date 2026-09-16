from typing import Dict, Tuple
from app.behavior.schemas import AnomalyFindingModel
import logging

logger = logging.getLogger(__name__)

# Configurable deviation multiplier to flag anomalies.
# The paper doesn't specify a universal numerical threshold for the deviation ratio.
# This is an implementation prototype default.
ANOMALY_DEVIATION_THRESHOLD = 5.0

def detect_anomaly(
    user_id: str,
    event_id: str,
    timestamp,
    current_rate: float,
    ewma_dict: Dict[str, float]
) -> AnomalyFindingModel:
    """
    Detects if the current activity rate is anomalous compared to the EWMA baseline.
    We check the deviation against the shortest window (e.g. 30m) or an aggregate.
    For this prototype, we use the 1h window as the primary baseline reference.
    """
    # Safe fallback if 1h is missing
    baseline = ewma_dict.get("1h", current_rate)
    
    # Avoid division by zero if baseline is extremely close to 0
    epsilon = 0.001
    safe_baseline = max(baseline, epsilon)
    
    deviation_ratio = current_rate / safe_baseline
    
    is_anomaly = deviation_ratio > ANOMALY_DEVIATION_THRESHOLD
    reason = "Activity rate is within normal baseline parameters."
    
    if is_anomaly:
        reason = f"Activity rate exceeded adaptive baseline (Deviation ratio: {deviation_ratio:.2f})"
        logger.warning(f"Anomaly detected for user {user_id}: {reason}")
        
    return AnomalyFindingModel(
        user_id=user_id,
        event_id=event_id,
        timestamp=timestamp,
        activity_rate=current_rate,
        ewma=ewma_dict,
        deviation=deviation_ratio,
        is_anomaly=is_anomaly,
        reason=reason,
        anomaly_type="ACTIVITY_SPIKE" if is_anomaly else "NORMAL"
    )
