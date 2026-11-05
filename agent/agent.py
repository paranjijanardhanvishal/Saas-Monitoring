"""Deprecated launcher kept for compatibility.

Use ``python -m agent`` instead. This shim does not contain credentials and
does not authenticate with user passwords.
"""

import sys
import warnings
from pathlib import Path

warnings.warn(
    "agent/agent.py is deprecated; use 'python -m agent run'", DeprecationWarning, stacklevel=2
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
