from datetime import datetime, timezone
from typing import Any, Optional

from app.database.mongodb import get_database
from app.risk.context import recent_context_scores
from app.risk.factors import generate_risk_explanation
from app.risk.schemas import RiskAssessmentModel, RiskAssessmentRequest
from app.risk.scoring import (
    BEHAVIORAL_WEIGHT,
    PRIVACY_WEIGHT,
    calculate_combined_risk,
    calculate_multi_signal_risk,
    determine_overall_risk_category,
    normalize_behavioral_deviation,
)


async def _load_owned_finding(db, collection: str, id_field: str, finding_id: str, user_id: str) -> Optional[dict[str, Any]]:
    item = await db[collection].find_one({id_field: finding_id})
    if not item:
        return None
    if item.get("user_id") and item.get("user_id") != user_id:
        raise ValueError("Finding does not belong to the specified user")
    return item


async def analyze_risk(
    request: RiskAssessmentRequest,
    endpoint_score: Optional[float] = None,
    access_score: Optional[float] = None,
) -> RiskAssessmentModel:
    db = get_database()
    if db is None:
        raise ValueError("Database connection failed")

    privacy_finding = None
    anomaly_finding = None
    if request.privacy_finding_id:
        privacy_finding = await _load_owned_finding(
            db, "pii_findings", "finding_id", request.privacy_finding_id, request.user_id
        )
    if request.anomaly_id:
        anomaly_finding = await _load_owned_finding(
            db, "anomalies", "anomaly_id", request.anomaly_id, request.user_id
        )
    event = await db.events.find_one({"event_id": request.event_id})
    if event and event.get("user_id") and event.get("user_id") != request.user_id:
        raise ValueError("Event does not belong to the specified user")

    if endpoint_score is None and access_score is None and request.include_context_signals:
        endpoint_score, access_score = await recent_context_scores(db, request.user_id, event)

    privacy_score = float(privacy_finding.get("sensitivity_score", 0.0)) if privacy_finding else 0.0
    behavioral_score = 0.0
    if anomaly_finding:
        ewma_score = normalize_behavioral_deviation(anomaly_finding.get("deviation", 1.0))
        role_score = float(anomaly_finding.get("role_anomaly_score", 0.0) or 0.0)
        behavioral_score = max(ewma_score, role_score)

    contextual = endpoint_score is not None or access_score is not None
    if not contextual:
        if event and event.get("source") == "privacy_scan" and privacy_finding:
            # An explicit content scan can have a valid privacy signal without
            # an EWMA event. Renormalize that available signal so a high PII
            # result is not silently halved by missing behavioral evidence.
            combined_score = privacy_score
            weights_used = {"privacy": 1.0}
            signal_confidence = PRIVACY_WEIGHT
            signals_used = ["privacy"]
            is_partial = True
        else:
            combined_score = calculate_combined_risk(privacy_score, behavioral_score)
            weights_used = {"privacy": PRIVACY_WEIGHT, "behavior": BEHAVIORAL_WEIGHT}
            signal_confidence = (0.5 if privacy_finding else 0.0) + (0.5 if anomaly_finding else 0.0)
            signals_used = [name for name, present in (("privacy", privacy_finding), ("behavior", anomaly_finding)) if present]
            is_partial = not (privacy_finding and anomaly_finding)
    else:
        signals = {
            "privacy": privacy_score if privacy_finding else None,
            "behavior": behavioral_score if anomaly_finding else None,
            "endpoint": endpoint_score,
            "access": access_score,
        }
        combined_score, weights_used, signal_confidence = calculate_multi_signal_risk(signals)
        signals_used = [name for name, value in signals.items() if value is not None]
        is_partial = len(signals_used) < 4

    risk_category = determine_overall_risk_category(combined_score)
    risk_factors, explanation = generate_risk_explanation(
        privacy_score=privacy_score,
        behavioral_score=behavioral_score,
        privacy_finding=privacy_finding,
        anomaly_finding=anomaly_finding,
        endpoint_score=endpoint_score,
        access_score=access_score,
        event=event,
    )

    assessment = RiskAssessmentModel(
        user_id=request.user_id,
        event_id=request.event_id,
        privacy_finding_id=request.privacy_finding_id,
        anomaly_id=request.anomaly_id,
        privacy_score=privacy_score,
        behavioral_score=behavioral_score,
        endpoint_score=endpoint_score or 0.0,
        access_score=access_score or 0.0,
        privacy_weight=weights_used.get("privacy", PRIVACY_WEIGHT),
        behavioral_weight=weights_used.get("behavior", BEHAVIORAL_WEIGHT),
        weights_used=weights_used,
        combined_score=combined_score,
        risk_category=risk_category,
        signal_confidence=signal_confidence,
        signals_used=signals_used,
        risk_factors=risk_factors,
        explanation=explanation,
        is_partial_assessment=is_partial,
        saas_app=event.get("saas_app") if event else None,
        resource_id=event.get("resource_id") if event else None,
        timestamp=request.timestamp,
    )

    await db.risk_assessments.insert_one(assessment.model_dump())
    return assessment
