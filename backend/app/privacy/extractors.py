"""Unified document and cloud content text extraction.

Extracts text in-memory from supported office formats (.docx, .xlsx),
plain text (.txt, .csv, .json, .log, etc.), PDFs, and images via OCR.
Raw contents and extracted text are held in-memory only during analysis
and are never written to disk or the database.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Optional, Tuple
import xml.etree.ElementTree as ET
import zipfile

from app.core.config import settings
from app.privacy.ocr import OCRInputError, extract_document_text

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {
    ".txt", ".csv", ".tsv", ".log", ".json", ".xml", ".md",
    ".yaml", ".yml", ".html", ".htm", ".rtf", ".py", ".sql",
}

WORD_EXTENSIONS = {".docx", ".docm"}
EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}

SUPPORTED_EXTENSIONS = (
    TEXT_EXTENSIONS | WORD_EXTENSIONS | EXCEL_EXTENSIONS | PDF_EXTENSIONS | IMAGE_EXTENSIONS
)


class ContentExtractionError(ValueError):
    """Raised when document content cannot be extracted safely."""


def _extract_text_plain(payload: bytes) -> str:
    """Decode plain text bytes using common encodings."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252", "utf-16"):
        try:
            return payload.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return payload.decode("utf-8", errors="ignore")


def _extract_text_docx(payload: bytes) -> str:
    """Extract text from Word .docx file via standard library zipfile and XML parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            parts = [name for name in zf.namelist() if name.startswith("word/") and name.endswith(".xml")]
            # Ensure main document is first
            if "word/document.xml" in parts:
                parts.remove("word/document.xml")
                parts.insert(0, "word/document.xml")

            paragraphs: list[str] = []
            for part in parts:
                try:
                    xml_data = zf.read(part)
                    root = ET.fromstring(xml_data)
                    for elem in root.iter():
                        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag == "t" and elem.text:
                            paragraphs.append(elem.text)
                        elif tag == "p":
                            paragraphs.append("\n")
                except Exception:
                    continue

            return "".join(paragraphs).strip()
    except Exception as exc:
        raise ContentExtractionError(f"Corrupted or invalid DOCX document: {exc}") from exc


def _extract_text_xlsx(payload: bytes) -> str:
    """Extract text and cell values from Excel .xlsx file via standard library zipfile and XML."""
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            text_tokens: list[str] = []

            # 1. Read shared strings table (holds most text values in Excel)
            if "xl/sharedStrings.xml" in zf.namelist():
                try:
                    ss_xml = zf.read("xl/sharedStrings.xml")
                    root = ET.fromstring(ss_xml)
                    for elem in root.iter():
                        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag == "t" and elem.text:
                            text_tokens.append(elem.text.strip())
                except Exception:
                    pass

            # 2. Read cell values from individual worksheets
            sheet_names = [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
            for sheet_name in sheet_names:
                try:
                    sheet_xml = zf.read(sheet_name)
                    root = ET.fromstring(sheet_xml)
                    for elem in root.iter():
                        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag in ("v", "t") and elem.text:
                            val = elem.text.strip()
                            if val and not val.isdigit():  # include non-numeric strings
                                text_tokens.append(val)
                except Exception:
                    continue

            return " ".join(text_tokens).strip()
    except Exception as exc:
        raise ContentExtractionError(f"Corrupted or invalid XLSX spreadsheet: {exc}") from exc


def extract_file_content(
    payload: bytes,
    filename: str,
    mime_type: Optional[str] = None,
) -> Tuple[str, str, int]:
    """Extract readable text from file payload.

    Returns:
        (extracted_text, engine_name, item_count)
    """
    if not payload:
        return "", "empty", 0

    if len(payload) > settings.OCR_MAX_FILE_BYTES:
        raise ContentExtractionError("File size exceeds configured maximum limit.")

    ext = Path(filename).suffix.lower() if filename else ""

    # Infer extension from mime_type if extension is missing
    if not ext and mime_type:
        mime_map = {
            "text/plain": ".txt",
            "text/csv": ".csv",
            "application/pdf": ".pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "image/png": ".png",
            "image/jpeg": ".jpg",
        }
        ext = mime_map.get(mime_type.lower(), "")

    if ext in TEXT_EXTENSIONS or (mime_type and mime_type.startswith("text/")):
        text = _extract_text_plain(payload)
        return text[:settings.PII_MAX_TEXT_LENGTH], "text_extractor", 1

    if ext in WORD_EXTENSIONS:
        text = _extract_text_docx(payload)
        return text[:settings.PII_MAX_TEXT_LENGTH], "docx_extractor", 1

    if ext in EXCEL_EXTENSIONS:
        text = _extract_text_xlsx(payload)
        return text[:settings.PII_MAX_TEXT_LENGTH], "xlsx_extractor", 1

    if ext in (PDF_EXTENSIONS | IMAGE_EXTENSIONS):
        try:
            extraction = extract_document_text(payload, filename or f"file{ext}")
            return extraction.text[:settings.PII_MAX_TEXT_LENGTH], extraction.engine, extraction.page_count
        except (OCRInputError, Exception) as exc:
            logger.warning("OCR/PDF extraction failed for %s: %s", filename, exc)
            return "", "ocr_failed", 0

    # Fallback: attempt plain text if mime type suggests readable text
    if mime_type and ("json" in mime_type or "xml" in mime_type or "yaml" in mime_type or "text" in mime_type):
        text = _extract_text_plain(payload)
        return text[:settings.PII_MAX_TEXT_LENGTH], "text_extractor", 1

    return "", "unsupported", 0
