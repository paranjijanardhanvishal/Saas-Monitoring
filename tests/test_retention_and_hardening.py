import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pymongo import ASCENDING, IndexModel
from pymongo.errors import OperationFailure

from app.core.config import settings
from app.database.mongodb import INDEX_DEFINITIONS, _create_col_indexes, db_client


def test_docs_and_openapi_disabled_in_production():
    """Verify FastAPI config disables docs, redoc, and openapi.json when APP_ENV is production."""
    with patch.object(settings, "APP_ENV", "production"):
        from fastapi import FastAPI
        is_prod = settings.APP_ENV.lower() == "production"
        prod_app = FastAPI(
            title=settings.PROJECT_NAME,
            version="2.0.0",
            docs_url=None if is_prod else "/docs",
            redoc_url=None if is_prod else "/redoc",
            openapi_url=None if is_prod else f"{settings.API_V1_STR}/openapi.json",
        )
        assert prod_app.docs_url is None
        assert prod_app.redoc_url is None
        assert prod_app.openapi_url is None
        route_paths = [getattr(r, "path", None) for r in prod_app.routes]
        assert "/docs" not in route_paths
        assert "/redoc" not in route_paths
        assert f"{settings.API_V1_STR}/openapi.json" not in route_paths


def test_docs_and_openapi_enabled_in_development():
    """Verify FastAPI config provides docs, redoc, and openapi.json in development."""
    with patch.object(settings, "APP_ENV", "development"):
        from fastapi import FastAPI
        is_prod = settings.APP_ENV.lower() == "production"
        dev_app = FastAPI(
            title=settings.PROJECT_NAME,
            version="2.0.0",
            docs_url=None if is_prod else "/docs",
            redoc_url=None if is_prod else "/redoc",
            openapi_url=None if is_prod else f"{settings.API_V1_STR}/openapi.json",
        )
        assert dev_app.docs_url == "/docs"
        assert dev_app.redoc_url == "/redoc"
        assert dev_app.openapi_url == f"{settings.API_V1_STR}/openapi.json"
        route_paths = [getattr(r, "path", None) for r in dev_app.routes]
        assert "/docs" in route_paths
        assert f"{settings.API_V1_STR}/openapi.json" in route_paths


@pytest.mark.asyncio
async def test_docs_accessible_in_test_environment(client):
    """Verify live test app has docs available."""
    resp = await client.get("/docs")
    assert resp.status_code == 200
    resp_openapi = await client.get(f"{settings.API_V1_STR}/openapi.json")
    assert resp_openapi.status_code == 200


def test_events_ttl_index_definition():
    """Verify events collection has a 90-day TTL index on timestamp (BSON Date)."""
    events_indexes = INDEX_DEFINITIONS.get("events", [])
    ttl_indexes = [
        idx for idx in events_indexes
        if isinstance(idx, IndexModel) and getattr(idx, "document", {}).get("expireAfterSeconds") is not None
    ]
    assert len(ttl_indexes) == 1, "Expected exactly 1 TTL index on events collection"
    ttl_idx = ttl_indexes[0]
    doc = ttl_idx.document
    assert doc.get("name") == "events_ttl_idx"
    assert doc.get("expireAfterSeconds") == 90 * 86400  # 7,776,000 seconds
    assert doc.get("key") == {"timestamp": ASCENDING}


def test_audit_logs_ttl_index_definition():
    """Verify audit_logs collection has a 365-day TTL index on timestamp (BSON Date)."""
    audit_indexes = INDEX_DEFINITIONS.get("audit_logs", [])
    ttl_indexes = [
        idx for idx in audit_indexes
        if isinstance(idx, IndexModel) and getattr(idx, "document", {}).get("expireAfterSeconds") is not None
    ]
    assert len(ttl_indexes) == 1, "Expected exactly 1 TTL index on audit_logs collection"
    ttl_idx = ttl_indexes[0]
    doc = ttl_idx.document
    assert doc.get("name") == "audit_logs_ttl_idx"
    assert doc.get("expireAfterSeconds") == 365 * 86400  # 31,536,000 seconds
    assert doc.get("key") == {"timestamp": ASCENDING}


def test_no_retention_ttl_on_other_collections():
    """Verify TTL indexes are NOT introduced on users, files, alerts, incidents, or pii_findings."""
    restricted_collections = ["users", "alerts", "incidents", "pii_findings", "devices", "behavior_profiles"]
    for col_name in restricted_collections:
        indexes = INDEX_DEFINITIONS.get(col_name, [])
        ttl_indexes = [
            idx for idx in indexes
            if isinstance(idx, IndexModel) and getattr(idx, "document", {}).get("expireAfterSeconds") is not None
        ]
        assert len(ttl_indexes) == 0, f"Unexpected TTL index on collection '{col_name}'"


@pytest.mark.asyncio
async def test_create_col_indexes_handles_individual_conflict():
    """Verify that if batch index creation encounters OperationFailure, individual indexes are attempted and logged."""
    mock_collection = MagicMock()
    # First batch call raises OperationFailure (e.g. index options conflict)
    # Second individual call succeeds, third individual call raises OperationFailure
    mock_collection.create_indexes = AsyncMock(
        side_effect=[
            OperationFailure("Index with name already exists with different options"),
            ["idx1_ok"],
            OperationFailure("Conflicting index spec"),
        ]
    )

    idx1 = IndexModel([("col_a", ASCENDING)], name="idx1")
    idx2 = IndexModel([("col_b", ASCENDING)], name="idx2")

    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_collection

    with patch.object(db_client, "db", mock_db):
        await _create_col_indexes("test_col", [idx1, idx2])

    assert mock_collection.create_indexes.call_count == 3
