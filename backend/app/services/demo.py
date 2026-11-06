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

DEMO_PROFILES = (
    ("normal.user", "Normal User", "FINANCE"),
    ("frequent.user", "Frequent User", "DEVELOPER"),
    ("suspicious.user", "Suspicious User", "GENERAL"),
    ("sensitive.user", "Sensitive User", "HR"),
    ("new.user", "New User", "GENERAL"),
)

DEMO_USER_IDS = (
    "normal.user",
    "frequent.user",
    "suspicious.user",
    "sensitive.user",
    "new.user",
    "demo_ava_finance",
    "demo_noah_developer",
    "demo_mia_hr",
)


async def _ensure_demo_users(db, now: datetime) -> None:
    for user_id, display_name, business_role in DEMO_PROFILES:
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
    sanitized_user = user_id.replace(".", "_")
    event = EventModel(
        event_id=f"demo_evt_{uuid4().hex}",
        event_type=event_type,
        user_id=user_id,
        device_id=f"demo_device_{sanitized_user}",
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
    user_doc = await db.users.find_one({"user_id": user_id}) or {}
    business_role = user_doc.get("business_role", "GENERAL")
    finding = await analyze_behavior(
        BehaviorAnalysisRequest(user_id=user_id, event_id=event.event_id, timestamp=timestamp),
        business_role=business_role,
        event=stored,
    )
    return stored, finding


async def generate_demo_run(db) -> dict[str, Any]:
    """Generate 5 distinct behavioral profiles through the production analysis services."""
    now = datetime.now(timezone.utc)
    run_id = f"demo_run_{uuid4().hex[:12]}"
    await _ensure_demo_users(db, now)

    for index, (user_id, _, _) in enumerate(DEMO_PROFILES):
        sanitized_user = user_id.replace(".", "_")
        await db.devices.update_one(
            {"device_id": f"demo_device_{sanitized_user}"},
            {"$set": {
                "user_id": user_id, "hostname": f"DEMO-{index + 1:02d}",
                "os_version": "Windows 11 (synthetic)", "agent_version": "demo-2.0",
                "status": "ACTIVE", "monitoring_enabled": True,
                "last_heartbeat": now, "demo_run_id": run_id, "synthetic": True,
                "token_hash": f"synthetic-{sanitized_user}", "token_prefix": "synthetic",
                "enrolled_at": now, "revoked_at": None, "revoked_reason": None,
            }},
            upsert=True,
        )

    all_event_ids: list[str] = []
    normal_count = 0

    # 1. Profile: normal.user (FINANCE) - Regular, spaced events (~20m apart), no anomaly
    normal_offsets_minutes = [90, 60, 35, 15]
    for offset in normal_offsets_minutes:
        event_dict, _ = await _persist_and_analyze(
            db, run_id=run_id, user_id="normal.user", event_type="file.access_observed",
            action=ActionEnum.ACCESS,
            timestamp=now - timedelta(minutes=offset),
            resource_name="finance_quarterly_report.pdf", category="finance",
        )
        all_event_ids.append(event_dict["event_id"])
        normal_count += 1

    # 2. Profile: frequent.user (DEVELOPER) - Consistent high volume, adapts baseline smoothly, no anomaly
    frequent_offsets_minutes = [180, 120, 80, 50, 30, 18, 10, 3]
    for offset in frequent_offsets_minutes:
        event_dict, _ = await _persist_and_analyze(
            db, run_id=run_id, user_id="frequent.user", event_type="file.access_observed",
            action=ActionEnum.ACCESS,
            timestamp=now - timedelta(minutes=offset),
            resource_name="microservice_api_spec.yaml", category="shared",
        )
        all_event_ids.append(event_dict["event_id"])
        normal_count += 1

    # 3. Profile: suspicious.user (MARKETING) - Calm baseline, then burst of 10 events within seconds -> ACTIVITY_SPIKE
    for offset in range(2):
        event_dict, _ = await _persist_and_analyze(
            db, run_id=run_id, user_id="suspicious.user", event_type="file.access_observed",
            action=ActionEnum.ACCESS,
            timestamp=now - timedelta(minutes=40 - offset * 20),
            resource_name="marketing_deck.pdf", category="shared",
        )
        all_event_ids.append(event_dict["event_id"])
        normal_count += 1

    for offset in range(10):
        # 1-second burst intervals trigger dramatic deviation above threshold 5.0
        burst_ts = now - timedelta(seconds=20 - offset * 2)
        event_dict, _ = await _persist_and_analyze(
            db, run_id=run_id, user_id="suspicious.user", event_type="file.downloaded",
            action=ActionEnum.ACCESS,
            timestamp=burst_ts,
            resource_name=f"confidential_client_record_{offset + 1}.json", category="shared",
        )
        all_event_ids.append(event_dict["event_id"])

    # 4. Profile: sensitive.user (HR) - Baseline + accesses synthetic PII export, triggers Presidio + compound risk
    event_dict, _ = await _persist_and_analyze(
        db, run_id=run_id, user_id="sensitive.user", event_type="file.access_observed",
        action=ActionEnum.ACCESS,
        timestamp=now - timedelta(minutes=30),
        resource_name="employee_benefits_guide.pdf", category="shared",
    )
    all_event_ids.append(event_dict["event_id"])
    normal_count += 1

    sensitive_event, anomaly = await _persist_and_analyze(
        db, run_id=run_id, user_id="sensitive.user", event_type="file.deleted",
        action=ActionEnum.DELETE, timestamp=now,
        resource_name="finance_customer_export.xlsx", category="finance",
        application="powershell.exe",
    )
    all_event_ids.append(sensitive_event["event_id"])

    pii_text = "\n".join(
        f"Employee SSN 123-45-{idx:04d}, Credit Card 4111-1111-1111-{idx:04d}, contact hr.audit{idx}@company.org"
        for idx in range(1, 11)
    )
    privacy = await analyze_text(
        PrivacyAnalysisRequest(
            text=pii_text,
            event_id=sensitive_event["event_id"],
            file_id="demo_synthetic_export",
        ),
        "sensitive.user", source=DEMO_SOURCE,
    )
    assessment = await analyze_risk(
        RiskAssessmentRequest(
            user_id="sensitive.user", event_id=sensitive_event["event_id"],
            privacy_finding_id=privacy.finding_id, anomaly_id=anomaly.anomaly_id,
            timestamp=now,
        ),
        endpoint_score=endpoint_signal_for_event(sensitive_event),
    )
    alerts = await create_alerts_from_risk(db, assessment.model_dump())

    # 5. Profile: new.user (SALES) - Exactly 1 event (cold start, insufficient history for anomaly)
    event_dict, _ = await _persist_and_analyze(
        db, run_id=run_id, user_id="new.user", event_type="file.access_observed",
        action=ActionEnum.ACCESS,
        timestamp=now - timedelta(minutes=5),
        resource_name="welcome_onboarding_guide.pdf", category="shared",
    )
    all_event_ids.append(event_dict["event_id"])
    normal_count += 1

    total_events = len(all_event_ids)

    await db.demo_runs.insert_one({
        "run_id": run_id, "created_at": now, "source": DEMO_SOURCE,
        "user_ids": [p[0] for p in DEMO_PROFILES],
        "event_ids": all_event_ids,
        "privacy_finding_ids": [privacy.finding_id],
        "risk_ids": [assessment.risk_id],
        "alert_ids": [str(item.get("_id")) for item in alerts],
    })

    return {
        "run_id": run_id,
        "created_at": now,
        "total_events": total_events,
        "normal_events": normal_count,
        "profiles": {
            "normal": "normal.user",
            "frequent": "frequent.user",
            "suspicious": "suspicious.user",
            "sensitive": "sensitive.user",
            "new": "new.user",
        },
        "suspicious_event_id": sensitive_event["event_id"],
        "privacy_finding_id": privacy.finding_id,
        "risk_id": assessment.risk_id,
        "risk_category": assessment.risk_category,
        "alerts_created": len(alerts),
        "synthetic": True,
    }


async def reset_demo_runs(db) -> dict[str, int]:
    """Delete only isolated synthetic records, leaving all real data intact."""
    run_docs = await db.demo_runs.find(
        {},
        {"run_id": 1, "event_ids": 1, "privacy_finding_ids": 1, "risk_ids": 1}
    ).to_list(length=1000)

    run_ids = [item["run_id"] for item in run_docs]
    event_ids = [eid for item in run_docs for eid in item.get("event_ids", [])]
    risk_ids = [rid for item in run_docs for rid in item.get("risk_ids", [])]
    finding_ids = [fid for item in run_docs for fid in item.get("privacy_finding_ids", [])]
    demo_user_list = list(DEMO_USER_IDS)
    demo_user_filter = {"user_id": {"$in": demo_user_list}}

    counts = {
        "events": (await db.events.delete_many({
            "$or": [
                {"metadata.demo_run_id": {"$in": run_ids}},
                {"metadata.synthetic": True},
                {"user_id": {"$in": demo_user_list}},
            ]
        })).deleted_count,
        "anomalies": (await db.anomalies.delete_many(demo_user_filter)).deleted_count,
        "profiles": (await db.behavior_profiles.delete_many(demo_user_filter)).deleted_count,
        "findings": (await db.pii_findings.delete_many({
            "$or": [
                {"finding_id": {"$in": finding_ids}},
                {"source": DEMO_SOURCE},
                {"user_id": {"$in": demo_user_list}},
            ]
        })).deleted_count,
        "risks": (await db.risk_assessments.delete_many({
            "$or": [
                {"risk_id": {"$in": risk_ids}},
                {"user_id": {"$in": demo_user_list}},
            ]
        })).deleted_count,
        "alerts": (await db.alerts.delete_many({"user_id": {"$in": demo_user_list}})).deleted_count,
        "incidents": (await db.incidents.delete_many(demo_user_filter)).deleted_count,
        "devices": (await db.devices.delete_many({"user_id": {"$in": demo_user_list}})).deleted_count,
        "users": (await db.users.delete_many({"user_id": {"$in": demo_user_list}})).deleted_count,
        "runs": (await db.demo_runs.delete_many({})).deleted_count,
    }
    return counts
