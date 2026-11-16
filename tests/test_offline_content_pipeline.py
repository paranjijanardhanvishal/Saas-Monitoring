"""Tests for Phase 1 Base Paper Implementation:
Offline cloud content analysis, unified extraction, vector indexing, and risk integration.
"""

from datetime import datetime, timedelta, timezone
import io
from unittest.mock import AsyncMock, MagicMock
import zipfile

import pytest

from app.metadata.vector import (
    LocalVectorDatabase,
    VectorMetadataService,
    build_metadata_vector_text,
)
from app.privacy.extractors import (
    extract_file_content,
)
from app.privacy.schemas import PrivacyFindingModel
from app.services.offline_analysis import run_offline_analysis, get_offline_analysis_summary


@pytest.fixture(autouse=True)
def mock_drive_download(monkeypatch):
    """Ensure tests never invoke real network Google Drive calls."""
    monkeypatch.setattr(
        "app.services.offline_analysis.drive_service.download_file",
        lambda fid: (io.BytesIO(b"Sample document text with test data"), "text/plain"),
    )


def _create_synthetic_docx(text: str) -> bytes:
    """Create a minimal valid DOCX archive in-memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
            "</w:body>"
            "</w:document>"
        )
        zf.writestr("word/document.xml", xml)
    return buf.getvalue()


def _create_synthetic_xlsx(shared_strings: list[str]) -> bytes:
    """Create a minimal valid XLSX archive in-memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        si_elements = "".join(f"<si><t>{s}</t></si>" for s in shared_strings)
        ss_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{si_elements}</sst>'
        )
        zf.writestr("xl/sharedStrings.xml", ss_xml)
        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>"
            '<row r="1"><c r="A1" t="s"><v>0</v></c></row>'
            "</sheetData>"
            "</worksheet>"
        )
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


class TestContentExtractors:
    def test_extract_plain_text(self):
        sample = b"Confidential memo: Internal audit results 2026."
        text, engine, count = extract_file_content(sample, "memo.txt")
        assert "Internal audit results" in text
        assert engine == "text_extractor"
        assert count == 1

    def test_extract_csv(self):
        sample = b"Name,Email,Department\nAlice,alice@corp.com,Finance\nBob,bob@corp.com,HR"
        text, engine, count = extract_file_content(sample, "employees.csv")
        assert "alice@corp.com" in text
        assert "Finance" in text

    def test_extract_docx(self):
        payload = _create_synthetic_docx("Confidential Strategy Document: Project Titan")
        text, engine, count = extract_file_content(payload, "strategy.docx")
        assert "Project Titan" in text
        assert engine == "docx_extractor"

    def test_extract_xlsx(self):
        payload = _create_synthetic_xlsx(["Customer Name", "CreditCard", "AccountID"])
        text, engine, count = extract_file_content(payload, "ledger.xlsx")
        assert "Customer Name" in text
        assert "CreditCard" in text
        assert engine == "xlsx_extractor"

    def test_extract_empty_payload(self):
        text, engine, count = extract_file_content(b"", "empty.txt")
        assert text == ""
        assert engine == "empty"


class TestVectorMetadataService:
    def test_vector_metadata_text_generation(self):
        meta = {
            "name": "Q3_financial_audit.xlsx",
            "sensitivity_tier": "HIGH_RISK",
            "sensitivity_score": 85,
            "entities_summary": [{"entity_type": "CREDIT_CARD"}, {"entity_type": "IBAN_CODE"}],
            "sharing_scope": "shared_domain",
            "source": "google_drive",
        }
        vec_text = build_metadata_vector_text(meta)
        assert "financial" in vec_text
        assert "audit" in vec_text
        assert "tier_high_risk" in vec_text
        assert "score_bucket_80" in vec_text
        assert "entity_credit_card" in vec_text
        assert "entity_iban_code" in vec_text
        assert "scope_shared_domain" in vec_text

    def test_local_vector_db_similarity_search(self):
        db = LocalVectorDatabase()
        db.insert("f1", "financial tax audit high_risk credit_card", {"name": "Tax.xlsx", "sensitivity_tier": "HIGH_RISK"})
        db.insert("f2", "financial revenue report sensitive", {"name": "Revenue.xlsx", "sensitivity_tier": "SENSITIVE"})
        db.insert("f3", "vacation holiday schedule safe calendar", {"name": "Holidays.pdf", "sensitivity_tier": "SAFE"})

        service = VectorMetadataService(db)
        results = service.search_similar("f1", top_k=2)

        assert len(results) >= 1
        top_match = results[0]
        assert top_match["file_id"] == "f2"
        assert top_match["similarity"] > 0
        assert top_match["name"] == "Revenue.xlsx"

    def test_vector_service_graceful_fallback(self):
        db = LocalVectorDatabase()
        service = VectorMetadataService(db)
        status = service.get_status()
        assert status["provider"] == "local_vector_db"
        assert status["total_indexed"] == 0


class TestOfflineAnalysisPipeline:
    @pytest.mark.asyncio
    async def test_run_offline_analysis_incremental_skipping(self, monkeypatch):
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(hours=2)

        file_unchanged = {
            "file_id": "file-101",
            "name": "Audit.txt",
            "mime_type": "text/plain",
            "analysis_status": "COMPLETED",
            "modified_time": earlier,
            "last_analyzed_at": now,
            "sensitivity_score": 75,
            "sensitivity_tier": "HIGH_RISK",
        }

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[file_unchanged])
        mock_db.files.find = MagicMock(return_value=mock_cursor)
        mock_db.files.update_one = AsyncMock()

        monkeypatch.setattr("app.services.offline_analysis.get_database", lambda: mock_db)

        result = await run_offline_analysis(user_id="admin-1")
        assert result["total"] == 1
        assert result["skipped"] == 1
        assert result["processed"] == 0
        assert result["high_risk_count"] == 1
        mock_db.files.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_offline_analysis_processes_new_file(self, monkeypatch):
        now = datetime.now(timezone.utc)
        file_new = {
            "file_id": "file-202",
            "name": "customers.csv",
            "mime_type": "text/csv",
            "analysis_status": "PENDING",
            "modified_time": now,
            "last_analyzed_at": None,
        }

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[file_new])
        mock_db.files.find = MagicMock(return_value=mock_cursor)
        mock_db.files.update_one = AsyncMock()

        content = io.BytesIO(b"Contact: user@company.com with phone +1234567890")
        monkeypatch.setattr("app.services.offline_analysis.get_database", lambda: mock_db)
        monkeypatch.setattr(
            "app.services.offline_analysis.drive_service.download_file",
            lambda fid: (content, "text/csv"),
        )

        mock_finding = PrivacyFindingModel(
            finding_id="f-new-1",
            user_id="admin-1",
            file_id="file-202",
            sensitivity_score=30,
            category="SENSITIVE",
            engine="regex",
            entities=[],
        )
        monkeypatch.setattr(
            "app.services.offline_analysis.analyze_text",
            AsyncMock(return_value=mock_finding),
        )

        result = await run_offline_analysis(user_id="admin-1")
        assert result["total"] == 1
        assert result["processed"] == 1
        assert result["skipped"] == 0
        assert result["sensitive_count"] == 1
        mock_db.files.update_one.assert_called_once()
        update_args = mock_db.files.update_one.call_args[0]
        assert update_args[0] == {"file_id": "file-202"}
        assert update_args[1]["$set"]["analysis_status"] == "COMPLETED"
        assert update_args[1]["$set"]["sensitivity_score"] == 30
        assert update_args[1]["$set"]["sensitivity_tier"] == "SENSITIVE"

    @pytest.mark.asyncio
    async def test_get_offline_analysis_summary(self, monkeypatch):
        mock_db = MagicMock()
        mock_db.files.count_documents = AsyncMock(side_effect=[10, 8, 1, 1, 3, 1])
        last_doc = [{"last_analyzed_at": datetime.now(timezone.utc)}]
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=last_doc)
        mock_db.files.find = MagicMock(return_value=mock_cursor)

        monkeypatch.setattr("app.services.offline_analysis.get_database", lambda: mock_db)

        summary = await get_offline_analysis_summary()
        assert summary["total"] == 10
        assert summary["completed"] == 8
        assert summary["pending"] == 1
        assert summary["failed"] == 1
        assert summary["sensitive_count"] == 3
        assert summary["high_risk_count"] == 1
        assert summary["last_analysis_time"] is not None
        assert "vector_status" in summary
