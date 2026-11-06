"""Local OCR for user-initiated image and scanned-PDF privacy scans.

Uploads and extracted text are used in memory for one request. This module
never writes either to the application database or to log messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
import threading
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_FILE_TYPES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
MAX_OCR_IMAGE_PIXELS = 25_000_000
MAX_OCR_PAGE_EDGE = 3_000

_linux_provision_lock = threading.Lock()
_linux_provision_attempted = False


def _ensure_linux_tesseract() -> str | None:
    """Download and unpack portable Linux Tesseract AppImage if missing system-wide."""
    global _linux_provision_attempted
    if platform.system() != "Linux":
        return None

    backend_dir = Path(__file__).resolve().parents[2]
    apprun = backend_dir / ".tesseract" / "squashfs-root" / "AppRun"
    if apprun.is_file() and os.access(apprun, os.X_OK):
        return str(apprun)

    tmp_apprun = Path("/tmp/.tesseract/squashfs-root/AppRun")
    if tmp_apprun.is_file() and os.access(tmp_apprun, os.X_OK):
        return str(tmp_apprun)

    with _linux_provision_lock:
        if apprun.is_file() and os.access(apprun, os.X_OK):
            return str(apprun)
        if tmp_apprun.is_file() and os.access(tmp_apprun, os.X_OK):
            return str(tmp_apprun)
        if _linux_provision_attempted:
            return None
        _linux_provision_attempted = True

        target_dir = backend_dir / ".tesseract"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            chosen_apprun = target_dir / "squashfs-root" / "AppRun"
        except Exception:
            target_dir = Path("/tmp/.tesseract")
            target_dir.mkdir(parents=True, exist_ok=True)
            chosen_apprun = target_dir / "squashfs-root" / "AppRun"

        appimage_path = target_dir / "tesseract.AppImage"
        try:
            logger.info("Setting up standalone Tesseract for Linux runtime at %s...", target_dir)
            import urllib.request
            url = "https://github.com/AlexanderP/tesseract-appimage/releases/download/v5.4.1/tesseract-5.4.1-x86_64.AppImage"
            urllib.request.urlretrieve(url, appimage_path)
            appimage_path.chmod(0o755)
            logger.info("Extracting Tesseract AppImage...")
            subprocess.run(
                [str(appimage_path), "--appimage-extract"],
                cwd=str(target_dir),
                check=True,
                capture_output=True,
                timeout=120,
            )
            if appimage_path.is_file():
                appimage_path.unlink()
            if chosen_apprun.is_file():
                chosen_apprun.chmod(0o755)
                tess_bin = target_dir / "squashfs-root" / "usr" / "bin" / "tesseract"
                if tess_bin.is_file():
                    tess_bin.chmod(0o755)
                logger.info("Standalone Linux Tesseract ready at %s", chosen_apprun)
                return str(chosen_apprun)
        except Exception as exc:
            logger.warning("Could not auto-provision Linux Tesseract AppImage: %s", exc)
            return None


def _resolve_tesseract_cmd() -> str | None:
    if settings.TESSERACT_CMD.strip() and Path(settings.TESSERACT_CMD.strip()).exists():
        return settings.TESSERACT_CMD.strip()
    which = shutil.which("tesseract")
    if which:
        return which

    backend_dir = Path(__file__).resolve().parents[2]
    candidates = [
        Path("/usr/bin/tesseract"),
        Path("/usr/local/bin/tesseract"),
        backend_dir / ".tesseract" / "squashfs-root" / "AppRun",
        backend_dir / ".tesseract" / "squashfs-root" / "usr" / "bin" / "tesseract",
        Path("/tmp/.tesseract/squashfs-root/AppRun"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")),
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)

    if platform.system() == "Linux":
        installed = _ensure_linux_tesseract()
        if installed:
            return installed

    return settings.TESSERACT_CMD.strip() or None


def _configure_pytesseract(pytesseract) -> None:
    cmd = _resolve_tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        cmd_path = Path(cmd)
        candidates_tessdata = [
            cmd_path.parent / "tessdata",
            cmd_path.parent / "usr" / "share" / "tesseract-ocr" / "5" / "tessdata",
            cmd_path.parent.parent / "share" / "tesseract-ocr" / "5" / "tessdata",
            Path("/usr/share/tesseract-ocr/5/tessdata"),
            Path("/usr/share/tesseract-ocr/4.00/tessdata"),
            Path("/usr/share/tessdata"),
        ]
        for td in candidates_tessdata:
            if td.is_dir() and "TESSDATA_PREFIX" not in os.environ:
                os.environ["TESSDATA_PREFIX"] = str(td)
                break


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

        _configure_pytesseract(pytesseract)
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
    _configure_pytesseract(pytesseract)

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
