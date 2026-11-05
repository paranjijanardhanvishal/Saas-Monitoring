"""Small native Windows helpers.

Every function degrades gracefully to ``None``/empty output when the platform
or permissions do not support the requested information. No content, key
input, screenshots, clipboard data or browser history is read.
"""

from __future__ import annotations

import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_EVENT_NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}


def get_foreground_process() -> Optional[Dict[str, Any]]:
    """Return the foreground process id and image name (no window title)."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return None
        import psutil

        process = psutil.Process(pid.value)
        name = process.name()
        return {"pid": int(pid.value), "name": name}
    except Exception:
        return None


def get_session_state() -> Optional[str]:
    """Return ``locked``/``unlocked`` using the current input desktop.

    This is a best-effort poll. It cannot observe remote desktop sessions other
    than the active input desktop and may briefly race during session changes.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        DESKTOP_READOBJECTS = 0x0001
        UOI_NAME = 2
        handle = user32.OpenInputDesktop(0, False, DESKTOP_READOBJECTS)
        if not handle:
            return "locked"
        try:
            needed = wintypes.DWORD()
            user32.GetUserObjectInformationW(handle, UOI_NAME, None, 0, ctypes.byref(needed))
            buffer = ctypes.create_unicode_buffer(max(1, needed.value // ctypes.sizeof(ctypes.c_wchar)))
            if not user32.GetUserObjectInformationW(
                handle, UOI_NAME, buffer, ctypes.sizeof(buffer), ctypes.byref(needed)
            ):
                return None
            name = buffer.value.lower()
            return "locked" if name == "winlogon" else "unlocked"
        finally:
            user32.CloseDesktop(handle)
    except Exception:
        return None


def _as_xml_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def read_failed_logins(since: datetime, limit: int = 50) -> List[Dict[str, Any]]:
    """Read Windows Security event 4625 (failed logon) since ``since``.

    Requires an elevated account with access to the Security log. Raises
    ``PermissionError`` when the log is not accessible.
    """
    if os.name != "nt":
        return []
    query = (
        "*[System[(EventID=4625) and "
        f"TimeCreated[@SystemTime>='{_as_xml_utc(since)}']]]"
    )
    command = [
        "wevtutil",
        "qe",
        "Security",
        f"/q:{query}",
        "/f:xml",
        "/rd:true",
        f"/c:{max(1, min(limit, 200))}",
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PermissionError(f"Could not read the Security event log: {type(exc).__name__}") from exc
    if completed.returncode != 0:
        # Error text may include paths but never event contents; keep it short.
        message = (completed.stderr or completed.stdout or "").strip()[:200]
        raise PermissionError(message or "Security event log is not accessible")

    text = (completed.stdout or "").strip()
    if not text:
        return []
    try:
        root = ET.fromstring(f"<Events>{text}</Events>")
    except ET.ParseError:
        return []

    results: List[Dict[str, Any]] = []
    for event in root.findall("e:Event", _EVENT_NS):
        time_node = event.find("e:System/e:TimeCreated", _EVENT_NS)
        timestamp = time_node.attrib.get("SystemTime") if time_node is not None else None
        data: Dict[str, str] = {}
        for item in event.findall("e:EventData/e:Data", _EVENT_NS):
            name = item.attrib.get("Name")
            if name:
                data[name] = (item.text or "").strip()
        results.append(
            {
                "timestamp": timestamp,
                "account": (data.get("TargetUserName") or data.get("SubjectUserName") or "unknown")[:128],
                "logon_type": (data.get("LogonType") or "")[:16],
                "ip_address": (data.get("IpAddress") or "")[:64],
                "status": (data.get("Status") or "")[:32],
                "sub_status": (data.get("SubStatus") or "")[:32],
            }
        )
    return results
