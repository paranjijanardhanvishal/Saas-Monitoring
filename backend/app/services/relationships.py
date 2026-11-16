"""Relationship mapping service between cloud files and enterprise users.

Aggregates real audit and proxy access/download/modify events from db.events.
Enforces strict RBAC and privacy isolation: non-admin users cannot see other
users' private file interactions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException


def _mask_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    parts = str(email).split("@")
    if len(parts) != 2:
        return "***"
    name, domain = parts
    masked_name = name[0] + "*" * (len(name) - 1) if name else "***"
    return f"{masked_name}@{domain}"


async def get_file_users_mapping(
    db,
    file_id: str,
    caller_user_id: str,
    caller_role: str,
    limit: int = 50,
) -> Dict[str, Any]:
    """Return users associated with a specific file and their activities.

    Non-admin callers only see their own activities. Admins see all users.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    file_doc = await db.files.find_one({"file_id": file_id})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")

    # File access check for non-admin
    if file_doc.get("available") is False:
        raise HTTPException(status_code=404, detail="File not found")

    # Build event query
    event_query: Dict[str, Any] = {"resource_id": file_id}
    if caller_role != "ADMIN":
        event_query["user_id"] = caller_user_id

    events = await db.events.find(event_query).sort("timestamp", -1).limit(200).to_list(length=200)

    # Group interactions by user_id
    user_stats: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        uid = ev.get("user_id") or "unknown"
        action = str(ev.get("action") or ev.get("event_type") or "ACCESS").upper()
        ts = ev.get("timestamp")

        if uid not in user_stats:
            user_stats[uid] = {
                "count": 0,
                "actions": {},
                "first_activity": ts,
                "last_activity": ts,
                "recent_events": [],
            }
        st = user_stats[uid]
        st["count"] += 1
        st["actions"][action] = st["actions"].get(action, 0) + 1
        if ts:
            if not st["first_activity"] or ts < st["first_activity"]:
                st["first_activity"] = ts
            if not st["last_activity"] or ts > st["last_activity"]:
                st["last_activity"] = ts
        if len(st["recent_events"]) < 5:
            st["recent_events"].append({
                "event_id": ev.get("event_id"),
                "action": action,
                "timestamp": ts,
                "event_type": ev.get("event_type"),
            })

    # Fetch user profile metadata
    users_list = []
    owner_email = (file_doc.get("owner_email") or "").lower()
    for uid, stats in user_stats.items():
        user_doc = await db.users.find_one({"user_id": uid}) if uid != "unknown" else None
        email = user_doc.get("email") if user_doc else None
        if caller_role == "VISITOR" and email:
            email = _mask_email(email)

        is_owner = False
        if email and owner_email and email.lower() == owner_email:
            is_owner = True
        elif user_doc and user_doc.get("user_id") == file_doc.get("owner_name"):
            is_owner = True

        users_list.append({
            "user_id": uid,
            "display_name": (user_doc or {}).get("display_name") or uid,
            "email": email,
            "business_role": (user_doc or {}).get("business_role", "GENERAL"),
            "role": (user_doc or {}).get("role", "USER"),
            "is_owner": is_owner,
            "total_interactions": stats["count"],
            "actions": stats["actions"],
            "first_activity": stats["first_activity"],
            "last_activity": stats["last_activity"],
            "recent_events": stats["recent_events"],
        })

    # Sort users by interaction count descending
    users_list.sort(key=lambda u: u["total_interactions"], reverse=True)

    return {
        "file_id": file_id,
        "name": file_doc.get("name"),
        "mime_type": file_doc.get("mime_type"),
        "size": file_doc.get("size"),
        "sensitivity_tier": file_doc.get("sensitivity_tier", "SAFE"),
        "sensitivity_score": file_doc.get("sensitivity_score", 0),
        "sharing_scope": file_doc.get("sharing_scope", "private"),
        "owner_email": file_doc.get("owner_email"),
        "owner_name": file_doc.get("owner_name"),
        "total_events": len(events),
        "unique_users_count": len(users_list),
        "users": users_list[:limit],
    }


async def get_user_files_mapping(
    db,
    target_user_id: str,
    caller_user_id: str,
    caller_role: str,
    limit: int = 50,
) -> Dict[str, Any]:
    """Return cloud files accessed by a specific user and their activity breakdown.

    Non-admin callers can ONLY view their own file interactions.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    if caller_role != "ADMIN" and caller_user_id != target_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You cannot inspect other users' file interactions")

    target_user = await db.users.find_one({"user_id": target_user_id})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    events = await db.events.find(
        {"user_id": target_user_id, "resource_id": {"$exists": True, "$ne": None}}
    ).sort("timestamp", -1).limit(200).to_list(length=200)

    # Group interactions by resource_id (file_id)
    file_stats: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        fid = ev.get("resource_id")
        if not fid:
            continue
        action = str(ev.get("action") or ev.get("event_type") or "ACCESS").upper()
        ts = ev.get("timestamp")
        rname = ev.get("resource_name") or fid

        if fid not in file_stats:
            file_stats[fid] = {
                "resource_name": rname,
                "count": 0,
                "actions": {},
                "first_activity": ts,
                "last_activity": ts,
                "recent_events": [],
            }
        st = file_stats[fid]
        st["count"] += 1
        st["actions"][action] = st["actions"].get(action, 0) + 1
        if ts:
            if not st["first_activity"] or ts < st["first_activity"]:
                st["first_activity"] = ts
            if not st["last_activity"] or ts > st["last_activity"]:
                st["last_activity"] = ts
        if len(st["recent_events"]) < 5:
            st["recent_events"].append({
                "event_id": ev.get("event_id"),
                "action": action,
                "timestamp": ts,
            })

    # Enrich with file metadata from db.files
    files_list = []
    for fid, stats in file_stats.items():
        file_doc = await db.files.find_one({"file_id": fid})
        files_list.append({
            "file_id": fid,
            "name": (file_doc or {}).get("name") or stats["resource_name"],
            "mime_type": (file_doc or {}).get("mime_type"),
            "size": (file_doc or {}).get("size"),
            "sensitivity_tier": (file_doc or {}).get("sensitivity_tier", "SAFE"),
            "sensitivity_score": (file_doc or {}).get("sensitivity_score", 0),
            "sharing_scope": (file_doc or {}).get("sharing_scope", "private"),
            "owner_email": (file_doc or {}).get("owner_email"),
            "total_interactions": stats["count"],
            "actions": stats["actions"],
            "first_activity": stats["first_activity"],
            "last_activity": stats["last_activity"],
            "recent_events": stats["recent_events"],
        })

    files_list.sort(key=lambda f: f["total_interactions"], reverse=True)

    email = target_user.get("email")
    if caller_role == "VISITOR" and email:
        email = _mask_email(email)

    return {
        "user_id": target_user_id,
        "display_name": target_user.get("display_name", target_user_id),
        "email": email,
        "business_role": target_user.get("business_role", "GENERAL"),
        "role": target_user.get("role", "USER"),
        "total_files_accessed": len(files_list),
        "total_interactions": len(events),
        "files": files_list[:limit],
    }


async def get_relationships_summary(
    db,
    caller_user_id: str,
    caller_role: str,
) -> Dict[str, Any]:
    """Aggregate summary statistics of file-user interactions."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    event_query: Dict[str, Any] = {"resource_id": {"$exists": True, "$ne": None}}
    if caller_role != "ADMIN":
        event_query["user_id"] = caller_user_id

    events = await db.events.find(event_query).limit(500).to_list(length=500)

    unique_files = set()
    unique_users = set()
    file_interaction_counts: Dict[str, int] = {}
    user_interaction_counts: Dict[str, int] = {}
    action_counts: Dict[str, int] = {}

    for ev in events:
        fid = ev.get("resource_id")
        uid = ev.get("user_id")
        act = str(ev.get("action") or "ACCESS").upper()

        if fid:
            unique_files.add(fid)
            file_interaction_counts[fid] = file_interaction_counts.get(fid, 0) + 1
        if uid:
            unique_users.add(uid)
            user_interaction_counts[uid] = user_interaction_counts.get(uid, 0) + 1
        action_counts[act] = action_counts.get(act, 0) + 1

    top_files = sorted(file_interaction_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_users = sorted(user_interaction_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_relationships": len(events),
        "unique_files_count": len(unique_files),
        "unique_users_count": len(unique_users),
        "action_breakdown": action_counts,
        "top_active_files": [{"file_id": f[0], "count": f[1]} for f in top_files],
        "top_active_users": [{"user_id": u[0], "count": u[1]} for u in top_users],
    }
