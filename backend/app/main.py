from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.database.mongodb import connect_to_mongo, close_mongo_connection
from app.api import health, files, events, users, privacy, behavior, risk, enforcement, alerts, incidents

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

origins = [origin.strip() for origin in settings.FRONTEND_URL.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(files.router, prefix=settings.API_V1_STR, tags=["files"])
app.include_router(events.router, prefix=settings.API_V1_STR, tags=["events"])
app.include_router(users.router, prefix=settings.API_V1_STR, tags=["users"])
app.include_router(privacy.router, prefix=settings.API_V1_STR + "/privacy", tags=["privacy"])
app.include_router(behavior.router, prefix=settings.API_V1_STR + "/behavior", tags=["behavior"])
app.include_router(risk.router, prefix=settings.API_V1_STR + "/risk", tags=["risk"])
app.include_router(enforcement.router, prefix=settings.API_V1_STR + "/enforcement", tags=["enforcement"])
app.include_router(alerts.router, prefix=settings.API_V1_STR + "/alerts", tags=["alerts"])
app.include_router(incidents.router, prefix=settings.API_V1_STR + "/incidents", tags=["incidents"])

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}
