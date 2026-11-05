"""Local device credential storage.

The device token is a revocable, device-scoped credential. It is written to a
single JSON file with user-only permissions and never logged. On Windows the
file ACL is inherited from the state directory; operators should restrict that
directory and use full-disk encryption. DPAPI sealing is not implemented.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

STATE_FILE = "device.json"


class StateError(RuntimeError):
    pass


class StateStore:
    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / STATE_FILE

    def ensure_dir(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.state_dir, 0o700)
        except OSError:
            pass

    def load(self) -> Optional[dict[str, Any]]:
        if not self.path.is_file():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise StateError(f"Could not read agent state: {type(exc).__name__}") from exc
        if not isinstance(data, dict) or not data.get("device_token"):
            raise StateError("Agent state is incomplete; re-enroll the device")
        return data

    def save(self, data: dict[str, Any]) -> None:
        if not data.get("device_token"):
            raise StateError("Refusing to persist state without a device token")
        self.ensure_dir()
        payload = json.dumps(data, indent=2, sort_keys=True)
        # Write to a temporary file in the same directory, then replace atomically.
        fd, temp_name = tempfile.mkstemp(dir=str(self.state_dir), prefix=".device-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def clear(self) -> bool:
        removed = False
        if self.path.exists():
            self.path.unlink()
            removed = True
        return removed

    def public_state(self) -> dict[str, Any]:
        """State without the device token, safe for status output/logs."""
        state = self.load() or {}
        state.pop("device_token", None)
        return state
