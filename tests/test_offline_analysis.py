"""Offline metadata analysis tests.

The script analyses file *names* only; these tests assert that boundary.
"""

from unittest.mock import AsyncMock, Mock

import pytest

import scripts.offline_analysis as oa
from app.privacy.schemas import PrivacyFindingModel


@pytest.mark.asyncio
async def test_offline_analysis_uses_file_names_only(monkeypatch):
    cursor = Mock()
    cursor.to_list = AsyncMock(
        return_value=[
            {
                "file_id": "file-1",
                "name": "Confidential Payroll 2026.xlsx",
                "owner_email": "owner@example.com",
            },
            {"file_id": "file-2", "name": "orphan.txt", "owner_email": "missing@example.com"},
        ]
    )
    fake_db = Mock()
    fake_db.files.find = Mock(return_value=cursor)
    fake_db.users.find_one = AsyncMock(
        side_effect=lambda query: (
            {"user_id": "owner-1", "email": "owner@example.com"} if "owner" in str(query) else None
        )
    )
    fake_db.offline_baselines.update_one = AsyncMock()

    monkeypatch.setattr(oa, "connect_to_mongo", AsyncMock())
    monkeypatch.setattr(oa, "close_mongo_connection", AsyncMock())
    monkeypatch.setattr(oa, "get_database", lambda: fake_db)

    fake_vdb = Mock()
    monkeypatch.setattr(oa, "local_vdb", fake_vdb)

    analyze = AsyncMock(
        return_value=PrivacyFindingModel(
            finding_id="finding-1",
            user_id="owner-1",
            file_id="file-1",
            sensitivity_score=15,
            category="SAFE",
            engine="regex",
        )
    )
    monkeypatch.setattr(oa, "analyze_text", analyze)

    await oa.run_offline_analysis()

    # Only the file name is analysed, never content.
    request = analyze.call_args.args[0]
    assert request.text == "Confidential Payroll 2026.xlsx"
    assert analyze.call_args.args[1] == "owner-1"
    assert analyze.await_count == 1

    fake_vdb.insert.assert_called_once_with("file-1", "Confidential Payroll 2026.xlsx")

    update = fake_db.offline_baselines.update_one.call_args
    assert update.args[0] == {"file_id": "file-1"}
    assert update.args[1]["$set"]["analyzed_field"] == "file_name_only"
    assert update.kwargs["upsert"] is True


@pytest.mark.asyncio
async def test_offline_analysis_handles_no_files(monkeypatch):
    cursor = Mock()
    cursor.to_list = AsyncMock(return_value=[])
    fake_db = Mock()
    fake_db.files.find = Mock(return_value=cursor)

    monkeypatch.setattr(oa, "connect_to_mongo", AsyncMock())
    monkeypatch.setattr(oa, "close_mongo_connection", AsyncMock())
    monkeypatch.setattr(oa, "get_database", lambda: fake_db)
    analyze = AsyncMock()
    monkeypatch.setattr(oa, "analyze_text", analyze)

    await oa.run_offline_analysis()
    analyze.assert_not_called()


@pytest.mark.asyncio
async def test_offline_analysis_aborts_without_database(monkeypatch):
    monkeypatch.setattr(oa, "connect_to_mongo", AsyncMock())
    monkeypatch.setattr(oa, "close_mongo_connection", AsyncMock())
    monkeypatch.setattr(oa, "get_database", lambda: None)
    analyze = AsyncMock()
    monkeypatch.setattr(oa, "analyze_text", analyze)

    await oa.run_offline_analysis()
    analyze.assert_not_called()
