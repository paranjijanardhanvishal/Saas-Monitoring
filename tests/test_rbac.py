"""Role-based access control and per-user data isolation tests."""

from datetime import datetime, timezone

import pytest

from conftest import create_user, login


def _event(event_id: str, user_id: str, **overrides) -> dict:
    document = {
        "event_id": event_id,
        "event_type": "saas.activity",
        "user_id": user_id,
        "source": "endpoint_agent",
        "saas_app": "endpoint",
        "action": "ACCESS",
        "timestamp": datetime.now(timezone.utc),
        "ingestion_timestamp": datetime.now(timezone.utc),
        "metadata": {},
    }
    document.update(overrides)
    return document


@pytest.mark.asyncio
async def test_user_directory_is_restricted_for_user_and_visitor(client, db):
    await create_user("admin-rbac", role="ADMIN")
    await create_user("member-rbac", email="member-secret@example.com", display_name="Private Member", consent="ALLOWED")
    await create_user("visitor-rbac", email="visitor-secret@example.com", display_name="Private Visitor", role="VISITOR", consent="ALLOWED")
    admin = {"Authorization": f"Bearer {(await login(client, 'admin-rbac'))['access_token']}"}
    member = {"Authorization": f"Bearer {(await login(client, 'member-rbac'))['access_token']}"}
    visitor = {"Authorization": f"Bearer {(await login(client, 'visitor-rbac'))['access_token']}"}

    # ADMIN: full directory with full details
    admin_list = await client.get("/api/users", headers=admin)
    assert admin_list.status_code == 200
    ids = {u["user_id"] for u in admin_list.json()}
    assert {"admin-rbac", "member-rbac"} <= ids
    assert next(u for u in admin_list.json() if u["user_id"] == "member-rbac")["email"] == "member-secret@example.com"

    # USER: read-only directory with full emails and names
    member_list = await client.get("/api/users", headers=member)
    assert member_list.status_code == 200
    member_entry = next(u for u in member_list.json() if u["user_id"] == "member-rbac")
    assert member_entry["email"] == "member-secret@example.com"
    assert member_entry["display_name"] == "Private Member"
    assert "role" in member_entry
    assert "business_role" in member_entry
    assert "monitoring_enabled" in member_entry
    assert "enforcement_status" in member_entry

    # VISITOR: denied from /api/users (403)
    visitor_full = await client.get("/api/users", headers=visitor)
    assert visitor_full.status_code == 403

    # VISITOR: restricted directory with masked emails only
    directory = await client.get("/api/users/directory", headers=visitor)
    assert directory.status_code == 200
    assert {entry["user_id"] for entry in directory.json()} >= {"admin-rbac", "member-rbac", "visitor-rbac"}
    # Emails are masked for VISITOR
    assert "member-secret@example.com" not in directory.text
    visitor_entry = next(e for e in directory.json() if e["user_id"] == "visitor-rbac")
    assert visitor_entry["email"].startswith("v*")
    # Restricted directory does NOT expose consent, enforcement, or dates
    for entry in directory.json():
        assert "monitoring_enabled" not in entry
        assert "enforcement_status" not in entry
        assert "created_at" not in entry


@pytest.mark.asyncio
async def test_directory_requires_auth_and_rejects_unexpected_role(client):
    from types import SimpleNamespace

    from app.core.dependencies import get_current_user
    from app.main import app

    assert (await client.get("/api/users/directory")).status_code == 401

    async def unexpected_role():
        return SimpleNamespace(user_id="unexpected-role", role="SERVICE")

    app.dependency_overrides[get_current_user] = unexpected_role
    try:
        response = await client.get("/api/users/directory")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_user_and_visitor_cannot_access_profiles_or_write_users(client, db):
    await create_user("restricted-user", consent="ALLOWED")
    await create_user("restricted-visitor", role="VISITOR", consent="ALLOWED")
    headers_by_role = {
        "USER": {"Authorization": f"Bearer {(await login(client, 'restricted-user'))['access_token']}"},
        "VISITOR": {"Authorization": f"Bearer {(await login(client, 'restricted-visitor'))['access_token']}"},
    }
    for headers in headers_by_role.values():
        for url in (
            "/api/users/restricted-user",
            "/api/users/restricted-user/summary",
            "/api/users/restricted-user/devices",
        ):
            assert (await client.get(url, headers=headers)).status_code == 403
        assert (await client.post(
            "/api/users",
            json={"user_id": "blocked-user", "email": "blocked@example.com", "password": "ValidPassword123"},
            headers=headers,
        )).status_code == 403
        assert (await client.patch(
            "/api/users/restricted-user", json={"display_name": "Changed"}, headers=headers
        )).status_code == 403
        assert (await client.patch(
            "/api/users/restricted-user/business-role", json={"business_role": "FINANCE"}, headers=headers
        )).status_code == 403
        assert (await client.delete("/api/users/restricted-user", headers=headers)).status_code == 403
        assert (await client.post(
            "/api/agent/enrollment-token?user_id=restricted-user", headers=headers
        )).status_code == 403
    assert await db.users.count_documents({"user_id": "blocked-user"}) == 0


@pytest.mark.asyncio
async def test_admin_retains_user_crud_access(client, db):
    await create_user("crud-admin", role="ADMIN")
    await create_user("crud-target")
    admin = {"Authorization": f"Bearer {(await login(client, 'crud-admin'))['access_token']}"}

    detail = await client.get("/api/users/crud-target", headers=admin)
    assert detail.status_code == 200
    assert detail.json()["email"] == "crud-target@example.com"

    created = await client.post(
        "/api/users",
        json={"user_id": "crud-created", "email": "created@example.com", "password": "ValidPassword123"},
        headers=admin,
    )
    assert created.status_code == 201
    updated = await client.patch(
        "/api/users/crud-target", json={"role": "VISITOR", "display_name": "Updated"}, headers=admin
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "VISITOR"
    business = await client.patch(
        "/api/users/crud-target/business-role", json={"business_role": "FINANCE"}, headers=admin
    )
    assert business.status_code == 200
    assert business.json()["business_role"] == "FINANCE"
    deleted = await client.delete("/api/users/crud-created", headers=admin)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_user_can_read_only_self_profile(client, db):
    await create_user("self-user")
    await create_user("other-user")
    headers = {"Authorization": f"Bearer {(await login(client, 'self-user'))['access_token']}"}

    assert (await client.get("/api/users/self-user", headers=headers)).status_code == 200
    assert (await client.get("/api/users/other-user", headers=headers)).status_code == 403
    assert (await client.get("/api/users/other-user/summary", headers=headers)).status_code == 403
    assert (await client.get("/api/users/other-user/devices", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_event_listing_is_scoped(client, db):
    await create_user("event-owner")
    await create_user("event-other")
    await create_user("event-admin", role="ADMIN")
    await db.events.insert_many(
        [_event("event-own-0001", "event-owner"), _event("event-oth-0001", "event-other")]
    )
    owner = {"Authorization": f"Bearer {(await login(client, 'event-owner'))['access_token']}"}
    admin = {"Authorization": f"Bearer {(await login(client, 'event-admin'))['access_token']}"}

    owner_events = await client.get("/api/events", headers=owner)
    assert owner_events.status_code == 200
    assert [e["event_id"] for e in owner_events.json()] == ["event-own-0001"]

    admin_events = await client.get("/api/events", headers=admin)
    assert len(admin_events.json()) == 2

    foreign = await client.get("/api/events/event-oth-0001", headers=owner)
    assert foreign.status_code == 403


@pytest.mark.asyncio
async def test_alert_and_incident_lists_are_scoped(client, db):
    from bson import ObjectId

    await create_user("alert-owner")
    await create_user("alert-other")
    await create_user("alert-admin", role="ADMIN")
    now = datetime.now(timezone.utc)
    await db.alerts.insert_many(
        [
            {
                "_id": ObjectId(),
                "severity": "HIGH",
                "title": "owner alert",
                "reason": "owner",
                "user_id": "alert-owner",
                "status": "OPEN",
                "source": "risk_engine",
                "timestamp": now,
            },
            {
                "_id": ObjectId(),
                "severity": "HIGH",
                "title": "other alert",
                "reason": "other",
                "user_id": "alert-other",
                "status": "OPEN",
                "source": "risk_engine",
                "timestamp": now,
            },
        ]
    )
    await db.incidents.insert_many(
        [
            {
                "_id": ObjectId(),
                "title": "owner incident",
                "severity": "HIGH",
                "status": "OPEN",
                "user_id": "alert-owner",
                "reason": "owner",
                "created_time": now,
            },
            {
                "_id": ObjectId(),
                "title": "other incident",
                "severity": "HIGH",
                "status": "OPEN",
                "user_id": "alert-other",
                "reason": "other",
                "created_time": now,
            },
        ]
    )

    owner = {"Authorization": f"Bearer {(await login(client, 'alert-owner'))['access_token']}"}
    admin = {"Authorization": f"Bearer {(await login(client, 'alert-admin'))['access_token']}"}

    owner_alerts = await client.get("/api/alerts", headers=owner)
    assert owner_alerts.status_code == 200
    assert [a["title"] for a in owner_alerts.json()] == ["owner alert"]

    admin_alerts = await client.get("/api/alerts", headers=admin)
    assert len(admin_alerts.json()) == 2

    owner_incidents = await client.get("/api/incidents", headers=owner)
    assert [i["title"] for i in owner_incidents.json()] == ["owner incident"]

    # Users cannot perform SOC actions.
    alert_id = owner_alerts.json()[0]["id"]
    denied = await client.patch(
        f"/api/alerts/{alert_id}/status",
        json={"status": "ACKNOWLEDGED"},
        headers=owner,
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_files_are_isolated_by_owner_email(client, db):
    await create_user("file-alice", email="alice@example.com")
    await create_user("file-bob", email="bob@example.com")
    now = datetime.now(timezone.utc)
    await db.files.insert_many(
        [
            {
                "file_id": "file-alice-1",
                "name": "alice.txt",
                "mime_type": "text/plain",
                "owner_email": "alice@example.com",
                "modified_time": now,
            },
            {
                "file_id": "file-bob-1",
                "name": "bob.txt",
                "mime_type": "text/plain",
                "owner_email": "bob@example.com",
                "modified_time": now,
            },
        ]
    )
    alice = {"Authorization": f"Bearer {(await login(client, 'file-alice'))['access_token']}"}
    files = await client.get("/api/files", headers=alice)
    assert [f["file_id"] for f in files.json()] == ["file-alice-1"]
    assert (await client.get("/api/files/file-bob-1", headers=alice)).status_code == 404


@pytest.mark.asyncio
async def test_dashboard_is_role_scoped(client, db):
    await create_user("dash-user")
    await create_user("dash-admin", role="ADMIN")
    await db.events.insert_many(
        [_event("dash-event-0001", "dash-user"), _event("dash-event-0002", "dash-admin")]
    )
    user = {"Authorization": f"Bearer {(await login(client, 'dash-user'))['access_token']}"}
    admin = {"Authorization": f"Bearer {(await login(client, 'dash-admin'))['access_token']}"}

    user_view = await client.get("/api/dashboard/overview", headers=user)
    assert user_view.status_code == 200
    assert user_view.json()["scope"] == "USER"
    assert user_view.json()["events"]["last_24h"] == 1
    assert "account" in user_view.json()
    assert "users" not in user_view.json()

    admin_view = await client.get("/api/dashboard/overview", headers=admin)
    assert admin_view.json()["scope"] == "ADMIN"
    assert admin_view.json()["events"]["last_24h"] == 2
    assert "users" in admin_view.json()


@pytest.mark.asyncio
async def test_investigation_is_admin_scoped(client, db):
    await create_user("inv-user")
    await create_user("inv-other")
    await create_user("inv-admin", role="ADMIN")
    user = {"Authorization": f"Bearer {(await login(client, 'inv-user'))['access_token']}"}
    admin = {"Authorization": f"Bearer {(await login(client, 'inv-admin'))['access_token']}"}

    assert (await client.get("/api/investigation/search?q=inv", headers=user)).status_code == 403
    search = await client.get("/api/investigation/search?q=inv", headers=admin)
    assert search.status_code == 200
    assert {u["user_id"] for u in search.json()} >= {"inv-user", "inv-other", "inv-admin"}

    assert (await client.get("/api/investigation/users/inv-user", headers=user)).status_code == 200
    assert (await client.get("/api/investigation/users/inv-other", headers=user)).status_code == 403
    assert (await client.get("/api/investigation/users/inv-other", headers=admin)).status_code == 200


@pytest.mark.asyncio
async def test_system_endpoints_are_admin_only(client, db):
    await create_user("sys-user")
    await create_user("sys-admin", role="ADMIN")
    user = {"Authorization": f"Bearer {(await login(client, 'sys-user'))['access_token']}"}
    admin = {"Authorization": f"Bearer {(await login(client, 'sys-admin'))['access_token']}"}

    assert (await client.get("/api/system/health", headers=user)).status_code == 403
    health = await client.get("/api/system/health", headers=admin)
    assert health.status_code == 200
    assert health.json()["database"]["connected"] is True
    assert health.json()["privacy_engine"]["active"] in {"regex", "presidio", None}

    assert (await client.get("/api/system/audit-logs", headers=user)).status_code == 403
    logs = await client.get("/api/system/audit-logs", headers=admin)
    assert logs.status_code == 200
    # Logging in as the admin is itself audited.
    assert any(entry["action"] == "auth.login" for entry in logs.json())


@pytest.mark.asyncio
async def test_editor_and_visitor_roles_and_live_activity_gating(client, db):
    await create_user("demo-editor", role="EDITOR")
    await create_user("demo-visitor", role="VISITOR")
    await create_user("demo-admin", role="ADMIN")

    editor = {"Authorization": f"Bearer {(await login(client, 'demo-editor'))['access_token']}"}
    visitor = {"Authorization": f"Bearer {(await login(client, 'demo-visitor'))['access_token']}"}
    admin = {"Authorization": f"Bearer {(await login(client, 'demo-admin'))['access_token']}"}

    # 1. Live activity is strictly ADMIN only (Editor and Visitor get 403)
    assert (await client.get("/api/events", headers=editor)).status_code == 403
    assert (await client.get("/api/events", headers=visitor)).status_code == 403
    assert (await client.get("/api/events", headers=admin)).status_code == 200

    # 2. Users directory is visible to all SOC roles, with Visitor getting masked email
    editor_users = await client.get("/api/users", headers=editor)
    assert editor_users.status_code == 200
    editor_directory = await client.get("/api/users/directory", headers=editor)
    assert editor_directory.status_code == 200
    assert all(set(u) == {"user_id", "role"} for u in editor_directory.json())

    visitor_users = await client.get("/api/users/directory", headers=visitor)
    assert visitor_users.status_code == 200
    # The restricted directory contains no email or profile fields.
    assert all(set(u) == {"user_id", "role"} for u in visitor_users.json())
    assert (await client.get("/api/users", headers=visitor)).status_code == 403

    # 3. Only ADMIN can delete users (Editor and Visitor get 403)
    assert (await client.delete("/api/users/demo-visitor", headers=visitor)).status_code == 403
    assert (await client.delete("/api/users/demo-visitor", headers=editor)).status_code == 403
    assert (await client.delete("/api/users/demo-visitor", headers=admin)).status_code == 200
