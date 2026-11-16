import warnings
import pymupdf
import pytest
from app.privacy.ocr import extract_document_text, OCRInputError


def test_pdf_extraction_with_pymupdf_no_deprecation_warning():
    """Verify PDF extraction uses modern pymupdf API without issuing fitz deprecation warnings."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Confidential Strategic Planning Document 2026. Internal use only.")
    pdf_bytes = doc.tobytes()
    doc.close()

    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        result = extract_document_text(pdf_bytes, "plan.pdf")

        # Verify no PyMuPDF / fitz deprecation warning was emitted
        deprecations = [
            str(w.message) for w in recorded_warnings
            if "fitz" in str(w.message).lower() or "deprecated" in str(w.message).lower()
        ]
        assert not deprecations, f"Unexpected deprecation warnings: {deprecations}"

    assert result.page_count == 1
    assert "Confidential Strategic Planning" in result.text


def test_pdf_extraction_handles_empty_or_corrupt_files():
    """Verify corrupted PDF handling raises clean OCRInputError."""
    with pytest.raises(OCRInputError, match="corrupted or cannot be read"):
        extract_document_text(b"%PDF-invalid-bytes", "corrupt.pdf")

    with pytest.raises(OCRInputError, match="file is empty"):
        extract_document_text(b"", "empty.pdf")
