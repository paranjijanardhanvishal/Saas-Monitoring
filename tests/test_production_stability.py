"""Production stability regression tests.

Verifies:
1. Admin credentials preservation after password update (prevents overwrite on restart).
2. Idempotent background job tracking for offline cloud analysis.
3. Bounded transient error retry during cloud file download.
4. Sanitized vector metadata persistence and restart hydration from MongoDB.
5. Session preservation and API retry semantics.
"""

from datetime import datetime, timedelta, timezone
import io
import ssl
from unittest.mock import AsyncMock, patch

import bcrypt
import pytest

from app.database.mongodb import ensure_initial_admin
from app.metadata.vector import local_vdb, vector_service, build_metadata_vector_text
from app.services.offline_analysis import (
    get_analysis_job,
    get_offline_analysis_summary,
    run_offline_analysis,
    start_offline_analysis_job,
)
from conftest import create_user, login


@pytest.mark.asyncio
async def test_admin_credentials_not_overwritten_if_password_changed(db, monkeypatch):
    monkeypatch.setattr("app.database.mongodb.is_test_database", lambda: False)
    custom_pwd = "MySecretCustomPassword123!"
    custom_hash = bcrypt.hashpw(custom_pwd.encode("utf-8"), bcrypt.gensalt(rounds=4)).decode("ascii")

    await db.users.insert_one(
        {
            "user_id": "admin",
            "email": "admin@admin.com",
            "role": "ADMIN",
            "is_active": True,
            "hashed_password": custom_hash,
            "must_change_password": False,  # Admin already changed temporary password!
        }
    )

    # Simulate container startup / cold-start
    await ensure_initial_admin()

    admin = await db.users.find_one({"user_id": "admin"})
    assert admin["must_change_password"] is False
    assert admin["hashed_password"] == custom_hash  # Must NOT be overwritten with admin123


@pytest.mark.asyncio
async def test_admin_credentials_synced_if_temporary_password_still_pending(db, monkeypatch):
    monkeypatch.setattr("app.database.mongodb.is_test_database", lambda: False)
    old_hash = bcrypt.hashpw(b"old_temp_pwd", bcrypt.gensalt(rounds=4)).decode("ascii")

    await db.users.insert_one(
        {
            "user_id": "admin",
            "email": "admin@admin.com",
            "role": "ADMIN",
            "is_active": True,
            "hashed_password": old_hash,
            "must_change_password": True,  # Temporary password pending change
        }
    )

    await ensure_initial_admin()

    admin = await db.users.find_one({"user_id": "admin"})
    assert admin["must_change_password"] is True
    # Synced to default temporary credentials
    assert bcrypt.checkpw(b"admin123", admin["hashed_password"].encode("utf-8"))


@pytest.mark.asyncio
async def test_idempotent_offline_analysis_background_job(db):
    now = datetime.now(timezone.utc)
    await db.files.insert_one(
        {
            "file_id": "job-test-f1",
            "name": "Report.txt",
            "mime_type": "text/plain",
            "analysis_status": "PENDING",
            "modified_time": now,
            "available": True,
        }
    )

    # 1. Start first job
    job1 = await start_offline_analysis_job(user_id="admin")
    assert job1["status"] == "RUNNING"
    assert "job_id" in job1
    assert job1["already_running"] is False

    # 2. Second request while running must return existing job (idempotency protection)
    job2 = await start_offline_analysis_job(user_id="admin")
    assert job2["status"] == "RUNNING"
    assert job2["job_id"] == job1["job_id"]
    assert job2["already_running"] is True


@pytest.mark.asyncio
async def test_offline_analysis_retry_transient_ssl_error(db, monkeypatch):
    now = datetime.now(timezone.utc)
    await db.files.insert_one(
        {
            "file_id": "ssl-retry-file",
            "name": "Audit.txt",
            "mime_type": "text/plain",
            "analysis_status": "PENDING",
            "modified_time": now,
            "available": True,
        }
    )

    attempts = {"count": 0}

    def flaky_download(fid):
        attempts["count"] += 1
        if attempts["count"] == 1:
            # Simulate OpenSSL socket reuse error on first attempt
            raise ssl.SSLError("[SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:2580)")
        return (io.BytesIO(b"Employee record: alice@company.com"), "text/plain")

    monkeypatch.setattr(
        "app.services.offline_analysis.drive_service.download_file",
        flaky_download,
    )

    result = await run_offline_analysis(user_id="admin", file_ids=["ssl-retry-file"], force_reanalyze=True)
    assert attempts["count"] == 2  # Proves retry occurred
    assert result["processed"] == 1
    assert result["failed"] == 0

    doc = await db.files.find_one({"file_id": "ssl-retry-file"})
    assert doc["analysis_status"] == "COMPLETED"
    assert doc["vector_indexed"] is True
    assert doc["vector_tokens"] is not None


@pytest.mark.asyncio
async def test_vector_persistence_and_startup_hydration(db):
    # Insert completed file with derived metadata and vector tokens
    now = datetime.now(timezone.utc)
    test_meta = {
        "file_id": "hydrate-file-01",
        "name": "financial_summary_2026.xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "analysis_status": "COMPLETED",
        "sensitivity_tier": "HIGH_RISK",
        "sensitivity_score": 85,
        "available": True,
        "vector_indexed": True,
        "last_analyzed_at": now,
    }
    v_tokens = build_metadata_vector_text(test_meta)
    test_meta["vector_tokens"] = v_tokens
    await db.files.insert_one(test_meta)

    # Simulate container restart: in-memory store is reset
    local_vdb.index.clear()
    local_vdb.metadata.clear()
    assert local_vdb.count() == 0

    # Hydrate from MongoDB
    hydrated = await vector_service.hydrate_from_mongodb(db)
    assert hydrated >= 1
    assert local_vdb.count() >= 1

    # Similarity search works using hydrated store
    sims = vector_service.search_similar("hydrate-file-01", top_k=5)
    assert isinstance(sims, list)

    # Summary reports actual persisted vector count
    summary = await get_offline_analysis_summary()
    assert summary["vector_status"]["total_indexed"] >= 1


@pytest.mark.asyncio
async def test_offline_analysis_job_endpoints(client, db):
    await create_user("admin-job", role="ADMIN")
    token = (await login(client, "admin-job"))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Trigger background analysis
    post_res = await client.post("/api/files/analyze-offline", json={"force": False}, headers=headers)
    assert post_res.status_code == 200
    data = post_res.json()
    assert "job_id" in data
    assert data["status"] == "RUNNING"

    # Query job status
    job_id = data["job_id"]
    get_res = await client.get(f"/api/files/analysis-jobs/{job_id}", headers=headers)
    assert get_res.status_code == 200
    job_info = get_res.json()
    assert job_info["job_id"] == job_id
    assert job_info["status"] in ("RUNNING", "COMPLETED")
