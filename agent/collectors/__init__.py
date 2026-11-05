"""Endpoint collector package."""

from __future__ import annotations

import os
from typing import List

from .base import ALLOWED_ACTIONS, ALLOWED_EVENT_TYPES, Collector, make_event
from .windows import (
    FailedLoginCollector,
    FileCollector,
    ForegroundCollector,
    ProcessCollector,
    SessionCollector,
    UsageCollector,
)

__all__ = [
    "ALLOWED_ACTIONS",
    "ALLOWED_EVENT_TYPES",
    "Collector",
    "FailedLoginCollector",
    "FileCollector",
    "ForegroundCollector",
    "ProcessCollector",
    "SessionCollector",
    "UsageCollector",
    "build_collectors",
]


def build_collectors(config) -> List[Collector]:
    """Build the supported collectors for the current platform.

    Windows-specific capabilities are only enabled on Windows. Optional
    collectors disable themselves at ``start()`` with an explicit reason when
    permissions or dependencies are unavailable.
    """
    collectors: List[Collector] = []
    if os.name != "nt":
        return collectors

    collectors.append(ProcessCollector())
    collectors.append(ForegroundCollector())
    collectors.append(UsageCollector(report_interval=config.usage_report_interval))
    collectors.append(SessionCollector())
    if config.enable_failed_login_monitoring:
        collectors.append(FailedLoginCollector())
    if config.enable_file_monitoring and config.watch_dirs:
        collectors.append(FileCollector(config.watch_dirs, state_dir=config.state_dir))
    return collectors
