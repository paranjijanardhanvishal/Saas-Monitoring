"""Automatic risk evaluation for endpoint events.

Runs after an authenticated agent event is persisted. Only server-generated
timestamps are used for baseline updates, so a compromised endpoint cannot move
its own baseline backwards or forwards.
"""

import logging
from typing import Any

from app.behavior.schemas import BehaviorAnalysisRequest
from app.behavior.service import analyze_behavior
from app.core.config import settings
from app.risk.context import endpoint_signal_for_event, access_signal_for_event, recent_context_scores
from app.risk.schemas import RiskAssessmentRequest
from app.risk.service import analyze_risk
from app.services.alerts import create_alerts_from_risk

logger = logging.getLogger(__name__)


async def evaluate_persisted_endpoint_event(db, event: dict[str, Any]) -> None:
    if not settings.AUTO_RISK_ENABLED:
        return
    event_id = event.get("event_id")
    user_id = event.get("user_id")
    if not event_id or not user_id:
        return

    try:
        existing = await db.risk_assessments.find_one({"event_id": event_id})
        if existing:
            return

        baseline_time = event.get("ingestion_timestamp") or event.get("timestamp")
        user = await db.users.find_one({"user_id": user_id})
        finding = await analyze_behavior(
            BehaviorAnalysisRequest(
                user_id=user_id,
                event_id=event_id,
                timestamp=baseline_time,
            ),
            business_role=(user or {}).get("business_role", "GENERAL"),
            event=event,
        )

        endpoint_score = endpoint_signal_for_event(event)
        access_score = (
            access_signal_for_event(event)
            if event.get("source") == "saas_proxy"
            else None
        )
        recent_endpoint, recent_access = await recent_context_scores(db, user_id, event)
        if recent_endpoint is not None:
            endpoint_score = max(endpoint_score, recent_endpoint)
        if recent_access is not None:
            access_score = max(access_score, recent_access)

        significant = (
            finding.is_anomaly
            or endpoint_score >= 20
            or (access_score or 0.0) >= 35
            or event.get("event_type") == "failed_login.observed"
        )
        if not significant:
            return

        privacy = await db.pii_findings.find_one({"event_id": event_id})
        request = RiskAssessmentRequest(
            user_id=user_id,
            event_id=event_id,
            privacy_finding_id=privacy.get("finding_id") if privacy else None,
            anomaly_id=finding.anomaly_id,
            timestamp=baseline_time,
        )
        assessment = await analyze_risk(
            request,
            endpoint_score=endpoint_score,
            access_score=access_score,
        )
        await create_alerts_from_risk(db, assessment.model_dump())
    except Exception:
        # Ingestion must not fail because analytics failed; the failure is
        # logged for operators instead of being silently swallowed.
        logger.exception("Risk pipeline failed for event %s", event_id)
