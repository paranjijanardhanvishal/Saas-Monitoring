import uuid
from typing import Dict, Any, Optional
from app.models.event import EventModel, ActionEnum
from urllib.parse import urlparse
import logging

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
    def create_event_from_request(
        cls, 
        method: str, 
        url: str, 
        headers: Dict[str, str],
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
        
        # Basic parsing for user identity - relies on external injection if available, otherwise unknown
        # Since we don't inspect auth tokens, user identification is limited at the proxy layer
        user_id = "unknown"
        
        metadata = {
            "http_method": method,
            "host": host,
            "path": path,
            "query": parsed_url.query, # could sanitize query params
            "status_code": status_code,
            "content_type": content_type,
            "request_size": request_size,
            "response_size": response_size,
            "headers": cls.sanitize_headers(headers)
        }
        
        return EventModel(
            event_id=str(uuid.uuid4()),
            user_id=user_id,
            file_id=None, # File ID extraction requires deeper SaaS-specific parsing
            action=action,
            source=saas,
            metadata=metadata
        )
