#!/usr/bin/env python3
"""Install the explicit, project-bound Hermes CuratorMD integration."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def atomic_write(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def handler_source(project_root: Path, source_dir: Path, profile: str) -> str:
    return f'''"""Project-bound CuratorMD observer for Hermes gateway events."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

SOURCE_DIR = Path({str(source_dir)!r})
PROJECT_ROOT = {str(project_root)!r}
PROFILE = {profile!r}
sys.path.insert(0, str(SOURCE_DIR))

from curatormd import native_projection_record  # noqa: E402


def _source_id(event_type: str, context: dict) -> str:
    session = str(context.get("session_id") or "unknown-session")
    return f"hermes:{{PROFILE}}:{{session}}:{{event_type}}"


async def handle(event_type: str, context: dict):
    """Capture only bounded, redacted lifecycle evidence; never block Hermes."""
    if event_type not in {{"agent:start", "agent:step", "agent:end"}}:
        return
    try:
        payload = {{
            "scope": "profile-bound",
            "profile": PROFILE,
            "event": event_type,
            "session_id": context.get("session_id"),
            "platform": context.get("platform"),
            "iteration": context.get("iteration"),
            "tool_names": context.get("tool_names", []),
            "model": context.get("model"),
            "provider": context.get("provider"),
            "message": context.get("message"),
            "response": context.get("response"),
        }}
        cursor = hashlib.sha256(repr(sorted(payload.items())).encode("utf-8")).hexdigest()[:32]
        native_projection_record(
            PROJECT_ROOT,
            _source_id(event_type, context),
            event_type,
            payload,
            cursor=cursor,
            profile=PROFILE,
        )
    except Exception:
        # Gateway hook errors are isolated by Hermes; keep this handler equally best-effort.
        return
'''


def cron_source(project_root: Path, source_dir: Path, profile: str, schedule_slot: str) -> str:
    return f'''#!/usr/bin/env python3
"""Deterministic daily CuratorMD run for one explicitly bound project."""

import json
import sys

sys.path.insert(0, {str(source_dir)!r})
from curatormd import curate  # noqa: E402


if __name__ == "__main__":
    result = curate({str(project_root)!r}, schedule_slot={schedule_slot!r}, profile={profile!r})
    print(json.dumps(result, ensure_ascii=False))
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    parser.add_argument(
        "--source-dir",
        default=str(REPO_ROOT / "plugins" / "curatormd" / "scripts"),
        help="Directory containing curatormd.py; use the central CuratorMD source for new repos.",
    )
    parser.add_argument("--schedule-slot", required=True)
    args = parser.parse_args()
    project_root = Path(args.project_root).expanduser().resolve(strict=True)
    hermes_home = Path(args.hermes_home).expanduser().resolve()
    source_dir = Path(args.source_dir).expanduser().resolve(strict=True)
    profile_home = hermes_home / "profiles" / args.profile
    # Keep the observer under the named profile. A shared root-level hook would
    # be ambiguous and could be overwritten when another repository is enabled.
    hook_dirs = [profile_home / "hooks" / "curatormd-observer"]
    manifest = (
        "name: curatormd-observer\n"
        "description: Capture bounded redacted lifecycle evidence for one bound project\n"
        "events:\n"
        "  - agent:start\n"
        "  - agent:step\n"
        "  - agent:end\n"
    )
    for hook_dir in hook_dirs:
        atomic_write(hook_dir / "HOOK.yaml", manifest, 0o600)
        atomic_write(hook_dir / "handler.py", handler_source(project_root, source_dir, args.profile), 0o700)
    script_path = profile_home / "scripts" / "curatormd.py"
    atomic_write(script_path, cron_source(project_root, source_dir, args.profile, args.schedule_slot), 0o700)
    for hook_dir in hook_dirs:
        print(f"hook={hook_dir}")
    print(f"cron_script={script_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
