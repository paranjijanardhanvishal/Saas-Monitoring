"""Database configuration and index tests. No production database is touched."""

import certifi
import pytest

from app.database import mongodb


def test_local_uri_does_not_enable_tls(monkeypatch):
    monkeypatch.setattr(mongodb.settings, "MONGODB_URI", "mongodb://localhost:27017")
    assert mongodb._tls_options() == {}


def test_remote_uri_validates_certificates(monkeypatch):
    monkeypatch.setattr(
        mongodb.settings,
        "MONGODB_URI",
        "mongodb+srv://user:pass@cluster.example.mongodb.net",
    )
    options = mongodb._tls_options()
    assert options == {"tlsCAFile": certifi.where()}
    assert "tlsAllowInvalidCertificates" not in options


def test_test_database_guard(monkeypatch):
    monkeypatch.setattr(mongodb.settings, "MONGO_DB_NAME", "saas_monitor_test")
    assert mongodb.is_test_database() is True
    monkeypatch.setattr(mongodb.settings, "MONGO_DB_NAME", "saas_monitor")
    assert mongodb.is_test_database() is False


@pytest.mark.asyncio
async def test_drop_test_database_refuses_non_test_database(monkeypatch):
    monkeypatch.setattr(mongodb.settings, "MONGO_DB_NAME", "saas_monitor")
    with pytest.raises(RuntimeError):
        await mongodb.drop_test_database()


@pytest.mark.asyncio
async def test_ensure_indexes_is_idempotent(db):
    await mongodb.ensure_indexes()
    await mongodb.ensure_indexes()
    indexes = await db.events.index_information()
    names = set(indexes)
    assert any("event_id" in name for name in names)
    alert_indexes = await db.alerts.index_information()
    unique = [info for info in alert_indexes.values() if info.get("unique")]
    assert unique, "alerts.dedupe_key must be a unique index"
