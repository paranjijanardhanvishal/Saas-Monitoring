"""Agent configuration.

Configuration comes from environment variables (optionally loaded from a
local ``.env`` file). The agent never stores a user password and never accepts
a user-supplied identity: the only credential is the device token issued once
at enrollment.
"""

from __future__ import annotations

import hashlib
import os
import platform
import socket
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

AGENT_VERSION = "2.0.0"
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

_AGENT_DIR = Path(__file__).resolve().parent
load_dotenv(_AGENT_DIR / ".env")
load_dotenv()


def default_state_dir() -> Path:
    configured = os.getenv("AGENT_STATE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        # Match install-agent.ps1: a per-user logon task keeps its credential
        # under the user's profile, which does not require administrator rights.
        base = os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(base) / "SaaSMonitorAgent"
    return Path.home() / ".saas-monitor-agent"


def _is_loopback(host: str) -> bool:
    return host.lower() in LOOPBACK_HOSTS


def validate_backend_url(url: str) -> str:
    """Reject plaintext transport to non-loopback hosts.

    Loopback HTTP is allowed only to support local development. TLS
    certificates are always verified by the HTTP client; there is no
    ``verify=False`` switch.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("BACKEND_URL must use http or https")
    if not parsed.hostname:
        raise ValueError("BACKEND_URL must include a host")
    if parsed.scheme == "http" and not _is_loopback(parsed.hostname):
        raise ValueError(
            "BACKEND_URL must use https for non-loopback hosts; "
            "use AGENT_DEV_HTTP only for local development"
        )
    return url.rstrip("/")


def _machine_guid() -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            if isinstance(value, str) and value:
                return value
    except OSError:
        return None
    return None


def stable_device_id() -> str:
    """Return a stable, non-secret device identifier for this host."""
    raw = _machine_guid() or f"{uuid.getnode()}-{socket.gethostname()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def os_version_string() -> str:
    return f"{platform.system()} {platform.release()} ({platform.version()})"


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, value)


def _watch_dirs() -> List[Path]:
    configured = os.getenv("AGENT_WATCH_DIRS", "").strip()
    if configured:
        candidates = [Path(item.strip()) for item in configured.split(";") if item.strip()]
    elif os.name == "nt":
        home = Path.home()
        candidates = [home / "Documents", home / "Desktop", home / "Downloads"]
    else:
        candidates = [Path.home() / "Documents"]
    unique: List[Path] = []
    for path in candidates:
        resolved = path.expanduser()
        if resolved.is_dir() and resolved not in unique:
            unique.append(resolved)
    return unique


@dataclass
class AgentConfig:
    backend_url: str = field(default_factory=lambda: os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api"))
    state_dir: Path = field(default_factory=default_state_dir)
    heartbeat_interval: int = field(default_factory=lambda: _int_env("HEARTBEAT_INTERVAL", 60, 10))
    poll_interval: int = field(default_factory=lambda: _int_env("POLL_INTERVAL", 5, 1))
    usage_report_interval: int = field(default_factory=lambda: _int_env("USAGE_REPORT_INTERVAL", 300, 60))
    event_batch_size: int = field(default_factory=lambda: min(200, _int_env("EVENT_BATCH_SIZE", 100, 1)))
    watch_dirs: List[Path] = field(default_factory=_watch_dirs)
    enable_file_monitoring: bool = field(
        default_factory=lambda: os.getenv("AGENT_ENABLE_FILE_MONITORING", "true").lower()
        not in {"0", "false", "no"}
    )
    enable_failed_login_monitoring: bool = field(
        default_factory=lambda: os.getenv("AGENT_ENABLE_FAILED_LOGIN_MONITORING", "true").lower()
        not in {"0", "false", "no"}
    )
    enrollment_token: Optional[str] = field(
        default_factory=lambda: os.getenv("AGENT_ENROLLMENT_TOKEN") or None
    )
    log_level: str = field(default_factory=lambda: os.getenv("AGENT_LOG_LEVEL", "INFO").upper())
    agent_version: str = AGENT_VERSION

    def validated(self) -> "AgentConfig":
        self.backend_url = validate_backend_url(self.backend_url)
        return self


config = AgentConfig().validated()
