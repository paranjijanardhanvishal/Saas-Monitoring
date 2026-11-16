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
import uuid

from app.core.config import settings
from app.database.mongodb import get_database
from app.metadata.vector import build_metadata_vector_text, vector_service
from app.privacy.extractors import extract_file_content
from app.privacy.schemas import PrivacyAnalysisRequest
from app.privacy.service import analyze_text
from app.services.google_drive import drive_service

logger = logging.getLogger(__name__)


async def start_offline_analysis_job(
    user_id: str,
    file_ids: Optional[List[str]] = None,
    force_reanalyze: bool = False,
) -> Dict[str, Any]:
    """Start an idempotent persistent offline analysis background job in MongoDB."""
    db = get_database()
    if db is None:
        raise RuntimeError("Database connection unavailable")

    now = datetime.now(timezone.utc)
    # Idempotency check: reuse active job if one is already running
    active_job = await db.analysis_jobs.find_one({"status": "RUNNING"})
    if active_job:
        started_at = active_job.get("started_at")
        if started_at:
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            # If started within the last 15 minutes, report the active running job
            if (now - started_at).total_seconds() < 900:
                return {
                    "job_id": active_job.get("job_id"),
                    "status": "RUNNING",
                    "message": "Offline content analysis is already running in background.",
                    "already_running": True,
                    "processed": active_job.get("processed", 0),
                    "total": active_job.get("total", 0),
                }

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job_doc = {
        "job_id": job_id,
        "status": "RUNNING",
        "started_at": now,
        "completed_at": None,
        "user_id": user_id,
        "force_reanalyze": force_reanalyze,
        "file_ids": file_ids or [],
        "total": 0,
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "sensitive_count": 0,
        "high_risk_count": 0,
        "error": None,
    }
    await db.analysis_jobs.insert_one(job_doc)

    # Launch background processing task
    asyncio.create_task(
        run_offline_analysis(
            user_id=user_id,
            file_ids=file_ids,
            force_reanalyze=force_reanalyze,
            job_id=job_id,
        )
    )

    return {
        "job_id": job_id,
        "status": "RUNNING",
        "message": "Offline content analysis initiated in background.",
        "already_running": False,
    }


async def get_analysis_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve persistent background job status and progress from MongoDB."""
    db = get_database()
    if db is None:
        return None
    doc = await db.analysis_jobs.find_one({"job_id": job_id}, {"_id": 0})
    return doc


async def run_offline_analysis(
    user_id: str,
    file_ids: Optional[List[str]] = None,
    force_reanalyze: bool = False,
    job_id: Optional[str] = None,
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

    if job_id:
        await db.analysis_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"total": total}},
        )

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
                if job_id:
                    await db.analysis_jobs.update_one(
                        {"job_id": job_id},
                        {"$set": {"skipped": skipped, "sensitive_count": sensitive_count, "high_risk_count": high_risk_count}},
                    )
                continue

        # 2. Download cloud document content in-memory with bounded retries for transient SSL/socket failures
        raw_payload = None
        content_type = ""
        max_retries = 2
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                content_stream, content_type = await asyncio.to_thread(
                    drive_service.download_file, file_id
                )
                raw_payload = content_stream.read()
                content_stream.close()
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                exc_str = str(exc).lower()
                is_transient = any(
                    w in exc_str
                    for w in ("ssl", "connection", "reset", "timeout", "wrong_version", "record_mac", "internal error")
                )
                if is_transient and attempt < max_retries:
                    logger.warning(
                        "Transient download error for %s (attempt %d/%d), retrying in 1s: %s",
                        file_id,
                        attempt + 1,
                        max_retries,
                        exc,
                    )
                    await asyncio.sleep(1.0)
                    continue
                break

        if last_exc is not None or raw_payload is None:
            logger.warning("Could not download file %s (%s) for offline analysis: %s", file_id, filename, last_exc)
            await db.files.update_one(
                {"file_id": file_id},
                {
                    "$set": {
                        "analysis_status": "FAILED",
                        "analysis_error": str(last_exc)[:250] if last_exc else "Empty content stream",
                        "last_analyzed_at": datetime.now(timezone.utc),
                    }
                },
            )
            failed += 1
            if job_id:
                await db.analysis_jobs.update_one(
                    {"job_id": job_id},
                    {"$set": {"failed": failed}},
                )
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

            # 5. Persist derived findings metadata & sanitized vector tokens in db.files
            updated_doc = {**file_doc, "sensitivity_tier": tier, "sensitivity_score": score, "name": filename}
            vector_tokens = build_metadata_vector_text(updated_doc)

            update_data = {
                "analysis_status": "COMPLETED",
                "last_analyzed_at": now,
                "sensitivity_score": score,
                "sensitivity_tier": tier,
                "finding_id": finding_id,
                "entities_summary": entities_summary,
                "analysis_error": None,
                "vector_indexed": True,
                "vector_tokens": vector_tokens,
            }
            await db.files.update_one({"file_id": file_id}, {"$set": update_data})

            # 6. Index safe metadata in vector service
            vector_service.index_file(file_id, {**updated_doc, **update_data})

            processed += 1
            if score >= 60:
                high_risk_count += 1
            if score >= 20:
                sensitive_count += 1

            if job_id:
                await db.analysis_jobs.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "processed": processed,
                            "sensitive_count": sensitive_count,
                            "high_risk_count": high_risk_count,
                        }
                    },
                )

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
            if job_id:
                await db.analysis_jobs.update_one(
                    {"job_id": job_id},
                    {"$set": {"failed": failed}},
                )

    result = {
        "job_id": job_id,
        "total": total,
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "sensitive_count": sensitive_count,
        "high_risk_count": high_risk_count,
        "vector_status": vector_service.get_status(),
    }

    if job_id:
        await db.analysis_jobs.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "COMPLETED",
                    "completed_at": datetime.now(timezone.utc),
                    "processed": processed,
                    "skipped": skipped,
                    "failed": failed,
                    "sensitive_count": sensitive_count,
                    "high_risk_count": high_risk_count,
                }
            },
        )

    return result


async def get_offline_analysis_summary() -> Dict[str, Any]:
    """Retrieve aggregate statistics on offline cloud content analysis and vector indexing."""
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

    # Persisted vectors match completed analyzed files
    persisted_vectors = completed

    # Ensure in-memory local vector store is hydrated if currently empty
    if vector_service.local.count() == 0 and persisted_vectors > 0:
        try:
            await vector_service.hydrate_from_mongodb(db)
        except Exception:
            pass

    last_record = await db.files.find(
        {"analysis_status": "COMPLETED", "last_analyzed_at": {"$ne": None}}
    ).sort("last_analyzed_at", -1).limit(1).to_list(1)

    last_analysis_time = last_record[0]["last_analyzed_at"] if last_record else None

    # Check for active background job safely
    latest_job = None
    try:
        active_job = await db.analysis_jobs.find_one({"status": "RUNNING"}, {"_id": 0})
        latest_job = active_job or await db.analysis_jobs.find_one({}, {"_id": 0}, sort=[("started_at", -1)])
        if not isinstance(latest_job, dict):
            latest_job = None
    except Exception:
        latest_job = None

    vector_status = vector_service.get_status()
    # Report actual persisted count
    vector_status["total_indexed"] = max(vector_status.get("total_indexed", 0), persisted_vectors)

    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "failed": failed,
        "sensitive_count": sensitive_count,
        "high_risk_count": high_risk_count,
        "last_analysis_time": last_analysis_time,
        "vector_status": vector_status,
        "active_job": latest_job,
    }
