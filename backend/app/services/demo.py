"""Safe, isolated synthetic data generation for demonstrations.

Demo records carry an immutable run id and use a reserved user-id namespace.
Resetting a run only removes records linked to that run; it never touches
operator-created accounts or monitoring data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.behavior.schemas import BehaviorAnalysisRequest
from app.behavior.service import analyze_behavior
from app.models.event import ActionEnum, EventModel
from app.models.user import UserModel
from app.privacy.schemas import PrivacyAnalysisRequest
from app.privacy.service import analyze_text
from app.risk.context import endpoint_signal_for_event
from app.risk.schemas import RiskAssessmentRequest
from app.risk.service import analyze_risk
from app.services.alerts import create_alerts_from_risk
from app.services.monitoring import log_event

DEMO_SOURCE = "synthetic_demo"
DEMO_USER_IDS = ("demo_ava_finance", "demo_noah_developer", "demo_mia_hr")


async def _ensure_demo_users(db, now: datetime) -> None:
    users = (
        ("demo_ava_finance", "Ava Patel", "FINANCE"),
        ("demo_noah_developer", "Noah Kim", "DEVELOPER"),
        ("demo_mia_hr", "Mia Santos", "HR"),
    )
    for user_id, display_name, business_role in users:
        await db.users.update_one(
            {"user_id": user_id},
            {"$setOnInsert": UserModel(
                user_id=user_id,
                email=f"{user_id}@synthetic.example",
                display_name=display_name,
                business_role=business_role,
                monitoring_enabled="ALLOWED",
                source=DEMO_SOURCE,
                created_at=now,
            ).model_dump()},
            upsert=True,
        )


async def _persist_and_analyze(
    db, *, run_id: str, user_id: str, event_type: str, action: ActionEnum,
    timestamp: datetime, resource_name: str, category: str, application: str = "explorer.exe",
) -> tuple[dict[str, Any], Any]:
    event = EventModel(
        event_id=f"demo_evt_{uuid4().hex}",
        event_type=event_type,
        user_id=user_id,
        device_id=f"demo_device_{user_id.removeprefix('demo_')}",
        source="endpoint_agent",
        saas_app="endpoint",
        action=action,
        resource_id=f"demo_resource_{uuid4().hex[:12]}",
        resource_name=resource_name,
        application={"name": application},
        timestamp=timestamp,
        metadata={"demo_run_id": run_id, "synthetic": True, "resource_category": category},
    )
    await log_event(event)
    stored = event.model_dump()
    finding = await analyze_behavior(
        BehaviorAnalysisRequest(user_id=user_id, event_id=event.event_id, timestamp=timestamp),
        business_role=(await db.users.find_one({"user_id": user_id}) or {}).get("business_role", "GENERAL"),
        event=stored,
    )
    return stored, finding


async def generate_demo_run(db) -> dict[str, Any]:
    """Generate data through the production analysis functions, never fixtures."""
    now = datetime.now(timezone.utc)
    run_id = f"demo_run_{uuid4().hex[:12]}"
    await _ensure_demo_users(db, now)

    for index, user_id in enumerate(DEMO_USER_IDS):
        await db.devices.update_one(
            {"device_id": f"demo_device_{user_id.removeprefix('demo_')}"},
            {"$set": {
                "user_id": user_id, "hostname": f"DEMO-{index + 1:02d}",
                "os_version": "Windows 11 (synthetic)", "agent_version": "demo-1.0",
                "status": "ACTIVE", "monitoring_enabled": True,
                "last_heartbeat": now, "demo_run_id": run_id, "synthetic": True,
                "token_hash": f"synthetic-{user_id}", "token_prefix": "synthetic",
                "enrolled_at": now, "revoked_at": None, "revoked_reason": None,
            }},
            upsert=True,
        )

    # Establish ordinary behaviour first. These are passed through the actual
    # EWMA profile/anomaly service but do not manufacture a risk outcome.
    normal_count = 0
    for user_index, user_id in enumerate(DEMO_USER_IDS):
        for offset in range(4):
            await _persist_and_analyze(
                db, run_id=run_id, user_id=user_id, event_type="file.access_observed",
                action=ActionEnum.ACCESS,
                timestamp=now - timedelta(minutes=90 - user_index * 4 - offset * 12),
                resource_name="company_shared_handbook.pdf", category="shared",
            )
            normal_count += 1

    # A high-impact HR user accessing finance records. The resulting role
    # mismatch, endpoint signal and PII finding are evaluated by risk.service.
    suspicious_event, anomaly = await _persist_and_analyze(
        db, run_id=run_id, user_id="demo_mia_hr", event_type="file.deleted",
        action=ActionEnum.DELETE, timestamp=now,
        resource_name="finance_customer_export.xlsx", category="finance",
        application="powershell.exe",
    )
    pii_text = "\n".join(
        f"Customer payment card 4111-1111-1111-{index:04d}; contact demo{index}@example.test"
        for index in range(1, 11)
    )
    privacy = await analyze_text(
        PrivacyAnalysisRequest(text=pii_text, event_id=suspicious_event["event_id"], file_id="demo_synthetic_export"),
        "demo_mia_hr", source=DEMO_SOURCE,
    )
    assessment = await analyze_risk(
        RiskAssessmentRequest(
            user_id="demo_mia_hr", event_id=suspicious_event["event_id"],
            privacy_finding_id=privacy.finding_id, anomaly_id=anomaly.anomaly_id,
            timestamp=now,
        ),
        endpoint_score=endpoint_signal_for_event(suspicious_event),
    )
    alerts = await create_alerts_from_risk(db, assessment.model_dump())
    await db.demo_runs.insert_one({
        "run_id": run_id, "created_at": now, "source": DEMO_SOURCE,
        "user_ids": list(DEMO_USER_IDS), "event_ids": [suspicious_event["event_id"]],
        "privacy_finding_ids": [privacy.finding_id], "risk_ids": [assessment.risk_id],
        "alert_ids": [str(item.get("_id")) for item in alerts],
    })
    return {
        "run_id": run_id, "created_at": now, "normal_events": normal_count,
        "suspicious_event_id": suspicious_event["event_id"], "privacy_finding_id": privacy.finding_id,
        "risk_id": assessment.risk_id, "risk_category": assessment.risk_category,
        "alerts_created": len(alerts), "synthetic": True,
    }


async def reset_demo_runs(db) -> dict[str, int]:
    """Delete only isolated synthetic records, leaving all real data intact."""
    run_docs = await db.demo_runs.find({}, {"run_id": 1, "event_ids": 1, "privacy_finding_ids": 1, "risk_ids": 1}).to_list(length=1000)
    run_ids = [item["run_id"] for item in run_docs]
    event_ids = [event_id for item in run_docs for event_id in item.get("event_ids", [])]
    risk_ids = [risk_id for item in run_docs for risk_id in item.get("risk_ids", [])]
    finding_ids = [finding_id for item in run_docs for finding_id in item.get("privacy_finding_ids", [])]
    demo_user_filter = {"user_id": {"$in": list(DEMO_USER_IDS)}}
    counts = {
        "events": (await db.events.delete_many({"metadata.demo_run_id": {"$in": run_ids}})).deleted_count if run_ids else 0,
        "anomalies": (await db.anomalies.delete_many(demo_user_filter)).deleted_count,
        "profiles": (await db.behavior_profiles.delete_many(demo_user_filter)).deleted_count,
        "findings": (await db.pii_findings.delete_many({"finding_id": {"$in": finding_ids}})).deleted_count if finding_ids else 0,
        "risks": (await db.risk_assessments.delete_many({"risk_id": {"$in": risk_ids}})).deleted_count if risk_ids else 0,
        "alerts": (await db.alerts.delete_many({"user_id": {"$in": list(DEMO_USER_IDS)}, "source": "risk_engine"})).deleted_count,
        "incidents": (await db.incidents.delete_many(demo_user_filter)).deleted_count,
        "devices": (await db.devices.delete_many({"synthetic": True, "user_id": {"$in": list(DEMO_USER_IDS)}})).deleted_count,
        "users": (await db.users.delete_many({"source": DEMO_SOURCE, "user_id": {"$in": list(DEMO_USER_IDS)}})).deleted_count,
        "runs": (await db.demo_runs.delete_many({})).deleted_count,
    }
    return counts
