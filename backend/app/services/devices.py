"""Device enrollment and revocation helpers."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.core.security import generate_opaque_token, hash_token

logger = logging.getLogger(__name__)

ENROLLMENT_TTL_SECONDS = 3600


async def issue_enrollment_token(db, user_id: str, created_by: str) -> tuple[str, datetime]:
    raw, digest, prefix = generate_opaque_token("enr_")
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ENROLLMENT_TTL_SECONDS)
    await db.enrollment_tokens.insert_one(
        {
            "token_hash": digest,
            "token_prefix": prefix,
            "user_id": user_id,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "used_at": None,
            "device_id": None,
        }
    )
    return raw, expires_at


async def consume_enrollment_token(db, raw_token: str) -> Optional[dict[str, Any]]:
    """Atomically consume a single-use enrollment token."""
    digest = hash_token(raw_token)
    now = datetime.now(timezone.utc)
    record = await db.enrollment_tokens.find_one_and_update(
        {
            "token_hash": digest,
            "used_at": None,
            "expires_at": {"$gt": now},
        },
        {"$set": {"used_at": now}},
        return_document=True,
    )
    return record


async def activate_enrollment_token(db, raw_token: str, device_id: str) -> None:
    await db.enrollment_tokens.update_one(
        {"token_hash": hash_token(raw_token)},
        {"$set": {"device_id": device_id}},
    )


async def revoke_device(db, device_id: str, reason: str) -> bool:
    result = await db.devices.update_one(
        {"device_id": device_id, "status": "ACTIVE"},
        {
            "$set": {
                "status": "REVOKED",
                "revoked_at": datetime.now(timezone.utc),
                "revoked_reason": reason,
                "monitoring_enabled": False,
            }
        },
    )
    return result.modified_count > 0


async def revoke_all_user_devices(db, user_id: str, reason: str) -> int:
    result = await db.devices.update_many(
        {"user_id": user_id, "status": "ACTIVE"},
        {
            "$set": {
                "status": "REVOKED",
                "revoked_at": datetime.now(timezone.utc),
                "revoked_reason": reason,
                "monitoring_enabled": False,
            }
        },
    )
    return int(result.modified_count)
