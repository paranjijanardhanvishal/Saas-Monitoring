"""Shared test configuration.

Integration tests use a dedicated MongoDB database whose name ends in ``_test``.
The database is dropped between tests. No production data is touched.
"""

import os

# These values must be set before app.core.config is imported. They are test
# fixtures, not real credentials.
os.environ["APP_ENV"] = "test"
os.environ["MONGO_DB_NAME"] = "saas_monitor_test"
os.environ["JWT_SECRET_KEY"] = "test-only-jwt-secret-value-that-is-at-least-32-chars"
os.environ["INGESTION_API_KEY"] = "test-ingestion-key"
os.environ["PII_ENGINE"] = "regex"
os.environ["AUTO_RISK_ENABLED"] = "true"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SLACK_WEBHOOK_URL"] = ""
os.environ["JIRA_API_URL"] = ""
os.environ["JIRA_AUTH_TOKEN"] = ""

from datetime import datetime, timezone
from typing import Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.rate_limit import login_limiter
from app.core.security import get_password_hash
from app.database.mongodb import (
    close_mongo_connection,
    connect_to_mongo,
    db_client,
    ensure_indexes,
    get_database,
)
from app.main import app
from app.models.user import UserModel

TEST_PASSWORD = "CorrectHorseBattery42"


async def create_user(
    user_id: str,
    email: Optional[str] = None,
    role: str = "USER",
    password: str = TEST_PASSWORD,
    consent: str = "ALLOWED",
    is_active: bool = True,
    enforcement_status: str = "ACTIVE",
    hashed_password: Optional[str] = None,
    display_name: Optional[str] = None,
) -> dict:
    """Insert a user directly with a valid password hash."""
    document = UserModel(
        user_id=user_id,
        email=email or f"{user_id}@example.com",
        display_name=display_name or user_id,
        role=role,
        monitoring_enabled=consent,
        hashed_password=hashed_password or get_password_hash(password),
        is_active=is_active,
        enforcement_status=enforcement_status,
        consent_updated_at=datetime.now(timezone.utc) if consent != "NOT_ASKED" else None,
    ).model_dump()
    await get_database().users.insert_one(document)
    return document


async def login(
    client: AsyncClient, username: str, password: str = TEST_PASSWORD
) -> dict:
    response = await client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def csrf_headers(client: AsyncClient) -> dict:
    token = client.cookies.get("csrf_token")
    assert token, "csrf_token cookie was not set by login"
    return {"X-CSRF-Token": token}


async def create_device(
    user_id: str,
    device_id: str = "device-test-0001",
    token: str = "dev_test_token_value",
) -> dict:
    from app.core.security import hash_token

    device = {
        "device_id": device_id,
        "user_id": user_id,
        "hostname": "TESTHOST",
        "os_version": "Windows 11",
        "agent_version": "2.0.0",
        "status": "ACTIVE",
        "monitoring_enabled": True,
        "token_hash": hash_token(token),
        "token_prefix": token[:12],
        "enrolled_at": datetime.now(timezone.utc),
        "last_heartbeat": None,
        "revoked_at": None,
        "revoked_reason": None,
    }
    await get_database().devices.insert_one(device)
    return device


def device_headers(token: str = "dev_test_token_value") -> dict:
    return {"X-Device-Token": token}


@pytest.fixture(autouse=True)
def reset_login_limiter():
    """Keep the in-process login limiter from leaking between tests."""
    login_limiter._events.clear()
    yield
    login_limiter._events.clear()


@pytest_asyncio.fixture
async def client():
    assert settings.MONGO_DB_NAME.endswith("_test"), "Refusing to run tests against a non-test database"
    await connect_to_mongo()
    if db_client.client is None:
        pytest.fail("MongoDB is not available for integration tests")
    await db_client.client.drop_database(settings.MONGO_DB_NAME)
    await ensure_indexes()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
    await close_mongo_connection()


@pytest_asyncio.fixture
async def db(client):
    return get_database()
