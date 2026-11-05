from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database.mongodb import ping_database

router = APIRouter()

APP_VERSION = "2.0.0"


@router.get("/health")
async def health_check():
    """Public liveness/readiness probe.

    Returns no configuration, credentials or exception text.
    """
    database_ok = await ping_database()
    body = {
        "status": "ok" if database_ok else "unhealthy",
        "database": "connected" if database_ok else "disconnected",
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if not database_ok:
        return JSONResponse(status_code=503, content=body)
    return body
