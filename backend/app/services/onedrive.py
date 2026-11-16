"""Microsoft OneDrive / SharePoint integration service using Microsoft Graph API.

Supports multi-cloud SaaS security monitoring:
- OAuth2 Client Credentials authentication against Microsoft Entra ID (Azure AD).
- Read-only metadata discovery with pagination support.
- Safe in-memory content retrieval for offline content inspection.
- Provider-aware identity normalization preventing ID collisions with Google Drive.
- Never stores credentials or raw file payloads in persistent logs or vector representations.

Required Microsoft Entra ID Application Permission:
- Files.Read.All (Application type, requires Entra ID administrator consent).
"""

from __future__ import annotations

from datetime import datetime, timezone
import io
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100MB bound


class OneDriveService:
    """Modular Microsoft Graph API client for OneDrive / SharePoint document libraries."""

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        drive_id: Optional[str] = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._drive_id = drive_id

        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._last_status: str = "not_configured"
        self._last_error: Optional[str] = None
        self._last_sync_at: Optional[datetime] = None
        self._last_delivery_at: Optional[datetime] = None

    @property
    def tenant_id(self) -> str:
        return (self._tenant_id or os.environ.get("ONEDRIVE_TENANT_ID") or getattr(settings, "ONEDRIVE_TENANT_ID", "")).strip()

    @property
    def client_id(self) -> str:
        return (self._client_id or os.environ.get("ONEDRIVE_CLIENT_ID") or getattr(settings, "ONEDRIVE_CLIENT_ID", "")).strip()

    @property
    def client_secret(self) -> str:
        return (self._client_secret or os.environ.get("ONEDRIVE_CLIENT_SECRET") or getattr(settings, "ONEDRIVE_CLIENT_SECRET", "")).strip()

    @property
    def drive_id(self) -> str:
        return (self._drive_id or os.environ.get("ONEDRIVE_DRIVE_ID") or getattr(settings, "ONEDRIVE_DRIVE_ID", "")).strip()

    def is_configured(self) -> bool:
        """Check if all required Microsoft Graph API credentials are configured."""
        return bool(self.tenant_id and self.client_id and self.client_secret and self.drive_id)

    def get_status(self) -> Dict[str, Any]:
        """Return non-sensitive configuration status and runtime health."""
        if not self.is_configured():
            return {
                "configured": False,
                "state": "NOT CONFIGURED",
                "status": "not_configured",
                "drive_configured": bool(self.drive_id),
                "credentials_present": bool(self.tenant_id and self.client_id and self.client_secret),
                "last_sync_at": self._last_sync_at,
                "last_delivery_at": self._last_delivery_at,
            }
        if self._last_status == "failed":
            return {
                "configured": True,
                "state": "ERROR",
                "status": "failed",
                "drive_configured": True,
                "credentials_present": True,
                "error": self._last_error or "Microsoft Graph API failure",
                "last_sync_at": self._last_sync_at,
                "last_delivery_at": self._last_delivery_at,
            }
        return {
            "configured": True,
            "state": "CONFIGURED",
            "status": "configured",
            "drive_configured": True,
            "credentials_present": True,
            "last_sync_at": self._last_sync_at,
            "last_delivery_at": self._last_delivery_at,
        }

    def get_access_token(self) -> str:
        """Retrieve or refresh Microsoft Graph OAuth2 application access token.

        Requires Microsoft Entra ID admin consent for Files.Read.All.
        """
        if not self.is_configured():
            raise RuntimeError("OneDrive integration is not configured")

        # Return cached token if valid (buffer of 60 seconds before expiration)
        if self._token and time.time() < (self._token_expires_at - 60):
            return self._token

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }

        try:
            response = requests.post(
                token_url,
                data=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
                verify=True,
            )
            if response.status_code == 401:
                self._last_status = "failed"
                self._last_error = "Authentication failed (401 Unauthorized)"
                logger.error("Microsoft Graph authentication failed: Invalid client credentials")
                raise RuntimeError("OneDrive authentication failed: Invalid client credentials")
            elif response.status_code == 403:
                self._last_status = "failed"
                self._last_error = "Authorization failed (403 Forbidden)"
                logger.error("Microsoft Graph authorization failed: Entra ID admin consent required for Files.Read.All")
                raise RuntimeError("OneDrive authorization failed: Entra ID admin consent required for Files.Read.All")

            response.raise_for_status()
            data = response.json()
            token = data.get("access_token")
            expires_in = int(data.get("expires_in", 3600))
            if not token:
                raise RuntimeError("OAuth2 token endpoint returned no access token")

            self._token = token
            self._token_expires_at = time.time() + expires_in
            self._last_status = "configured"
            self._last_error = None
            return token
        except requests.RequestException as exc:
            self._token = None
            self._last_status = "failed"
            self._last_error = str(type(exc).__name__)
            logger.error("OneDrive token acquisition request failed: %s", type(exc).__name__)
            raise RuntimeError(f"OneDrive connection failed: {type(exc).__name__}") from exc

    def list_files(self, max_items: int = 500) -> List[Dict[str, Any]]:
        """Discover read-only OneDrive file metadata using Microsoft Graph API with pagination."""
        if not self.is_configured():
            raise RuntimeError("OneDrive integration is not configured")

        token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        url: Optional[str] = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root/children?$top=100"
        records: List[Dict[str, Any]] = []

        while url and len(records) < max_items:
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    verify=True,
                )
                if response.status_code == 401:
                    # Invalidate cached token on 401 and retry once
                    self._token = None
                    token = self.get_access_token()
                    headers["Authorization"] = f"Bearer {token}"
                    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, verify=True)
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "5")
                    logger.warning("Microsoft Graph API rate limited (429). Retry-After: %s", retry_after)
                    self._last_status = "failed"
                    self._last_error = "Rate limit exceeded (429)"
                    raise RuntimeError("OneDrive API rate limit exceeded")

                response.raise_for_status()
                res_data = response.json()

                items = res_data.get("value", [])
                for item in items:
                    # Filter out folders, synchronize documents only
                    if "folder" in item:
                        continue

                    raw_id = str(item.get("id"))
                    file_name = str(item.get("name", "untitled"))
                    mime_type = item.get("file", {}).get("mimeType") or "application/octet-stream"
                    size = item.get("size", 0)

                    # Extract owner/creator details
                    created_by_user = item.get("createdBy", {}).get("user", {})
                    owner_email = created_by_user.get("email") or created_by_user.get("userPrincipalName")
                    owner_name = created_by_user.get("displayName")

                    # Parse timestamps
                    created_dt = self._parse_iso_datetime(item.get("createdDateTime"))
                    modified_dt = self._parse_iso_datetime(item.get("lastModifiedDateTime"))

                    # Provider-aware unique file ID prevents collision with Google Drive IDs
                    namespaced_id = f"onedrive_{raw_id}"

                    records.append({
                        "id": namespaced_id,
                        "provider_file_id": raw_id,
                        "name": file_name,
                        "mimeType": mime_type,
                        "size": size,
                        "createdTime": created_dt,
                        "modifiedTime": modified_dt,
                        "source": "onedrive",
                        "drive_id": self.drive_id,
                        "webUrl": item.get("webUrl"),
                        "owners": [{"emailAddress": owner_email, "displayName": owner_name}] if owner_email else [],
                    })

                # Follow Graph API pagination
                url = res_data.get("@odata.nextLink")
            except requests.RequestException as exc:
                self._last_status = "failed"
                self._last_error = str(type(exc).__name__)
                logger.error("OneDrive metadata discovery failed: %s", type(exc).__name__)
                raise RuntimeError(f"OneDrive metadata discovery failed: {type(exc).__name__}") from exc

        self._last_status = "configured"
        self._last_error = None
        self._last_sync_at = datetime.now(timezone.utc)
        return records

    def download_file(self, file_id: str) -> Tuple[io.BytesIO, str]:
        """Download document content into memory from OneDrive using Microsoft Graph API.

        Accepts either namespaced ID (onedrive_...) or raw Graph item ID.
        Returns (BytesIO, content_type).
        """
        if not self.is_configured():
            raise RuntimeError("OneDrive integration is not configured")

        raw_id = file_id.removeprefix("onedrive_") if file_id.startswith("onedrive_") else file_id
        token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
        }

        download_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{raw_id}/content"

        try:
            response = requests.get(
                download_url,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
                verify=True,
                stream=True,
            )
            if response.status_code == 401:
                self._token = None
                token = self.get_access_token()
                headers["Authorization"] = f"Bearer {token}"
                response = requests.get(download_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, verify=True, stream=True)
            elif response.status_code == 404:
                raise ValueError("The requested OneDrive document was not found or has been deleted.")
            elif response.status_code == 429:
                raise RuntimeError("OneDrive API rate limit exceeded")

            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "application/octet-stream")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
                raise ValueError("The requested file exceeds the 100MB download limit.")

            buffer = io.BytesIO()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if buffer.tell() + len(chunk) > MAX_DOWNLOAD_BYTES:
                    buffer.close()
                    raise ValueError("The requested file exceeds the 100MB download limit.")
                buffer.write(chunk)

            buffer.seek(0)
            self._last_delivery_at = datetime.now(timezone.utc)
            return buffer, content_type
        except requests.RequestException as exc:
            self._last_status = "failed"
            self._last_error = str(type(exc).__name__)
            logger.error("OneDrive file download failed for %s: %s", raw_id, type(exc).__name__)
            raise RuntimeError(f"OneDrive content download failed: {type(exc).__name__}") from exc

    @staticmethod
    def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        """Safely parse ISO 8601 timestamps returned by Microsoft Graph."""
        if not value:
            return None
        try:
            # Normalize trailing Z to UTC timezone
            clean_str = value.replace("Z", "+00:00")
            return datetime.fromisoformat(clean_str)
        except Exception:
            return None


onedrive_service = OneDriveService()
