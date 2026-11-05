"""Local OCR for user-initiated image and scanned-PDF privacy scans.

Uploads and extracted text are used in memory for one request. This module
never writes either to the application database or to log messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from app.core.config import settings


SUPPORTED_FILE_TYPES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
MAX_OCR_IMAGE_PIXELS = 25_000_000
MAX_OCR_PAGE_EDGE = 3_000


class OCRUnavailableError(RuntimeError):
    """Raised when the Python OCR packages or Tesseract executable are absent."""


class OCRInputError(ValueError):
    """Raised when a document cannot be safely or completely analysed."""


@dataclass(frozen=True)
class OCRExtraction:
    text: str
    page_count: int
    engine: str = "tesseract"


def get_ocr_status() -> dict[str, Any]:
    """Return measured OCR readiness without exposing system paths."""
    limits = {
        "max_file_bytes": settings.OCR_MAX_FILE_BYTES,
        "max_pdf_pages": settings.OCR_MAX_PAGES,
        "max_text_length": settings.PII_MAX_TEXT_LENGTH,
    }
    try:
        import fitz  # noqa: F401
        import pytesseract
        from PIL import Image  # noqa: F401

        if settings.TESSERACT_CMD.strip():
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD.strip()
        version = str(pytesseract.get_tesseract_version()).split()[0]
    except Exception:
        return {
            **limits,
            "available": False,
            "engine": "tesseract",
            "reason": "Install the optional OCR dependencies and Tesseract executable.",
        }
    return {**limits, "available": True, "engine": "tesseract", "version": version}


def _ocr_image(image, pytesseract) -> str:
    try:
        return pytesseract.image_to_string(image, lang="eng", timeout=30)
    except Exception as exc:
        raise OCRInputError("OCR could not read this image. Check that it is clear and not corrupted.") from exc


def extract_document_text(payload: bytes, filename: str | None) -> OCRExtraction:
    """Extract text from a supported image or PDF, with strict size/page caps."""
    if not payload:
        raise OCRInputError("The uploaded file is empty.")
    if len(payload) > settings.OCR_MAX_FILE_BYTES:
        raise OCRInputError("The uploaded file exceeds the configured size limit.")

    extension = Path(filename or "").suffix.lower()
    if extension not in SUPPORTED_FILE_TYPES:
        raise OCRInputError("Choose a PDF, PNG, JPEG, TIFF, BMP or WebP file.")

    status = get_ocr_status()
    if not status.get("available"):
        raise OCRUnavailableError(status["reason"])

    import fitz
    import pytesseract
    from PIL import Image
    if settings.TESSERACT_CMD.strip():
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD.strip()

    extracted: list[str] = []
    page_count = 1
    try:
        if extension == ".pdf":
            with fitz.open(stream=payload, filetype="pdf") as document:
                if document.needs_pass:
                    raise OCRInputError("Password-protected PDFs are not supported.")
                page_count = len(document)
                if page_count < 1:
                    raise OCRInputError("The PDF contains no pages.")
                if page_count > settings.OCR_MAX_PAGES:
                    raise OCRInputError(
                        f"The PDF exceeds the configured {settings.OCR_MAX_PAGES}-page limit."
                    )
                for page in document:
                    rect = page.rect
                    longest_edge = max(float(rect.width), float(rect.height))
                    if longest_edge <= 0:
                        raise OCRInputError("The PDF contains a page with invalid dimensions.")
                    scale = min(170 / 72, MAX_OCR_PAGE_EDGE / longest_edge)
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    with Image.open(BytesIO(pixmap.tobytes("png"))) as image:
                        extracted.append(_ocr_image(image, pytesseract))
                    if sum(map(len, extracted)) > settings.PII_MAX_TEXT_LENGTH:
                        raise OCRInputError("Extracted text exceeds the configured analysis limit.")
        else:
            with Image.open(BytesIO(payload)) as image:
                if image.width * image.height > MAX_OCR_IMAGE_PIXELS:
                    raise OCRInputError("The image exceeds the configured pixel limit.")
                image.load()
                extracted.append(_ocr_image(image, pytesseract))
    except OCRInputError:
        raise
    except Exception as exc:
        raise OCRInputError("The uploaded file is invalid or could not be decoded.") from exc

    text = "\n".join(part.strip() for part in extracted if part and part.strip())
    if len(text) > settings.PII_MAX_TEXT_LENGTH:
        raise OCRInputError("Extracted text exceeds the configured analysis limit.")
    return OCRExtraction(text=text, page_count=page_count)
