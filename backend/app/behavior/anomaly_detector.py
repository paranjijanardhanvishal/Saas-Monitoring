"""EWMA-based anomaly detection evaluating all 8 monitoring windows and download bursts.

Adheres to IEEE base paper:
  - Windows: 30m, 1h, 2h, 8h, 1d, 7d, 30d, 90d
  - Burst detection: >50 downloads in 5 minutes
  - Cold-start & zero-baseline safe handling
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.behavior.schemas import AnomalyFindingModel

logger = logging.getLogger(__name__)

ANOMALY_DEVIATION_THRESHOLD = 5.0
ALL_WINDOWS = ("30m", "1h", "2h", "8h", "1d", "7d", "30d", "90d")


def detect_anomaly(
    user_id: str,
    event_id: str,
    timestamp,
    current_rate: float,
    ewma_dict: Dict[str, float],
    burst_info: Optional[Dict[str, Any]] = None,
) -> AnomalyFindingModel:
    """Evaluate activity rate against all eight EWMA windows and detect bursts."""
    window_deviations: Dict[str, float] = {}
    epsilon = 0.001

    # 1. Compute deviations across all 8 windows
    for window in ALL_WINDOWS:
        baseline = ewma_dict.get(window)
        if baseline is None:
            window_deviations[window] = 1.0
        elif baseline < epsilon:
            # Avoid treating uninitialized or zero baseline as a real anomaly
            window_deviations[window] = 1.0
        else:
            window_deviations[window] = round(current_rate / baseline, 2)

    dev_1h = window_deviations.get("1h", 1.0)
    short_term_dev = max(
        window_deviations.get("30m", 1.0),
        dev_1h,
        window_deviations.get("2h", 1.0),
    )
    long_term_dev = max(
        window_deviations.get("1d", 1.0),
        window_deviations.get("7d", 1.0),
        window_deviations.get("30d", 1.0),
        window_deviations.get("90d", 1.0),
    )

    # 2. Multi-window composite deviation
    # Checks short-term acceleration vs long-term baseline divergence
    if short_term_dev > 1.0 and long_term_dev > 1.0:
        composite_deviation = max(dev_1h, 0.6 * short_term_dev + 0.4 * long_term_dev)
    else:
        composite_deviation = dev_1h

    deviation_ratio = round(composite_deviation, 2)
    is_rate_anomaly = deviation_ratio > ANOMALY_DEVIATION_THRESHOLD

    # 3. Download burst detection (>50 downloads in 5 minutes)
    burst_detected = bool(burst_info and burst_info.get("burst_detected"))
    burst_count = int((burst_info or {}).get("burst_count", 0))

    is_anomaly = is_rate_anomaly or burst_detected

    if burst_detected and is_rate_anomaly:
        anomaly_type = "COMPOUND_BURST"
        reason = (
            f"High-frequency download burst: {burst_count} downloads within 5 minutes. "
            f"Activity rate exceeded baseline across multiple windows (Composite deviation: {deviation_ratio:.2f}x; "
            f"1h={dev_1h:.1f}x, 30m={window_deviations.get('30m', 1.0):.1f}x, 7d={window_deviations.get('7d', 1.0):.1f}x)."
        )
        logger.warning("Compound download burst anomaly detected for user %s: %s", user_id, reason)
    elif burst_detected:
        anomaly_type = "DOWNLOAD_BURST"
        reason = f"High-frequency download burst: {burst_count} files downloaded within 5-minute rolling window."
        logger.warning("Download burst anomaly detected for user %s: %s", user_id, reason)
    elif is_rate_anomaly:
        anomaly_type = "ACTIVITY_SPIKE"
        reason = (
            f"Activity rate exceeded adaptive baseline across multiple windows (Composite deviation: {deviation_ratio:.2f}x; "
            f"1h={dev_1h:.1f}x, 30m={window_deviations.get('30m', 1.0):.1f}x, 7d={window_deviations.get('7d', 1.0):.1f}x)."
        )
        logger.warning("Activity spike detected for user %s: %s", user_id, reason)
    else:
        anomaly_type = "NORMAL"
        reason = "Activity rate is within normal baseline parameters across all monitoring windows."

    return AnomalyFindingModel(
        user_id=user_id,
        event_id=event_id,
        timestamp=timestamp,
        activity_rate=current_rate,
        ewma=ewma_dict,
        deviation=deviation_ratio,
        window_deviations=window_deviations,
        burst_detected=burst_detected,
        burst_count=burst_count,
        is_anomaly=is_anomaly,
        reason=reason,
        anomaly_type=anomaly_type,
    )
