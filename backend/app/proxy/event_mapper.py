import uuid
from typing import Dict, Any, Optional
from app.models.event import EventModel, ActionEnum
from urllib.parse import urlparse
import logging
import hashlib
import re

logger = logging.getLogger(__name__)

class EventMapper:
    """Maps intercepted HTTP requests to standardized EventModel."""

    SENSITIVE_HEADERS = ['authorization', 'cookie', 'set-cookie', 'x-api-key']

    @classmethod
    def sanitize_headers(cls, headers: Dict[str, str]) -> Dict[str, str]:
        """Redacts sensitive headers."""
        sanitized = {}
        for k, v in headers.items():
            if k.lower() in cls.SENSITIVE_HEADERS:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = v
        return sanitized

    @classmethod
    def identify_saas(cls, host: str) -> str:
        """Identifies SaaS platform from host."""
        host = host.lower()
        if "googleapis.com" in host or "google.com" in host:
            return "google_drive"
        return "unknown_saas"

    @classmethod
    def map_action(cls, method: str, path: str, query: str, saas: str) -> ActionEnum:
        """Attempts to map HTTP method and path/query to a standardized action."""
        method = method.upper()
        path_query = (path + "?" + query).lower()
        
        # Simple heuristic mapping
        if method == "GET":
            if "download" in path_query or "alt=media" in path_query:
                return ActionEnum.DOWNLOAD
            return ActionEnum.ACCESS
        elif method == "POST":
            if "permissions" in path_query or "acl" in path_query or "share" in path_query:
                return ActionEnum.PERMISSION_CHANGE
            if "upload" in path_query:
                return ActionEnum.UPLOAD
            return ActionEnum.MODIFY
        elif method in ["PUT", "PATCH"]:
            if "permissions" in path_query or "acl" in path_query:
                return ActionEnum.PERMISSION_CHANGE
            return ActionEnum.MODIFY
        elif method == "DELETE":
            return ActionEnum.DELETE
            
        return ActionEnum.ACCESS

    @classmethod
    def extract_resource_info(cls, path: str, saas: str) -> Optional[str]:
        """Extract resource ID from path if available."""
        if saas == "google_drive":
            # Typical Drive API path: /drive/v3/files/1A2B3C...
            match = re.search(r'/files/([a-zA-Z0-9_-]+)', path)
            if match:
                return match.group(1)
        return None

    @classmethod
    def get_identity_from_headers(cls, headers: Dict[str, str]) -> Optional[str]:
        """Hash the authorization token to use as a session fallback identity."""
        for k, v in headers.items():
            if k.lower() == 'authorization' and v.lower().startswith('bearer '):
                token = v[7:].strip()
                # Hash the token so we don't expose it
                return "session_" + hashlib.sha256(token.encode()).hexdigest()[:12]
        return None

    @classmethod
    def create_event_from_request(
        cls, 
        method: str, 
        url: str, 
        headers: Dict[str, str],
        client_ip: str = "unknown",
        status_code: int = 0,
        content_type: str = "",
        request_size: int = 0,
        response_size: int = 0
    ) -> EventModel:
        """Converts HTTP metadata to a standardized event."""
        parsed_url = urlparse(url)
        host = parsed_url.hostname or ""
        path = parsed_url.path
        
        saas = cls.identify_saas(host)
        action = cls.map_action(method, path, parsed_url.query, saas)
        resource_id = cls.extract_resource_info(path, saas)
        
        session_id = cls.get_identity_from_headers(headers)
        # The proxy cannot assert a trusted employee identity. It reports an
        # opaque session fingerprint; user attribution requires a separate
        # verified mapping and is never accepted from the network payload.
        metadata = {
            "http_method": method,
            "host": host,
            "path": path,
            "query": parsed_url.query,
            "status_code": status_code,
            "content_type": content_type,
            "request_size": request_size,
            "response_size": response_size,
            "headers": cls.sanitize_headers(headers),
            "identity_verified": False,
        }
        
        device_info = {
            "ip_address": client_ip
        }
        
        return EventModel(
            event_id=str(uuid.uuid4()),
            user_id=None,
            session_id=session_id,
            saas_app=saas,
            action=action,
            resource_id=resource_id,
            device_info=device_info,
            metadata=metadata
        )
