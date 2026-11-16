"""Unit and integration tests for File-to-User and User-to-File Relationship Mapping."""

from datetime import datetime, timezone
import pytest

from conftest import create_user, login


@pytest.mark.asyncio
async def test_file_to_user_mapping_admin(client, db):
    await create_user("rel-admin", role="ADMIN")
    await create_user("analyst-1", role="USER", email="analyst1@example.com")
    await create_user("analyst-2", role="USER", email="analyst2@example.com")
    admin_headers = {"Authorization": f"Bearer {(await login(client, 'rel-admin'))['access_token']}"}

    file_id = "test-doc-001"
    await db.files.insert_one({
        "file_id": file_id,
        "name": "Q3_Financial_Export.xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "size": 20480,
        "sensitivity_tier": "HIGH_RISK",
        "sensitivity_score": 85,
        "sharing_scope": "private",
        "owner_email": "analyst1@example.com",
        "available": True,
    })

    # Insert real events for this file
    now = datetime.now(timezone.utc)
    await db.events.insert_many([
        {
            "event_id": "ev-rel-01",
            "user_id": "analyst-1",
            "action": "DOWNLOAD",
            "resource_id": file_id,
            "resource_name": "Q3_Financial_Export.xlsx",
            "timestamp": now,
        },
        {
            "event_id": "ev-rel-02",
            "user_id": "analyst-1",
            "action": "ACCESS",
            "resource_id": file_id,
            "resource_name": "Q3_Financial_Export.xlsx",
            "timestamp": now,
        },
        {
            "event_id": "ev-rel-03",
            "user_id": "analyst-2",
            "action": "ACCESS",
            "resource_id": file_id,
            "resource_name": "Q3_Financial_Export.xlsx",
            "timestamp": now,
        },
    ])

    response = await client.get(f"/api/relationships/files/{file_id}", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == file_id
    assert data["total_events"] == 3
    assert data["unique_users_count"] == 2

    users_map = {u["user_id"]: u for u in data["users"]}
    assert "analyst-1" in users_map
    assert users_map["analyst-1"]["total_interactions"] == 2
    assert users_map["analyst-1"]["actions"] == {"DOWNLOAD": 1, "ACCESS": 1}
    assert users_map["analyst-1"]["is_owner"] is True

    assert "analyst-2" in users_map
    assert users_map["analyst-2"]["total_interactions"] == 1
    assert users_map["analyst-2"]["actions"] == {"ACCESS": 1}
    assert users_map["analyst-2"]["is_owner"] is False


@pytest.mark.asyncio
async def test_file_to_user_mapping_non_admin_privacy_isolation(client, db):
    await create_user("user-alice", role="USER")
    await create_user("user-bob", role="USER")
    alice_headers = {"Authorization": f"Bearer {(await login(client, 'user-alice'))['access_token']}"}

    file_id = "shared-sheet-002"
    await db.files.insert_one({
        "file_id": file_id,
        "name": "Shared_Roadmap.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "folder_id": "folder-123",
        "available": True,
    })

    now = datetime.now(timezone.utc)
    await db.events.insert_many([
        {
            "event_id": "ev-p-01",
            "user_id": "user-alice",
            "action": "DOWNLOAD",
            "resource_id": file_id,
            "timestamp": now,
        },
        {
            "event_id": "ev-p-02",
            "user_id": "user-bob",
            "action": "DOWNLOAD",
            "resource_id": file_id,
            "timestamp": now,
        },
    ])

    # Alice queries file relationships: must only see her own interaction, never Bob's
    response = await client.get(f"/api/relationships/files/{file_id}", headers=alice_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_events"] == 1
    assert data["unique_users_count"] == 1
    assert data["users"][0]["user_id"] == "user-alice"
    assert "user-bob" not in [u["user_id"] for u in data["users"]]


@pytest.mark.asyncio
async def test_user_to_file_mapping_permissions(client, db):
    await create_user("admin-user-01", role="ADMIN")
    await create_user("target-user-01", role="USER")
    await create_user("other-user-01", role="USER")

    admin_headers = {"Authorization": f"Bearer {(await login(client, 'admin-user-01'))['access_token']}"}
    target_headers = {"Authorization": f"Bearer {(await login(client, 'target-user-01'))['access_token']}"}
    other_headers = {"Authorization": f"Bearer {(await login(client, 'other-user-01'))['access_token']}"}

    await db.files.insert_one({
        "file_id": "f-secret-01",
        "name": "Secret_Project.pdf",
        "mime_type": "application/pdf",
        "sensitivity_tier": "SENSITIVE",
        "sensitivity_score": 45,
        "available": True,
    })

    now = datetime.now(timezone.utc)
    await db.events.insert_one({
        "event_id": "ev-u-01",
        "user_id": "target-user-01",
        "action": "DOWNLOAD",
        "resource_id": "f-secret-01",
        "resource_name": "Secret_Project.pdf",
        "timestamp": now,
    })

    # 1. Self access succeeds
    resp_self = await client.get("/api/relationships/users/target-user-01", headers=target_headers)
    assert resp_self.status_code == 200
    assert resp_self.json()["total_files_accessed"] == 1
    assert resp_self.json()["files"][0]["file_id"] == "f-secret-01"
    assert resp_self.json()["files"][0]["sensitivity_tier"] == "SENSITIVE"

    # 2. Admin access succeeds
    resp_admin = await client.get("/api/relationships/users/target-user-01", headers=admin_headers)
    assert resp_admin.status_code == 200
    assert resp_admin.json()["total_files_accessed"] == 1

    # 3. Other non-admin user access is forbidden (403)
    resp_other = await client.get("/api/relationships/users/target-user-01", headers=other_headers)
    assert resp_other.status_code == 403


@pytest.mark.asyncio
async def test_relationships_summary(client, db):
    await create_user("sum-admin", role="ADMIN")
    headers = {"Authorization": f"Bearer {(await login(client, 'sum-admin'))['access_token']}"}

    now = datetime.now(timezone.utc)
    await db.events.insert_many([
        {"event_id": "e1", "user_id": "u1", "resource_id": "f1", "action": "ACCESS", "timestamp": now},
        {"event_id": "e2", "user_id": "u1", "resource_id": "f2", "action": "DOWNLOAD", "timestamp": now},
        {"event_id": "e3", "user_id": "u2", "resource_id": "f1", "action": "ACCESS", "timestamp": now},
    ])

    response = await client.get("/api/relationships/summary", headers=headers)
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_relationships"] == 3
    assert summary["unique_files_count"] == 2
    assert summary["unique_users_count"] == 2
    assert summary["action_breakdown"]["ACCESS"] == 2
    assert summary["action_breakdown"]["DOWNLOAD"] == 1


@pytest.mark.asyncio
async def test_zero_fake_data_when_no_interactions(client, db):
    await create_user("zero-admin", role="ADMIN")
    headers = {"Authorization": f"Bearer {(await login(client, 'zero-admin'))['access_token']}"}

    file_id = "f-lonely-01"
    await db.files.insert_one({
        "file_id": file_id,
        "name": "Lonely_File.txt",
        "mime_type": "text/plain",
        "available": True,
    })

    # No events inserted
    response = await client.get(f"/api/relationships/files/{file_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["total_events"] == 0
    assert response.json()["unique_users_count"] == 0
    assert response.json()["users"] == []
