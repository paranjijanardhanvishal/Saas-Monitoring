import io
from unittest.mock import MagicMock

import pytest

from app.services import google_drive
from app.services.google_drive import GoogleDriveService


def test_authenticate_uses_service_account_file(monkeypatch, tmp_path):
    keyfile = tmp_path / "sa.json"
    keyfile.write_text("{}")
    credentials = MagicMock()
    monkeypatch.setattr("google.oauth2.service_account.Credentials.from_service_account_file", lambda *a, **kw: credentials)
    built = MagicMock()
    monkeypatch.setattr(google_drive, "build", lambda *a, **kw: built)
    service = GoogleDriveService(str(keyfile), "folder")
    assert service.authenticate() is built


def test_authentication_missing_key_is_disabled(tmp_path):
    assert GoogleDriveService(str(tmp_path / "missing.json"), "folder").authenticate() is None


def test_is_configured_and_get_status(tmp_path):
    keyfile = tmp_path / "sa.json"
    keyfile.write_text("{}")
    configured = GoogleDriveService(str(keyfile), " folder-123 ")
    assert configured.folder_id == "folder-123"
    assert configured.is_configured() is True
    assert configured.get_status() == {
        "configured": True,
        "credentials_file_present": True,
        "folder_configured": True,
    }

    missing_key = GoogleDriveService(str(tmp_path / "absent.json"), "folder-123")
    assert missing_key.is_configured() is False
    assert missing_key.get_status()["credentials_file_present"] is False

    missing_folder = GoogleDriveService(str(keyfile), "")
    assert missing_folder.is_configured() is False
    assert missing_folder.get_status()["folder_configured"] is False


def test_listing_is_folder_scoped_and_paginates():
    client = MagicMock()
    client.files().get.return_value.execute.return_value = {
        "id": "approved-folder", "name": "Approved", "mimeType": "application/vnd.google-apps.folder"
    }
    client.files().list.return_value.execute.side_effect = [
        {"files": [{"id": "f1", "name": "sample.pdf", "mimeType": "application/pdf"}], "nextPageToken": "next"},
        {"files": [{"id": "f2", "name": "sheet.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}]},
    ]
    service = GoogleDriveService("key", "approved-folder")
    service.service = client
    assert [f["id"] for f in service.list_files()] == ["f1", "f2"]
    call = client.files().list.call_args.kwargs
    assert "'approved-folder' in parents" in call["q"]
    assert "supportsAllDrives" not in call
    assert "includeItemsFromAllDrives" not in call
    client.files().get.assert_called_once_with(fileId="approved-folder", fields="id,name,mimeType,driveId")


def test_listing_reports_folder_probe_404():
    from googleapiclient.errors import HttpError
    from httplib2 import Response

    client = MagicMock()
    client.files().get.return_value.execute.side_effect = HttpError(
        Response({"status": "404"}), b'{"error":{"message":"File not found"}}'
    )
    service = GoogleDriveService("key", "inaccessible-folder")
    service.service = client
    with pytest.raises(RuntimeError, match=r"cannot access configured folder \(HTTP 404\)"):
        service.list_files()
    client.files().list.assert_not_called()


def test_download_uses_get_media_and_rejects_path_traversal(monkeypatch):
    client = MagicMock()
    request = MagicMock()
    request.headers = {"content-type": "text/plain"}
    client.files().get_media.return_value = request

    class Downloader:
        def __init__(self, output, media_request):
            self.output = output
        def next_chunk(self):
            self.output.write(b"mock bytes")
            return None, True

    monkeypatch.setattr(google_drive, "MediaIoBaseDownload", Downloader)
    service = GoogleDriveService("key", "folder")
    service.service = client
    stream, mime = service.download_file("real-id")
    assert stream.read() == b"mock bytes"
    assert mime == "text/plain"
    with pytest.raises(ValueError):
        service.download_file("../secret")


@pytest.mark.asyncio
async def test_roles_shared_file_access_and_download_events(client, db, monkeypatch):
    from app.api import files as file_api
    from conftest import create_user, login, bearer

    for role, uid in [("ADMIN", "drive-admin"), ("USER", "drive-user"), ("VISITOR", "drive-visitor")]:
        await create_user(uid, role=role)
    await db.files.insert_one({"file_id": "drive-file-1", "name": "test.pdf", "mime_type": "application/pdf", "size": 42,
                               "source": "google_drive", "available": True, "folder_id": "folder"})
    calls = []
    async def event_log(event):
        calls.append(event)
        await db.events.insert_one(event.model_dump())
        return True
    async def analyze(*args, **kwargs):
        calls.append("ewma")
    monkeypatch.setattr(file_api, "log_event", event_log)
    monkeypatch.setattr("app.behavior.service.analyze_behavior", analyze)
    monkeypatch.setattr(file_api.drive_service, "download_file", lambda _id: (io.BytesIO(b"file"), "application/pdf"))

    for role, uid in [("ADMIN", "drive-admin"), ("USER", "drive-user"), ("VISITOR", "drive-visitor")]:
        token = (await login(client, uid))["access_token"]
        headers = bearer(token)
        listing = await client.get("/api/files", headers=headers)
        assert listing.status_code == 200 and listing.json()[0]["file_id"] == "drive-file-1"
        downloaded = await client.get("/api/files/drive-file-1/download", headers=headers)
        if role == "VISITOR":
            assert downloaded.status_code == 403
        else:
            assert downloaded.status_code == 200 and downloaded.content == b"file"
    records = await db.events.find({"event_type": "file.download"}).to_list(length=10)
    assert len(records) == 2
    assert {record["user_id"] for record in records} == {"drive-admin", "drive-user"}
    assert "ewma" in calls


@pytest.mark.asyncio
async def test_missing_cloud_file_and_provider_failure(client, db, monkeypatch):
    from app.api import files as file_api
    from conftest import create_user, login, bearer

    await create_user("drive-user-fail", role="USER")
    token = (await login(client, "drive-user-fail"))["access_token"]
    headers = bearer(token)
    missing = await client.get("/api/files/missing/download", headers=headers)
    assert missing.status_code == 404
    await db.files.insert_one({"file_id": "drive-fails", "name": "x.csv", "mime_type": "text/csv", "source": "google_drive", "available": True})
    from googleapiclient.errors import HttpError
    from httplib2 import Response
    provider_error = HttpError(Response({"status": "500"}), b'{"error":{"message":"provider unavailable"}}')
    monkeypatch.setattr(file_api.drive_service, "download_file", MagicMock(side_effect=provider_error))
    response = await client.get("/api/files/drive-fails/download", headers=headers)
    assert response.status_code == 502
    assert await db.events.count_documents({"event_type": "file.download"}) == 0
