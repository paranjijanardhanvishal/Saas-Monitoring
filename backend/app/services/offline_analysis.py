"""Offline cloud content analysis pipeline.

Implements Phase 1 of the Base Research Paper:
"SaaS API Monitoring for Data Leakage and Access Anomalies: A Privacy-Aware
and Adaptive Behavioral Analytics Framework for Enterprise Cloud Systems."

Performs authorized offline content inspection on cloud documents (.txt, .docx, .xlsx,
.pdf, and images via OCR), detects PII and assigns sensitivity scores using Presidio,
tracks analysis lifecycle (PENDING -> COMPLETED / FAILED), enforces incremental
skipping of unchanged files, and indexes derived metadata in the vector database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.database.mongodb import get_database
from app.metadata.vector import vector_service
from app.privacy.extractors import extract_file_content
from app.privacy.schemas import PrivacyAnalysisRequest
from app.privacy.service import analyze_text
from app.services.google_drive import drive_service

logger = logging.getLogger(__name__)


async def run_offline_analysis(
    user_id: str,
    file_ids: Optional[List[str]] = None,
    force_reanalyze: bool = False,
) -> Dict[str, Any]:
    """Execute offline content analysis across synchronized cloud files.

    Raw document bytes and extracted text are used in memory only and
    immediately cleared. Only derived findings, sensitivity metrics, and
    vector representations are persisted.
    """
    db = get_database()
    if db is None:
        raise RuntimeError("Database connection unavailable")

    query: Dict[str, Any] = {"available": {"$ne": False}}
    if file_ids:
        query["file_id"] = {"$in": file_ids}

    cursor = db.files.find(query)
    files = await cursor.to_list(length=500)

    total = len(files)
    processed = 0
    skipped = 0
    failed = 0
    sensitive_count = 0
    high_risk_count = 0

    for file_doc in files:
        file_id = file_doc.get("file_id")
        filename = file_doc.get("name", "untitled")
        mime_type = file_doc.get("mime_type", "")
        modified_time = file_doc.get("modified_time")
        last_analyzed_at = file_doc.get("last_analyzed_at")
        status = file_doc.get("analysis_status")

        # 1. Incremental check: Skip unchanged files that are already COMPLETED
        if not force_reanalyze and status == "COMPLETED" and last_analyzed_at and modified_time:
            # Ensure both have timezone for comparison
            if last_analyzed_at.tzinfo is None:
                last_analyzed_at = last_analyzed_at.replace(tzinfo=timezone.utc)
            if modified_time.tzinfo is None:
                modified_time = modified_time.replace(tzinfo=timezone.utc)

            if last_analyzed_at >= modified_time:
                # File has not changed since last analysis; ensure vector indexed
                vector_service.index_file(file_id, file_doc)
                skipped += 1
                if (file_doc.get("sensitivity_score") or 0) >= 60:
                    high_risk_count += 1
                if (file_doc.get("sensitivity_score") or 0) >= 20:
                    sensitive_count += 1
                continue

        # 2. Download cloud document content in-memory
        try:
            content_stream, content_type = await asyncio.to_thread(
                drive_service.download_file, file_id
            )
            raw_payload = content_stream.read()
            content_stream.close()
        except Exception as exc:
            logger.warning("Could not download file %s (%s) for offline analysis: %s", file_id, filename, exc)
            await db.files.update_one(
                {"file_id": file_id},
                {
                    "$set": {
                        "analysis_status": "FAILED",
                        "analysis_error": str(exc)[:250],
                        "last_analyzed_at": datetime.now(timezone.utc),
                    }
                },
            )
            failed += 1
            continue

        # 3. Extract text from supported formats (.txt, .docx, .xlsx, .pdf, images)
        try:
            extracted_text, engine, page_count = extract_file_content(
                raw_payload, filename, mime_type or content_type
            )
        except Exception as exc:
            logger.warning("Extraction error for %s (%s): %s", file_id, filename, exc)
            extracted_text, engine, page_count = "", "extraction_error", 0
        finally:
            del raw_payload  # Zero/delete raw payload immediately

        # 4. Run Presidio PII detection and sensitivity scoring
        try:
            now = datetime.now(timezone.utc)
            if extracted_text and extracted_text.strip():
                truncated_text = extracted_text[: settings.PII_MAX_TEXT_LENGTH]
                del extracted_text  # Free full text from memory

                finding = await analyze_text(
                    PrivacyAnalysisRequest(text=truncated_text, file_id=file_id),
                    user_id=user_id,
                    source="offline_cloud_analysis",
                    ocr_engine=engine,
                    file_type=Path(filename).suffix.lower(),
                    page_count=page_count,
                )
                score = finding.sensitivity_score
                tier = finding.category
                finding_id = finding.finding_id
                entities_summary = [e.model_dump() for e in finding.entities]
            else:
                score = 0
                tier = "SAFE"
                finding_id = None
                entities_summary = []

            # 5. Persist derived findings metadata in db.files
            update_data = {
                "analysis_status": "COMPLETED",
                "last_analyzed_at": now,
                "sensitivity_score": score,
                "sensitivity_tier": tier,
                "finding_id": finding_id,
                "entities_summary": entities_summary,
                "analysis_error": None,
                "vector_indexed": True,
            }
            await db.files.update_one({"file_id": file_id}, {"$set": update_data})

            # 6. Index safe metadata in vector service
            updated_doc = {**file_doc, **update_data}
            vector_service.index_file(file_id, updated_doc)

            processed += 1
            if score >= 60:
                high_risk_count += 1
            if score >= 20:
                sensitive_count += 1

            logger.info("Offline analysis completed for %s (%s): score=%s tier=%s", file_id, filename, score, tier)

        except Exception as exc:
            logger.exception("Offline analysis processing failed for %s", file_id)
            await db.files.update_one(
                {"file_id": file_id},
                {
                    "$set": {
                        "analysis_status": "FAILED",
                        "analysis_error": str(exc)[:250],
                        "last_analyzed_at": datetime.now(timezone.utc),
                    }
                },
            )
            failed += 1

    return {
        "total": total,
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "sensitive_count": sensitive_count,
        "high_risk_count": high_risk_count,
        "vector_status": vector_service.get_status(),
    }


async def get_offline_analysis_summary() -> Dict[str, Any]:
    """Retrieve aggregate statistics on offline cloud content analysis."""
    db = get_database()
    if db is None:
        raise RuntimeError("Database connection unavailable")

    base_filter = {"available": {"$ne": False}}
    total = await db.files.count_documents(base_filter)
    completed = await db.files.count_documents({**base_filter, "analysis_status": "COMPLETED"})
    pending = await db.files.count_documents({**base_filter, "analysis_status": {"$in": ["PENDING", None]}})
    failed = await db.files.count_documents({**base_filter, "analysis_status": "FAILED"})
    sensitive_count = await db.files.count_documents(
        {**base_filter, "sensitivity_tier": {"$in": ["SENSITIVE", "HIGH_RISK"]}}
    )
    high_risk_count = await db.files.count_documents({**base_filter, "sensitivity_tier": "HIGH_RISK"})

    last_record = await db.files.find(
        {"analysis_status": "COMPLETED", "last_analyzed_at": {"$ne": None}}
    ).sort("last_analyzed_at", -1).limit(1).to_list(1)

    last_analysis_time = last_record[0]["last_analyzed_at"] if last_record else None

    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "failed": failed,
        "sensitive_count": sensitive_count,
        "high_risk_count": high_risk_count,
        "last_analysis_time": last_analysis_time,
        "vector_status": vector_service.get_status(),
    }
