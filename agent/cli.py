"""Command line interface for the endpoint agent.

Explicit commands: ``enroll``, ``run``, ``status`` and ``uninstall``. The
agent never prints or logs the device token, enrollment token or any password.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from .client import AgentAuthError, AgentError
from .config import AGENT_VERSION, AgentConfig
from .service import AgentService
from .storage import StateError, StateStore


def _safe_backend(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "unknown"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}{parsed.path.rstrip('/')}"


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def build_config(args: argparse.Namespace) -> AgentConfig:
    config = AgentConfig()
    if getattr(args, "backend_url", None):
        config.backend_url = args.backend_url
    if getattr(args, "state_dir", None):
        config.state_dir = Path(args.state_dir).expanduser()
    if getattr(args, "log_level", None):
        config.log_level = args.log_level.upper()
    return config.validated()


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def cmd_enroll(args: argparse.Namespace) -> int:
    config = build_config(args)
    configure_logging(config.log_level)
    store = StateStore(config.state_dir)
    if store.path.exists() and not args.force:
        _print_json(
            {
                "status": "already_enrolled",
                "message": "Use 'status' to inspect the device or --force to replace the credential.",
                "state_dir": str(config.state_dir),
            }
        )
        return 0
    if args.force:
        store.clear()
    config.enrollment_token = args.token or config.enrollment_token
    service = AgentService(config, store=store, collectors=[])
    try:
        state = service.prepare()
    except (AgentError, StateError) as exc:
        logging.getLogger(__name__).error("Enrollment failed: %s", exc)
        return 2
    finally:
        service.client.close()
    _print_json(
        {
            "status": "enrolled",
            "device_id": state.get("device_id"),
            "user_id": state.get("user_id"),
            "state_dir": str(config.state_dir),
            "backend": _safe_backend(config.backend_url),
        }
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = build_config(args)
    configure_logging(config.log_level)
    stop_event = threading.Event()

    def _stop(_signum, _frame):
        stop_event.set()

    for signal_name in ("SIGINT", "SIGTERM"):
        signal_value = getattr(signal, signal_name, None)
        if signal_value is not None:
            try:
                signal.signal(signal_value, _stop)
            except (OSError, ValueError):
                pass

    service = AgentService(config, stop_event=stop_event)
    logging.getLogger(__name__).info(
        "Starting SaaS Security Monitor agent %s for %s", AGENT_VERSION, _safe_backend(config.backend_url)
    )
    try:
        if args.once:
            result = service.run_once()
        else:
            result = service.run(max_seconds=args.duration)
    except (AgentAuthError, AgentError, StateError) as exc:
        logging.getLogger(__name__).error("Agent stopped: %s", exc)
        return 2
    _print_json(
        {
            "status": "stopped",
            "monitoring_active": result.monitoring_active,
            "enrolled": result.enrolled,
            "stats": result.stats,
        }
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = build_config(args)
    configure_logging("ERROR")
    service = AgentService(config, collectors=[])
    try:
        _print_json(service.public_status())
    except StateError as exc:
        _print_json({"enrolled": False, "state_error": str(exc), "state_dir": str(config.state_dir)})
        return 2
    finally:
        service.client.close()
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    config = build_config(args)
    configure_logging("ERROR")
    store = StateStore(config.state_dir)
    removed = store.clear()
    _print_json(
        {
            "status": "state_removed" if removed else "no_state",
            "state_dir": str(config.state_dir),
            "message": "Stop and delete the scheduled task with uninstall-agent.ps1 if it was installed.",
        }
    )
    return 0


def _add_global_options(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    default = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument("--backend-url", default=default, help="Backend API base URL (HTTPS outside loopback)")
    parser.add_argument("--state-dir", default=default, help="Directory for the device credential and local state")
    parser.add_argument("--log-level", default=default, help="DEBUG, INFO, WARNING or ERROR")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agent",
        description="SaaS Security Monitor endpoint agent (metadata-only collection).",
    )
    _add_global_options(parser)
    parser.add_argument("--version", action="version", version=f"%(prog)s {AGENT_VERSION}")

    sub = parser.add_subparsers(dest="command", required=True)

    enroll = sub.add_parser("enroll", help="Enroll this device with a one-time token")
    _add_global_options(enroll, suppress_defaults=True)
    enroll.add_argument("--token", help="One-time enrollment token (prefer AGENT_ENROLLMENT_TOKEN)")
    enroll.add_argument("--force", action="store_true", help="Replace an existing device credential")
    enroll.set_defaults(func=cmd_enroll)

    run = sub.add_parser("run", help="Run the collection and heartbeat loop")
    _add_global_options(run, suppress_defaults=True)
    run.add_argument("--once", action="store_true", help="Heartbeat, collect and send once, then exit")
    run.add_argument("--duration", type=float, default=None, help="Stop after N seconds (diagnostics)")
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="Show sanitized local enrollment status")
    _add_global_options(status, suppress_defaults=True)
    status.set_defaults(func=cmd_status)

    uninstall = sub.add_parser("uninstall", help="Remove the local device credential")
    _add_global_options(uninstall, suppress_defaults=True)
    uninstall.set_defaults(func=cmd_uninstall)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
