"""mitmproxy addon that forwards SaaS API metadata to the monitor backend.

Only request/response metadata is forwarded. Authorization, cookie and API-key
headers are redacted before the event is created. The proxy authenticates to
the backend with ``INGESTION_API_KEY`` and never supplies a trusted user
identity.
"""

import logging
import os

import httpx
from mitmproxy import http

from app.core.config import settings
from app.proxy.event_mapper import EventMapper

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


class APIMonitorProxy:
    def __init__(self):
        self.api_url = f"{BACKEND_URL}{settings.API_V1_STR}/events"
        self.headers = {}
        if settings.INGESTION_API_KEY:
            self.headers["X-Ingestion-Key"] = settings.INGESTION_API_KEY
        self.client = httpx.AsyncClient(timeout=10.0, verify=True, headers=self.headers)

    async def send_event(self, event_data: dict):
        try:
            response = await self.client.post(self.api_url, json=event_data)
            if response.status_code not in (200, 201):
                # Avoid logging response bodies: they may contain internal detail.
                logger.error(
                    "Failed to ingest event %s: HTTP %s",
                    event_data.get("event_id"),
                    response.status_code,
                )
            else:
                logger.info("Ingested event %s", event_data.get("event_id"))
        except httpx.HTTPError as exc:
            logger.error(
                "Error sending event %s to backend: %s",
                event_data.get("event_id"),
                type(exc).__name__,
            )

    async def response(self, flow: http.HTTPFlow):
        """Intercept responses for known SaaS hosts only."""
        host = flow.request.host
        saas_platform = EventMapper.identify_saas(host)
        if saas_platform == "unknown_saas":
            return

        method = flow.request.method
        url = flow.request.url
        headers = dict(flow.request.headers)

        status_code = flow.response.status_code if flow.response else 0
        content_type = flow.response.headers.get("Content-Type", "") if flow.response else ""
        request_size = len(flow.request.content) if flow.request.content else 0
        response_size = len(flow.response.content) if flow.response and flow.response.content else 0

        client_ip = (
            flow.client_conn.peername[0]
            if flow.client_conn and flow.client_conn.peername
            else "unknown"
        )

        event = EventMapper.create_event_from_request(
            method=method,
            url=url,
            headers=headers,
            client_ip=client_ip,
            status_code=status_code,
            content_type=content_type,
            request_size=request_size,
            response_size=response_size,
        )

        logger.info(
            "SaaS=%s method=%s action=%s status=%s",
            event.saas_app,
            method,
            event.action,
            status_code,
        )
        await self.send_event(event.model_dump(mode="json"))

    async def done(self):
        await self.client.aclose()


addons = [APIMonitorProxy()]
