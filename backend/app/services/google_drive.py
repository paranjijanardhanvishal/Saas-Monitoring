"""Backend-only Google Drive access using a mounted service-account key."""
import io
import logging
import os

from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from app.core.config import settings

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024


class GoogleDriveService:
    def __init__(self, credentials_path: str | None = None, folder_id: str | None = None):
        self._credentials_path = credentials_path
        self._folder_id = folder_id
        self.service = None
        self.service_account_email = None

    @property
    def credentials_path(self) -> str:
        if self._credentials_path:
            return self._credentials_path.strip().strip('"').strip("'")
        val = getattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", "") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        return (val or "").strip().strip('"').strip("'")

    @property
    def folder_id(self) -> str:
        if self._folder_id:
            return self._folder_id.strip().strip('"').strip("'")
        val = getattr(settings, "GOOGLE_DRIVE_FOLDER_ID", "") or os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        return (val or "").strip().strip('"').strip("'")

    def is_configured(self) -> bool:
        """Return True if credentials file exists and folder_id is set."""
        path = self.credentials_path
        return bool(path and os.path.isfile(path) and self.folder_id)

    def get_status(self) -> dict:
        """Return non-sensitive configuration status."""
        path = self.credentials_path
        has_file = bool(path and os.path.isfile(path))
        has_folder = bool(self.folder_id)
        return {
            "configured": bool(has_file and has_folder),
            "credentials_file_present": has_file,
            "folder_configured": has_folder,
        }

    def authenticate(self):
        """Build a Drive client from the Render-mounted service-account key."""
        path = self.credentials_path
        if not path or not os.path.isfile(path):
            logger.warning("Google Drive disabled: GOOGLE_APPLICATION_CREDENTIALS file is unavailable: %s", path)
            return None
        try:
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_file(
                path, scopes=SCOPES
            )
            self.service_account_email = credentials.service_account_email
            self.service = build("drive", "v3", credentials=credentials, cache_discovery=False)
            logger.info("Google Drive service account authenticated: %s", self.service_account_email)
            return self.service
        except (DefaultCredentialsError, ValueError, OSError) as exc:
            logger.exception("Google Drive service-account authentication failed: %s", exc)
            return None

    def _client(self):
        return self.service or self.authenticate()

    def get_current_user(self):
        """Return non-sensitive service-account identity for legacy sync callers."""
        if not self._client():
            return None
        return {"emailAddress": self.service_account_email} if self.service_account_email else None

    def list_files(self, page_size=100):
        """List all non-trashed direct children of the configured shared folder."""
        if not self.folder_id:
            raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID is not configured")
        client = self._client()
        if client is None:
            raise RuntimeError("Google Drive credentials are not configured")
        logger.info(
            "Checking Google Drive folder access: folder_id=%s service_account=%s",
            self.folder_id,
            self.service_account_email or "identity_unavailable",
        )
        try:
            folder = client.files().get(
                fileId=self.folder_id,
                fields="id,name,mimeType,driveId",
            ).execute()
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", "unknown")
            logger.error(
                "Google Drive folder probe failed: status=%s folder_id=%s service_account=%s",
                status,
                self.folder_id,
                self.service_account_email or "identity_unavailable",
            )
            raise RuntimeError(
                f"Google Drive cannot access configured folder (HTTP {status}); "
                "check the folder ID and sharing with the authenticated service account"
            ) from exc
        if folder.get("id") != self.folder_id or folder.get("mimeType") != "application/vnd.google-apps.folder":
            logger.error(
                "Configured Google Drive ID is not an accessible folder: folder_id=%s returned_id=%s mime_type=%s",
                self.folder_id,
                folder.get("id"),
                folder.get("mimeType"),
            )
            raise RuntimeError("Configured Google Drive ID is not an accessible folder")
        logger.info(
            "Google Drive folder access confirmed: folder_id=%s name=%s drive_id=%s",
            self.folder_id,
            folder.get("name", "[unnamed]"),
            folder.get("driveId", "my-drive"),
        )
        files, page_token = [], None
        fields = "nextPageToken,files(id,name,mimeType,size,owners(displayName,emailAddress),createdTime,modifiedTime,trashed)"
        while True:
            try:
                result = client.files().list(
                    q=f"'{self.folder_id}' in parents and trashed = false",
                    pageSize=min(max(page_size, 1), 1000),
                    pageToken=page_token,
                    fields=fields,
                ).execute()
            except HttpError as exc:
                status = getattr(getattr(exc, "resp", None), "status", "unknown")
                logger.error(
                    "Google Drive child listing failed after folder probe: status=%s folder_id=%s",
                    status,
                    self.folder_id,
                )
                raise
            batch = result.get("files", [])
            for item in batch:
                if not all(isinstance(item.get(key), str) and item[key] for key in ("id", "name", "mimeType")):
                    logger.warning("Ignoring malformed Drive file metadata")
                    continue
                files.append(item)
            page_token = result.get("nextPageToken")
            if not page_token:
                return files

    def download_file(self, file_id: str) -> tuple[io.BytesIO, str]:
        """Fetch bytes by validated provider ID; never return a Drive URL/token."""
        if not file_id or len(file_id) > 256 or any(c in file_id for c in "/\\"):
            raise ValueError("Invalid Google Drive file ID")
        client = self._client()
        if client is None:
            raise RuntimeError("Google Drive credentials are not configured")
        request = client.files().get_media(fileId=file_id)
        output = io.BytesIO()
        downloader = MediaIoBaseDownload(output, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
            if output.tell() > MAX_DOWNLOAD_BYTES:
                output.close()
                raise ValueError("Cloud file exceeds the 100 MiB download limit")
        output.seek(0)
        return output, request.headers.get("content-type", "application/octet-stream")


drive_service = GoogleDriveService()
