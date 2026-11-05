"""HTTP client for the monitoring backend.

TLS certificates are always verified. The client never sends a user password
or a user-selected identity; only the enrolled device token is used.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from .config import validate_backend_url

logger = logging.getLogger(__name__)

MAX_BATCHES = 10


class AgentError(RuntimeError):
    pass


class AgentTransportError(AgentError):
    pass


class AgentAuthError(AgentError):
    def __init__(self, message: str, status_code: int, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class AgentClient:
    def __init__(
        self,
        backend_url: str,
        device_token: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: int = 15,
    ):
        self.backend_url = validate_backend_url(backend_url)
        self.device_token = device_token
        self.timeout = timeout
        self.session = session or requests.Session()

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "SaaSMonitorAgent/2.0"}
        if self.device_token:
            headers["X-Device-Token"] = self.device_token
        return headers

    def _request(
        self, method: str, path: str, *, json: Any = None, params: Optional[dict] = None
    ) -> Dict[str, Any]:
        url = f"{self.backend_url}{path}"
        try:
            response = self.session.request(
                method,
                url,
                json=json,
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
                verify=True,
            )
        except requests.RequestException as exc:
            raise AgentTransportError(
                f"Could not reach the backend ({type(exc).__name__})"
            ) from exc

        if response.status_code in (401, 403):
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            raise AgentAuthError(
                "Device credential rejected or monitoring is not permitted",
                response.status_code,
                detail,
            )
        if response.status_code >= 400:
            raise AgentTransportError(
                f"Backend returned HTTP {response.status_code} for {method} {path}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise AgentTransportError("Backend returned a non-JSON response") from exc

    def enroll(
        self,
        enrollment_token: str,
        device_id: str,
        hostname: str,
        os_version: str,
        agent_version: str,
    ) -> Dict[str, Any]:
        data = self._request(
            "POST",
            "/agent/enroll",
            json={
                "enrollment_token": enrollment_token,
                "device_id": device_id,
                "hostname": hostname[:255],
                "os_version": os_version[:255],
                "agent_version": agent_version[:32],
            },
        )
        if not data.get("device_token"):
            raise AgentError("Enrollment succeeded but no device token was returned")
        return data

    def heartbeat(
        self, hostname: str, os_version: str, agent_version: str, monitoring_active: bool = True
    ) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/agent/heartbeat",
            json={
                "hostname": hostname[:255],
                "os_version": os_version[:255],
                "agent_version": agent_version[:32],
                "monitoring_active": monitoring_active,
            },
        )

    def send_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not events:
            return {"accepted": 0, "duplicates": 0, "rejected": [], "received": 0}
        if len(events) > 200:
            raise AgentError("Event batch exceeds the server limit of 200")
        return self._request("POST", "/agent/events", json=events)

    def close(self) -> None:
        self.session.close()
