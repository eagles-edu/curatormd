#!/usr/bin/env python3
"""Emit a secret-free CuratorMD status snapshot for the VS Code extension."""

# This hyphenated filename is the status extension's established entry point.
# pylint: disable=invalid-name

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def run(command: list[str], *, cwd: Path, timeout: int = 8) -> tuple[int, str]:
    """Run a bounded health probe and return its status and stdout."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 127, ""
    return result.returncode, result.stdout


def _object_dict(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    raw_object = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw_object):
        return None
    return cast(dict[str, Any], value)


def curation_is_active(lock: Path) -> bool:
    """Check the advisory lock without changing the persistent lock file."""
    try:
        with lock.open("a+") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        return False
    return False


def curator_script(root: Path) -> Path | None:
    """Find the project-local or installed CuratorMD runtime."""
    candidates = [root / "plugins" / "curatormd" / "scripts" / "curatormd.py"]
    configured = os.environ.get("CURATORMD_SOURCE_DIR")
    if configured:
        candidates.append(Path(configured).expanduser() / "curatormd.py")
    candidates.extend(
        sorted(
            Path.home().glob(".codex/plugins/cache/personal/curatormd/*/scripts/curatormd.py"),
            reverse=True,
        )
    )
    candidates.append(Path.home() / ".hermes/plugins/curatormd/scripts/curatormd.py")
    return next((path for path in candidates if path.is_file()), None)


# This entry point collects the independent health probes into one status result.
# pylint: disable=too-many-locals,too-many-branches
def main() -> int:
    """Collect local health states and emit the extension status payload."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    script = curator_script(root)

    hermes_code, hermes_output = run(["hermes", "-p", args.profile, "status"], cwd=root, timeout=10)
    hermes = hermes_code == 0 and bool(
        re.search(r"Gateway Service[ \t]*\n[ \t]*Status:\s+.*running", hermes_output)
    )
    codex = hermes_code == 0 and bool(re.search(r"OpenAI Codex\s+✓\s+logged in", hermes_output))

    if script is None:
        curator_code, curator_output = 127, ""
    else:
        curator_code, curator_output = run(
            [
                sys.executable,
                str(script),
                "--project-root",
                str(root),
                "--profile",
                args.profile,
                "status",
            ],
            cwd=root,
            timeout=5,
        )
    curator_status: dict[str, Any] = {}
    if curator_code == 0:
        try:
            curator_status = _object_dict(json.loads(curator_output)) or {}
        except json.JSONDecodeError:
            pass

    stores_value = curator_status.get("stores", [])
    stores: list[dict[str, Any]] = []
    stores_valid = isinstance(stores_value, list)
    if isinstance(stores_value, list):
        for store_value in cast(list[Any], stores_value):
            store = _object_dict(store_value)
            if store is None:
                stores_valid = False
            else:
                stores.append(store)
    curator = (
        curator_code == 0
        and stores_valid
        and bool(stores)
        and all(store.get("exists") and not store.get("merge_conflict_markers") for store in stores)
    )
    capture_value = curator_status.get("capture_status", "degraded")
    capture = capture_value if isinstance(capture_value, str) else "degraded"
    pending = int(curator_status.get("pending_reviews", 0) or 0)
    lock = root / ".curatormd" / "curation.lock"
    working = curator and curation_is_active(lock)

    failures = [
        name
        for name, healthy in (("Hermes", hermes), ("Codex", codex), ("CuratorMD", curator))
        if not healthy
    ]
    if len(failures) > 1:
        color, label = "red", "MULTIPLE FAILURES"
    elif not hermes:
        color, label = "purple", "HERMES UNHEALTHY"
    elif not codex:
        color, label = "yellow", "CODEX UNHEALTHY"
    elif pending:
        color, label = "blue", f"{pending} NOTES TO REVIEW"
    elif working:
        color, label = "cyan", "CURATORMD WORKING"
    else:
        color, label = "green", "HEALTHY"

    result = {
        "state": color,
        "color": color,
        "label": label,
        "hermes": hermes,
        "codex": codex,
        "curator": curator,
        "capture": capture,
        "working": working,
        "pendingReview": pending,
        "failures": failures,
        "tooltip": (
            f"{label} | Hermes {'OK' if hermes else 'FAIL'} | "
            f"Codex {'OK' if codex else 'FAIL'} | "
            f"CuratorMD {'OK' if curator else 'FAIL'} | Review notes: {pending}"
        ),
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
