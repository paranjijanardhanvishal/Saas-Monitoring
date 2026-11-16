"""Tests for Phase 6 Microsoft OneDrive integration, metadata discovery, content retrieval, and offline analysis."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.user import UserModel
from app.services.monitoring import persist_files
from app.services.onedrive import OneDriveService, onedrive_service


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.files = MagicMock()
    db.users = MagicMock()
    db.events = MagicMock()
    db.audit_logs = MagicMock()
    db.analysis_jobs = MagicMock()
    db.pii_findings = MagicMock()
    db.command = AsyncMock(return_value={"ok": 1})
    return db


def test_unconfigured_onedrive_service():
    service = OneDriveService(tenant_id="", client_id="", client_secret="", drive_id="")
    assert not service.is_configured()
    status = service.get_status()
    assert status["configured"] is False
    assert status["state"] == "NOT CONFIGURED"
    assert status["status"] == "not_configured"

    with pytest.raises(RuntimeError, match="not configured"):
        service.get_access_token()

    with pytest.raises(RuntimeError, match="not configured"):
        service.list_files()

    with pytest.raises(RuntimeError, match="not configured"):
        service.download_file("onedrive_123")


def test_token_acquisition_and_caching():
    service = OneDriveService(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
        drive_id="test-drive",
    )
    assert service.is_configured()

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "mock-access-token-12345",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_response

        # First call retrieves token via HTTP POST
        token1 = service.get_access_token()
        assert token1 == "mock-access-token-12345"
        assert mock_post.call_count == 1
        assert "login.microsoftonline.com/test-tenant/oauth2/v2.0/token" in mock_post.call_args[0][0]
        assert mock_post.call_args[1]["data"]["client_id"] == "test-client"
        assert mock_post.call_args[1]["data"]["grant_type"] == "client_credentials"

        # Second call reuses cached token
        token2 = service.get_access_token()
        assert token2 == "mock-access-token-12345"
        assert mock_post.call_count == 1  # No second HTTP call


def test_token_acquisition_auth_errors():
    service = OneDriveService(
        tenant_id="test-tenant",
        client_id="bad-client",
        client_secret="bad-secret",
        drive_id="test-drive",
    )

    # 401 Unauthorized
    with patch("requests.post") as mock_post:
        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401
        mock_post.return_value = mock_resp_401

        with pytest.raises(RuntimeError, match="Invalid client credentials"):
            service.get_access_token()
        assert service.get_status()["state"] == "ERROR"

    # 403 Forbidden (Consent required)
    with patch("requests.post") as mock_post:
        mock_resp_403 = MagicMock()
        mock_resp_403.status_code = 403
        mock_post.return_value = mock_resp_403

        with pytest.raises(RuntimeError, match="admin consent required"):
            service.get_access_token()
        assert service.get_status()["state"] == "ERROR"


def test_metadata_discovery_with_pagination_and_namespace():
    service = OneDriveService(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
        drive_id="drive-abc-123",
    )
    service._token = "valid-token"
    service._token_expires_at = datetime.now(timezone.utc).timestamp() + 3600

    page_1_data = {
        "value": [
            {
                "id": "item001",
                "name": "Customer_List.xlsx",
                "file": {"mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                "size": 45000,
                "createdDateTime": "2026-03-01T10:00:00Z",
                "lastModifiedDateTime": "2026-03-02T12:00:00Z",
                "webUrl": "https://company.sharepoint.com/Customer_List.xlsx",
                "createdBy": {
                    "user": {"email": "alice@company.com", "displayName": "Alice Admin"}
                },
            },
            {
                # Subfolder should be filtered out
                "id": "folder001",
                "name": "Archive",
                "folder": {"childCount": 5},
            },
        ],
        "@odata.nextLink": "https://graph.microsoft.com/v1.0/drives/drive-abc-123/root/children?$top=100&$skiptoken=xyz",
    }

    page_2_data = {
        "value": [
            {
                "id": "item002",
                "name": "Secrets.pdf",
                "file": {"mimeType": "application/pdf"},
                "size": 89000,
                "createdDateTime": "2026-03-03T10:00:00Z",
                "lastModifiedDateTime": "2026-03-04T12:00:00Z",
                "webUrl": "https://company.sharepoint.com/Secrets.pdf",
                "createdBy": {
                    "user": {"email": "bob@company.com", "displayName": "Bob Builder"}
                },
            }
        ]
    }

    with patch("requests.get") as mock_get:
        resp_1 = MagicMock()
        resp_1.status_code = 200
        resp_1.json.return_value = page_1_data

        resp_2 = MagicMock()
        resp_2.status_code = 200
        resp_2.json.return_value = page_2_data

        mock_get.side_effect = [resp_1, resp_2]

        items = service.list_files()
        assert len(items) == 2
        assert mock_get.call_count == 2

        # Verify provider-aware identity prefix
        assert items[0]["id"] == "onedrive_item001"
        assert items[0]["provider_file_id"] == "item001"
        assert items[0]["name"] == "Customer_List.xlsx"
        assert items[0]["source"] == "onedrive"
        assert items[0]["drive_id"] == "drive-abc-123"
        assert items[0]["owners"][0]["emailAddress"] == "alice@company.com"

        assert items[1]["id"] == "onedrive_item002"
        assert items[1]["provider_file_id"] == "item002"
        assert items[1]["name"] == "Secrets.pdf"
        assert items[1]["source"] == "onedrive"


def test_download_file_stream_and_bounds():
    service = OneDriveService(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
        drive_id="drive-abc-123",
    )
    service._token = "valid-token"
    service._token_expires_at = datetime.now(timezone.utc).timestamp() + 3600

    content_bytes = b"Hello from OneDrive file content!"

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Type": "text/plain",
            "Content-Length": str(len(content_bytes)),
        }
        mock_response.iter_content.return_value = [content_bytes]
        mock_get.return_value = mock_response

        # Both onedrive_item001 and item001 should resolve properly
        stream, mime = service.download_file("onedrive_item001")
        assert mime == "text/plain"
        assert stream.read() == content_bytes
        stream.close()

        # Check URL queried strips prefix
        called_url = mock_get.call_args[0][0]
        assert "/drives/drive-abc-123/items/item001/content" in called_url


def test_download_file_oversized_rejected():
    service = OneDriveService(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
        drive_id="drive-abc-123",
    )
    service._token = "valid-token"
    service._token_expires_at = datetime.now(timezone.utc).timestamp() + 3600

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(150 * 1024 * 1024),  # 150MB > 100MB limit
        }
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="exceeds the 100MB download limit"):
            service.download_file("onedrive_large_file")


@pytest.mark.asyncio
async def test_persist_files_provider_aware_upsert():
    mock_db = MagicMock()
    mock_db.files = MagicMock()
    mock_db.files.update_one = AsyncMock(return_value=MagicMock())

    with patch("app.services.monitoring.get_database", return_value=mock_db):
        onedrive_items = [
            {
                "id": "onedrive_abc123",
                "provider_file_id": "abc123",
                "name": "Report.docx",
                "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size": 12000,
                "createdTime": datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
                "modifiedTime": datetime(2026, 3, 2, 10, 0, 0, tzinfo=timezone.utc),
                "source": "onedrive",
                "drive_id": "shared-drive-99",
                "webUrl": "https://company.sharepoint.com/Report.docx",
                "owners": [{"emailAddress": "auditor@company.com", "displayName": "Auditor"}],
            }
        ]

        count = await persist_files(onedrive_items)
        assert count == 1
        assert mock_db.files.update_one.call_count == 1

        call_filter, call_update = mock_db.files.update_one.call_args[0]
        assert call_filter == {"file_id": "onedrive_abc123", "source": "onedrive"}
        assert call_update["$set"]["source"] == "onedrive"
        assert call_update["$set"]["provider_file_id"] == "abc123"
        assert call_update["$set"]["drive_id"] == "shared-drive-99"
        assert call_update["$set"]["web_url"] == "https://company.sharepoint.com/Report.docx"


@pytest.mark.asyncio
async def test_offline_analysis_routes_by_provider():
    from app.services.offline_analysis import run_offline_analysis

    mock_db = MagicMock()
    mock_db.files = MagicMock()
    mock_db.analysis_jobs = MagicMock()
    mock_db.pii_findings = MagicMock()

    # Create one Google Drive doc and one OneDrive doc
    gdrive_doc = {
        "file_id": "gdrive_doc_1",
        "name": "gdrive_file.txt",
        "mime_type": "text/plain",
        "source": "google_drive",
        "folder_id": "folder-123",
        "available": True,
        "modified_time": datetime.now(timezone.utc),
    }

    onedrive_doc = {
        "file_id": "onedrive_item_2",
        "provider_file_id": "item_2",
        "name": "onedrive_file.txt",
        "mime_type": "text/plain",
        "source": "onedrive",
        "drive_id": "drive-456",
        "available": True,
        "modified_time": datetime.now(timezone.utc),
    }

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[gdrive_doc, onedrive_doc])
    mock_db.files.find.return_value = mock_cursor
    mock_db.files.find_one = AsyncMock(side_effect=lambda q: gdrive_doc if q.get("file_id") == "gdrive_doc_1" else onedrive_doc)
    mock_db.files.update_one = AsyncMock()
    mock_db.analysis_jobs.update_one = AsyncMock()

    with patch("app.services.offline_analysis.get_database", return_value=mock_db), \
         patch("app.services.offline_analysis.drive_service.download_file") as mock_gdrive_dl, \
         patch("app.services.offline_analysis.onedrive_service.download_file") as mock_onedrive_dl, \
         patch("app.services.offline_analysis.analyze_text") as mock_analyze:

        mock_gdrive_dl.return_value = (io.BytesIO(b"Google Drive document text"), "text/plain")
        mock_onedrive_dl.return_value = (io.BytesIO(b"OneDrive document text"), "text/plain")
        mock_analyze.return_value = MagicMock(
            findings=[],
            sensitivity_score=10,
            sensitivity_tier="LOW",
            model_dump=lambda: {"findings": [], "sensitivity_score": 10, "sensitivity_tier": "LOW"},
        )

        summary = await run_offline_analysis(user_id="admin-1")

        assert summary["total"] == 2
        assert summary["processed"] == 2

        # Check that drive_service was called for gdrive_doc_1
        mock_gdrive_dl.assert_called_once_with("gdrive_doc_1")
        # Check that onedrive_service was called with raw provider_file_id "item_2"
        mock_onedrive_dl.assert_called_once_with("item_2")


def test_system_health_integration_status():
    from app.api.system import system_health

    mock_db = MagicMock()
    mock_db.command = AsyncMock(return_value={"ok": 1})
    mock_db.__getitem__ = MagicMock(return_value=MagicMock(count_documents=AsyncMock(return_value=5)))

    admin_user = UserModel(
        user_id="admin_01",
        email="admin@example.com",
        display_name="Admin",
        role="ADMIN",
    )

    with patch("app.api.system.get_database", return_value=mock_db), \
         patch("app.api.system.onedrive_service.is_configured", return_value=True), \
         patch("app.api.system.onedrive_service.get_status", return_value={"configured": True, "state": "CONFIGURED", "status": "configured"}):

        import asyncio
        health = asyncio.run(system_health(current_user=admin_user))

        integrations = health["integrations"]
        assert integrations["onedrive_configured"] is True
        assert integrations["onedrive"]["state"] == "CONFIGURED"


@pytest.mark.asyncio
async def test_onedrive_api_status_and_sync_endpoints():
    from app.api.files import get_onedrive_status, sync_onedrive_files

    admin_user = UserModel(
        user_id="admin_01",
        email="admin@example.com",
        display_name="Admin",
        role="ADMIN",
    )
    regular_user = UserModel(
        user_id="user_01",
        email="user@example.com",
        display_name="User",
        role="USER",
    )

    # 1. Status endpoint
    with patch("app.api.files.onedrive_service.get_status", return_value={"configured": False, "state": "NOT CONFIGURED"}):
        res = await get_onedrive_status(current_user=regular_user)
        assert res["state"] == "NOT CONFIGURED"

    # 2. Sync endpoint forbids non-admin
    from fastapi import HTTPException
    mock_request = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        await sync_onedrive_files(request=mock_request, current_user=regular_user)
    assert exc_info.value.status_code == 403

    # 3. Sync endpoint succeeds for admin
    mock_db = MagicMock()
    mock_db.files = MagicMock()
    mock_db.files.update_one = AsyncMock()
    mock_db.files.update_many = AsyncMock()
    mock_db.audit_logs = MagicMock()
    mock_db.audit_logs.insert_one = AsyncMock()

    sync_items = [
        {
            "id": "onedrive_101",
            "provider_file_id": "101",
            "name": "Financial_Report.pdf",
            "mimeType": "application/pdf",
            "size": 50000,
            "createdTime": datetime.now(timezone.utc),
            "modifiedTime": datetime.now(timezone.utc),
            "source": "onedrive",
            "drive_id": "test-drive-id",
        }
    ]

    with patch("app.api.files.get_database", return_value=mock_db), \
         patch("app.api.files.onedrive_service.list_files", return_value=sync_items), \
         patch.object(onedrive_service, "_drive_id", "test-drive-id"), \
         patch("app.api.files.persist_files", AsyncMock(return_value=1)), \
         patch("app.api.files.record_audit", AsyncMock()) as mock_audit:

        sync_res = await sync_onedrive_files(request=mock_request, current_user=admin_user)
        assert sync_res == {"synchronized": 1}
        assert mock_db.files.update_many.call_count == 2
        mock_audit.assert_called_once()


@pytest.mark.asyncio
async def test_onedrive_download_endpoint_and_telemetry():
    from app.api.files import download_cloud_file
    from fastapi import HTTPException

    admin_user = UserModel(
        user_id="admin_01",
        email="admin@example.com",
        display_name="Admin",
        role="ADMIN",
    )
    unauthorized_user = UserModel(
        user_id="user_stranger",
        email="stranger@other.com",
        display_name="Stranger",
        role="USER",
    )

    mock_db = MagicMock()
    mock_db.files = MagicMock()
    mock_db.users = MagicMock()
    mock_db.events = MagicMock()
    mock_db.audit_logs = MagicMock()

    private_onedrive_doc = {
        "file_id": "onedrive_priv_1",
        "provider_file_id": "priv_1",
        "name": "Confidential.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "source": "onedrive",
        "drive_id": None,  # Not in shared drive
        "owner_email": "owner@company.com",
        "available": True,
    }

    shared_onedrive_doc = {
        "file_id": "onedrive_shared_1",
        "provider_file_id": "shared_1",
        "name": "Policy.pdf",
        "mime_type": "application/pdf",
        "source": "onedrive",
        "drive_id": "shared-corp-drive",
        "owner_email": "corp@company.com",
        "available": True,
    }

    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"

    # Non-admin trying to download unshared file not owned by them -> 404
    mock_db.files.find_one = AsyncMock(return_value=private_onedrive_doc)
    with patch("app.api.files.get_database", return_value=mock_db), \
         patch("app.api.files.record_audit", AsyncMock()):
        with pytest.raises(HTTPException) as exc_info:
            await download_cloud_file("onedrive_priv_1", request=mock_request, current_user=unauthorized_user)
        assert exc_info.value.status_code == 404

    # Non-admin downloading file from shared OneDrive library -> Allowed, streamed, event logged with saas_app="onedrive"
    mock_db.files.find_one = AsyncMock(return_value=shared_onedrive_doc)
    mock_db.users.find_one = AsyncMock(return_value={"user_id": unauthorized_user.user_id, "business_role": "GENERAL"})

    with patch("app.api.files.get_database", return_value=mock_db), \
         patch("app.api.files.onedrive_service.download_file", return_value=(io.BytesIO(b"Shared file stream"), "application/pdf")), \
         patch("app.api.files.log_event", AsyncMock(return_value=True)) as mock_log_event, \
         patch("app.api.files.record_audit", AsyncMock()), \
         patch("app.behavior.service.analyze_behavior", AsyncMock()):

        response = await download_cloud_file("onedrive_shared_1", request=mock_request, current_user=unauthorized_user)
        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="Policy.pdf"'

        # Verify telemetry logged saas_app="onedrive"
        mock_log_event.assert_called_once()
        logged_event = mock_log_event.call_args[0][0]
        assert logged_event.saas_app == "onedrive"
        assert logged_event.resource_id == "onedrive_shared_1"

