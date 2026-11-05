import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    agent,
    alerts,
    auth,
    behavior,
    dashboard,
    demo,
    enforcement,
    events,
    files,
    health,
    incidents,
    investigation,
    privacy,
    risk,
    system,
    users,
)
from app.core.config import settings
from app.database.mongodb import close_mongo_connection, connect_to_mongo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    logger.info("API startup complete for environment '%s'", settings.APP_ENV)
    yield
    await close_mongo_connection()
    logger.info("API shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="2.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

origins = [origin.strip() for origin in settings.FRONTEND_URL.split(",") if origin.strip()]
allow_all = "*" in origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=not allow_all,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Device-Token", "X-Ingestion-Key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.COOKIE_SECURE:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix=settings.API_V1_STR + "/auth", tags=["auth"])
app.include_router(files.router, prefix=settings.API_V1_STR, tags=["files"])
app.include_router(events.router, prefix=settings.API_V1_STR, tags=["events"])
app.include_router(users.router, prefix=settings.API_V1_STR, tags=["users"])
app.include_router(privacy.router, prefix=settings.API_V1_STR + "/privacy", tags=["privacy"])
app.include_router(behavior.router, prefix=settings.API_V1_STR + "/behavior", tags=["behavior"])
app.include_router(risk.router, prefix=settings.API_V1_STR + "/risk", tags=["risk"])
app.include_router(enforcement.router, prefix=settings.API_V1_STR + "/enforcement", tags=["enforcement"])
app.include_router(alerts.router, prefix=settings.API_V1_STR + "/alerts", tags=["alerts"])
app.include_router(incidents.router, prefix=settings.API_V1_STR + "/incidents", tags=["incidents"])
app.include_router(agent.router, prefix=settings.API_V1_STR + "/agent", tags=["agent"])
app.include_router(dashboard.router, prefix=settings.API_V1_STR, tags=["dashboard"])
app.include_router(demo.router, prefix=settings.API_V1_STR + "/demo", tags=["demo"])
app.include_router(investigation.router, prefix=settings.API_V1_STR, tags=["investigation"])
app.include_router(system.router, prefix=settings.API_V1_STR, tags=["system"])


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}", "version": "2.0.0"}
