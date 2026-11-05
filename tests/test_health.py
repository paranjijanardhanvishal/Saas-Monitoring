"""Public health endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_health_is_public_and_does_not_leak_configuration(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert set(body) == {"status", "database", "version", "timestamp"}
    text = response.text.lower()
    for secret_name in ("jwt_secret", "ingestion", "mongodb_uri", "password"):
        assert secret_name not in text


@pytest.mark.asyncio
async def test_health_reports_unhealthy_when_database_unreachable(client, monkeypatch):
    async def _down():
        return False

    monkeypatch.setattr("app.api.health.ping_database", _down)
    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "version" in response.json()
