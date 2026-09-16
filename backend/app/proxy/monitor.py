import asyncio
import httpx
from mitmproxy import http
import logging
from app.proxy.event_mapper import EventMapper
from app.core.config import settings

logger = logging.getLogger(__name__)

class APIMonitorProxy:
    def __init__(self):
        self.api_url = f"http://127.0.0.1:8000{settings.API_V1_STR}/events"
        # We use an async client to send events to the backend without blocking the proxy
        self.client = httpx.AsyncClient()

    async def send_event(self, event_data: dict):
        try:
            response = await self.client.post(self.api_url, json=event_data)
            if response.status_code not in (200, 201):
                logger.error(f"Failed to ingest event: {response.status_code} - {response.text}")
            else:
                logger.info(f"Successfully ingested event {event_data.get('event_id')} to backend.")
        except Exception as e:
            logger.error(f"Error sending event to backend: {e}")

    def response(self, flow: http.HTTPFlow):
        """Intercepts HTTP responses to gather complete request/response metadata."""
        # Filter for relevant SaaS APIs. We don't want to log every single web request.
        # But for this Step, we will let event_mapper decide if it's a known saas.
        
        host = flow.request.host
        saas_platform = EventMapper.identify_saas(host)
        
        if saas_platform == "unknown_saas":
            return # Skip irrelevant traffic

        method = flow.request.method
        url = flow.request.url
        headers = dict(flow.request.headers)
        
        status_code = flow.response.status_code if flow.response else 0
        content_type = flow.response.headers.get("Content-Type", "") if flow.response else ""
        request_size = len(flow.request.content) if flow.request.content else 0
        response_size = len(flow.response.content) if flow.response and flow.response.content else 0
        
        event = EventMapper.create_event_from_request(
            method=method,
            url=url,
            headers=headers,
            status_code=status_code,
            content_type=content_type,
            request_size=request_size,
            response_size=response_size
        )
        
        logger.info(f"[INFO] SaaS={event.source} Method={method} Action={event.action} User={event.user_id} Status={status_code}")

        # Dispatch the event to the FastAPI backend asynchronously
        event_dict = event.model_dump(mode='json')
        # Schedule the coroutine in mitmproxy's event loop
        asyncio.create_task(self.send_event(event_dict))

addons = [
    APIMonitorProxy()
]
