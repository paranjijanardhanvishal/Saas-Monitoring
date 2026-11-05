"""Append-only administrative audit trail.

Never store passwords, tokens, raw event payloads or file contents here.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def record_audit(
    db,
    actor_id: Optional[str],
    actor_role: Optional[str],
    action: str,
    target_type: str,
    target_id: Optional[str],
    result: str,
    reason: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    client_ip: Optional[str] = None,
) -> None:
    if db is None:
        logger.warning("Audit event dropped because the database is unavailable: %s", action)
        return
    document = {
        "timestamp": datetime.now(timezone.utc),
        "actor_id": actor_id,
        "actor_role": actor_role,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "result": result,
        "reason": reason,
        "metadata": metadata or {},
        "client_ip": client_ip,
    }
    try:
        await db.audit_logs.insert_one(document)
    except Exception:
        # Audit failures must be visible but must not crash the request path.
        logger.exception("Failed to write audit log entry: %s", action)
