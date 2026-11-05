from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep imports deterministic and avoid reading a developer's real state dir.
os.environ.setdefault("BACKEND_URL", "http://localhost:8000/api")
os.environ.setdefault("AGENT_STATE_DIR", str(ROOT / ".pytest-agent-state"))
