"""Privacy/PII tests: detection, derived-only storage and ownership."""

import pytest

from app.privacy.presidio_analyzer import (
    RegexAnalyzerEngine,
    get_engine_name,
    reset_analyzer,
)
from app.privacy.schemas import PrivacyAnalysisRequest
from app.privacy.sensitivity import (
    calculate_sensitivity_score,
    classify_entity_sensitivity,
    determine_risk_category,
)
from app.privacy.service import analyze_text
from conftest import create_user, login


def test_regex_engine_detects_identifiers():
    engine = RegexAnalyzerEngine()
    results = engine.analyze(
        "email jane@example.com ssn 123-45-6789 password: hunter2 "
        "card 4111 1111 1111 1111 ip 10.0.0.5"
    )
    types = {item.entity_type for item in results}
    assert "EMAIL_ADDRESS" in types
    assert "US_SSN" in types
    assert "PASSWORD" in types
    assert "CREDIT_CARD" in types
    assert "IP_ADDRESS" in types


def test_regex_engine_is_deterministic_and_ignores_empty():
    engine = RegexAnalyzerEngine()
    assert engine.analyze("") == []
    first = engine.analyze("a@b.com")
    second = engine.analyze("a@b.com")
    assert [(i.entity_type, i.start, i.end) for i in first] == [
        (i.entity_type, i.start, i.end) for i in second
    ]


def test_sensitivity_scoring():
    assert classify_entity_sensitivity("PASSWORD") == "HIGH"
    assert classify_entity_sensitivity("EMAIL_ADDRESS") == "MODERATE"
    assert classify_entity_sensitivity("PERSON") == "LOW"
    assert classify_entity_sensitivity("WHATEVER") == "UNKNOWN"
    assert calculate_sensitivity_score(0, 0, 0) == 0
    assert calculate_sensitivity_score(10, 10, 10) == 100
    assert determine_risk_category(10) == "SAFE"
    assert determine_risk_category(30) == "SENSITIVE"
    assert determine_risk_category(60) == "HIGH_RISK"


@pytest.mark.asyncio
async def test_analyze_text_stores_only_derived_metadata(db):
    reset_analyzer()
    request = PrivacyAnalysisRequest(
        text="Contact jane@example.com about ssn 123-45-6789",
        file_id="file-1",
    )
    finding = await analyze_text(request, "owner-1")
    assert finding.user_id == "owner-1"
    assert finding.engine == get_engine_name()
    assert finding.sensitivity_score > 0
    assert finding.file_id == "file-1"
    assert not hasattr(finding, "text")

    stored = await db.pii_findings.find_one({"finding_id": finding.finding_id})
    assert stored is not None
    assert "jane@example.com" not in str(stored)
    assert "123-45-6789" not in str(stored)


@pytest.mark.asyncio
async def test_privacy_api_requires_authentication(client):
    response = await client.post("/api/privacy/analyze", json={"text": "a@b.com"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_privacy_api_assigns_server_side_owner(client, db):
    await create_user("privacy-user")
    token = (await login(client, "privacy-user"))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/privacy/analyze",
        json={"text": "password: letmein123 ssn 123-45-6789", "file_id": "f-1"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user_id"] == "privacy-user"
    assert body["category"] in {"SENSITIVE", "HIGH_RISK"}

    findings = await client.get("/api/privacy/findings", headers=headers)
    assert findings.status_code == 200
    assert [f["finding_id"] for f in findings.json()] == [body["finding_id"]]


@pytest.mark.asyncio
async def test_privacy_findings_are_isolated_between_users(client, db):
    await create_user("alice")
    await create_user("bob")
    alice_headers = {"Authorization": f"Bearer {(await login(client, 'alice'))['access_token']}"}
    bob_headers = {"Authorization": f"Bearer {(await login(client, 'bob'))['access_token']}"}

    created = await client.post(
        "/api/privacy/analyze", json={"text": "a@b.com"}, headers=alice_headers
    )
    assert created.status_code == 201
    finding_id = created.json()["finding_id"]

    bob_list = await client.get("/api/privacy/findings", headers=bob_headers)
    assert bob_list.status_code == 200
    assert bob_list.json() == []

    bob_direct = await client.get(f"/api/privacy/findings/{finding_id}", headers=bob_headers)
    assert bob_direct.status_code == 403


@pytest.mark.asyncio
async def test_only_admin_can_target_another_user(client, db):
    await create_user("admin-one", role="ADMIN")
    await create_user("target-one")
    await create_user("plain-one")
    admin_token = (await login(client, "admin-one"))["access_token"]
    user_token = (await login(client, "plain-one"))["access_token"]

    denied = await client.post(
        "/api/privacy/analyze?target_user_id=target-one",
        json={"text": "a@b.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert denied.status_code == 403

    allowed = await client.post(
        "/api/privacy/analyze?target_user_id=target-one",
        json={"text": "a@b.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 201
    assert allowed.json()["user_id"] == "target-one"


@pytest.mark.asyncio
async def test_ocr_status_endpoint(client, db):
    await create_user("ocr-tester")
    token = (await login(client, "ocr-tester"))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/privacy/ocr-status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "available" in data
    assert data["engine"] == "tesseract"
    assert "max_file_bytes" in data


@pytest.mark.asyncio
async def test_ocr_scan_end_to_end_with_pii_and_risk(client, db):
    import io
    from PIL import Image, ImageDraw

    await create_user("ocr-pipeline-user")
    token = (await login(client, "ocr-pipeline-user"))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    img = Image.new("RGB", (600, 120), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 40), "CONFIDENTIAL: patient.record@hospital.org SSN 123-45-6789", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    files = {"upload": ("scanned_id.png", image_bytes, "image/png")}
    response = await client.post("/api/privacy/scan-ocr", files=files, headers=headers)
    assert response.status_code == 201, response.text
    data = response.json()

    assert "finding" in data
    finding = data["finding"]
    assert finding["user_id"] == "ocr-pipeline-user"
    assert finding["ocr_engine"] == "tesseract"
    assert finding["page_count"] == 1
    assert finding["file_type"] == "png"
    assert finding["sensitivity_score"] > 0
    entity_types = [e["entity_type"] for e in finding.get("entities", [])]
    assert any(e in entity_types for e in ("US_SSN", "EMAIL_ADDRESS"))

    # Verify risk assessment was executed
    assert "risk_assessment" in data
    if data["risk_assessment"]:
        assert "combined_score" in data["risk_assessment"]
        assert "risk_category" in data["risk_assessment"]

    # Verify original text/image is not stored in DB
    stored_finding = await db.pii_findings.find_one({"finding_id": finding["finding_id"]})
    assert stored_finding is not None
    assert "patient.record@hospital.org" not in str(stored_finding)
    assert "123-45-6789" not in str(stored_finding)

    # Verify metadata event was recorded
    event = await db.events.find_one({"event_id": finding["event_id"]})
    assert event is not None
    assert event["event_type"] == "privacy.file_scanned"
    assert event["metadata"]["scan_source"] == "ocr_upload"

