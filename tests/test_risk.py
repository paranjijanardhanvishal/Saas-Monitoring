"""Risk scoring unit tests and API scoping tests."""

from datetime import datetime, timezone

import pytest

from app.risk.scoring import (
    calculate_combined_risk,
    calculate_multi_signal_risk,
    determine_overall_risk_category,
    normalize_behavioral_deviation,
)
from app.risk.context import endpoint_signal_for_event
from app.risk.service import analyze_risk
from app.risk.schemas import RiskAssessmentRequest
from conftest import create_user, login


def test_behavioral_deviation_normalisation():
    assert normalize_behavioral_deviation(0.5) == 0.0
    assert normalize_behavioral_deviation(1.0) == 0.0
    assert normalize_behavioral_deviation(10.0) == 100.0
    assert normalize_behavioral_deviation(100.0) == 100.0
    assert 0 < normalize_behavioral_deviation(5.5) < 100


def test_combined_risk_requires_valid_weights():
    assert calculate_combined_risk(80, 40) == pytest.approx(60.0)
    assert calculate_combined_risk(100, 100) == 100.0
    with pytest.raises(ValueError):
        calculate_combined_risk(50, 50, p_weight=0.8, b_weight=0.8)


def test_multi_signal_renormalises_available_weights():
    score, weights, confidence = calculate_multi_signal_risk(
        {"privacy": 90, "behavior": None, "endpoint": 60, "access": None}
    )
    assert confidence == pytest.approx(0.52)
    assert weights["privacy"] == pytest.approx(0.30 / 0.52, rel=1e-3)
    assert weights["endpoint"] == pytest.approx(0.22 / 0.52, rel=1e-3)
    assert weights["behavior"] if "behavior" in weights else True
    assert "behavior" not in weights
    assert 70 <= score <= 80

    assert calculate_multi_signal_risk({"privacy": None}) == (0.0, {}, 0.0)


def test_risk_categories():
    assert determine_overall_risk_category(19.9) == "LOW"
    assert determine_overall_risk_category(20) == "MEDIUM"
    assert determine_overall_risk_category(50) == "HIGH"
    assert determine_overall_risk_category(80) == "CRITICAL"


def test_endpoint_signal_tolerates_null_application():
    # Persisted endpoint events store application=null when the agent has no
    # application metadata. Signal derivation must not fail on that shape.
    assert (
        endpoint_signal_for_event(
            {
                "event_type": "file.created",
                "resource_name": "controlled.pdf",
                "application": None,
                "metadata": None,
            }
        )
        == 25.0
    )
    assert (
        endpoint_signal_for_event(
            {
                "event_type": "process.started",
                "application": {"name": "powershell.exe"},
                "metadata": {},
            }
        )
        == 15.0
    )


async def _seed_event_and_finding(db, user_id: str, event_id: str) -> tuple[dict, dict]:
    now = datetime.now(timezone.utc)
    event = {
        "event_id": event_id,
        "event_type": "file.download_observed",
        "user_id": user_id,
        "action": "DOWNLOAD",
        "source": "endpoint_agent",
        "saas_app": "endpoint",
        "resource_name": "payroll.xlsx",
        "timestamp": now,
        "ingestion_timestamp": now,
        "metadata": {},
    }
    finding = {
        "finding_id": f"finding-{event_id}",
        "user_id": user_id,
        "event_id": event_id,
        "sensitivity_score": 90,
        "category": "HIGH_RISK",
        "timestamp": now,
    }
    await db.events.insert_one(event)
    await db.pii_findings.insert_one(finding)
    return event, finding


@pytest.mark.asyncio
async def test_two_signal_assessment_uses_legacy_weights(db):
    _, finding = await _seed_event_and_finding(db, "risk-user", "risk-event-0001")
    assessment = await analyze_risk(
        RiskAssessmentRequest(
            user_id="risk-user",
            event_id="risk-event-0001",
            privacy_finding_id=finding["finding_id"],
        )
    )
    assert assessment.privacy_score == 90
    assert assessment.behavioral_score == 0
    assert assessment.combined_score == pytest.approx(45.0)
    assert assessment.weights_used == {"privacy": 0.5, "behavior": 0.5}
    assert assessment.risk_category == "MEDIUM"
    assert assessment.is_partial_assessment is True
    assert "HIGH_SENSITIVITY_PII" in assessment.risk_factors
    assert any("privacy" in line.lower() for line in assessment.explanation)


@pytest.mark.asyncio
async def test_multi_signal_assessment_uses_context(db):
    await _seed_event_and_finding(db, "risk-ctx", "risk-event-0002")
    assessment = await analyze_risk(
        RiskAssessmentRequest(
            user_id="risk-ctx",
            event_id="risk-event-0002",
            include_context_signals=True,
        )
    )
    # file.download_observed (35) + sensitive .xlsx extension (15) = 50 endpoint.
    # No attributed proxy telemetry exists, so access is unavailable rather than
    # a measured zero and must not dilute the available endpoint signal.
    assert assessment.endpoint_score == pytest.approx(50.0)
    assert assessment.access_score == pytest.approx(0.0)
    assert assessment.weights_used == {"endpoint": 1.0}
    assert assessment.combined_score == pytest.approx(50.0)
    assert assessment.risk_category == "HIGH"
    assert assessment.signals_used == ["endpoint"]
    assert "ELEVATED_ENDPOINT_RISK_SIGNAL" in assessment.risk_factors


@pytest.mark.asyncio
async def test_access_signal_only_counts_attributed_proxy_events(db):
    await _seed_event_and_finding(db, "risk-access", "risk-event-0004")
    await db.events.insert_one(
        {
            "event_id": "risk-event-proxy-0001",
            "event_type": "saas.access",
            "user_id": "risk-access",
            "source": "saas_proxy",
            "action": "PERMISSION_CHANGE",
            "timestamp": datetime.now(timezone.utc),
            "metadata": {"identity_verified": False},
        }
    )
    assessment = await analyze_risk(
        RiskAssessmentRequest(
            user_id="risk-access",
            event_id="risk-event-0004",
            include_context_signals=True,
        )
    )
    assert assessment.endpoint_score == pytest.approx(50.0)
    assert assessment.access_score == pytest.approx(80.0)
    assert set(assessment.weights_used) == {"endpoint", "access"}
    assert "SENSITIVE_SAAS_ACCESS_PATTERN" in assessment.risk_factors


@pytest.mark.asyncio
async def test_assessment_rejects_foreign_findings(db):
    await _seed_event_and_finding(db, "risk-a", "risk-event-0003")
    with pytest.raises(ValueError):
        await analyze_risk(
            RiskAssessmentRequest(
                user_id="risk-b",
                event_id="risk-event-0003",
                privacy_finding_id="finding-risk-event-0003",
            )
        )


@pytest.mark.asyncio
async def test_risk_api_scoping_and_summary(client, db):
    await create_user("risk-api-user")
    await create_user("risk-api-admin", role="ADMIN")
    await _seed_event_and_finding(db, "risk-api-user", "risk-api-event-0001")

    user = {"Authorization": f"Bearer {(await login(client, 'risk-api-user'))['access_token']}"}
    admin = {"Authorization": f"Bearer {(await login(client, 'risk-api-admin'))['access_token']}"}

    created = await client.post(
        "/api/risk/analyze",
        json={
            "user_id": "risk-api-user",
            "event_id": "risk-api-event-0001",
            "privacy_finding_id": "finding-risk-api-event-0001",
        },
        headers=user,
    )
    assert created.status_code == 201, created.text
    assert created.json()["user_id"] == "risk-api-user"

    user_list = await client.get("/api/risk/assessments", headers=user)
    assert user_list.status_code == 200
    assert len(user_list.json()) == 1

    summary = await client.get("/api/risk/summary", headers=user)
    assert summary.status_code == 200
    assert summary.json()["top_users"][0]["user_id"] == "risk-api-user"

    admin_list = await client.get("/api/risk/assessments", headers=admin)
    assert admin_list.status_code == 200
    assert len(admin_list.json()) == 1

    other = await client.get("/api/risk/users/other-user", headers=user)
    assert other.status_code == 403
