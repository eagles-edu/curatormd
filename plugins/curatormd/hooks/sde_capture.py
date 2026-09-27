#!/usr/bin/env python3
"""Capture bounded SDE cues from Codex turns into the current repo's inbox."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, cast


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from sde_vocabulary import match_sde_cues  # noqa: E402  # pylint: disable=wrong-import-position
import curatormd  # noqa: E402  # pylint: disable=wrong-import-position


# Guard clauses keep malformed or cross-repository envelopes out of capture.
# pylint: disable=too-many-return-statements
# Guard clauses keep malformed or cross-repository envelopes out of capture.
# pylint: disable=too-many-return-statements
def _project_profile(envelope: dict[str, Any]) -> tuple[Path, str] | None:
    """Validate a capture envelope against this repository's root/profile marker."""
    raw_root = envelope.get("cwd") or envelope.get("workspace_root")
    if not isinstance(raw_root, str) or not Path(raw_root).is_absolute():
        return None
    try:
        root = curatormd.resolve_project_root(raw_root)
    except (OSError, ValueError, curatormd.CuratorError):
        return None
    marker = root / ".curatormd" / "project.json"
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    raw_project = cast(dict[object, object], data)
    if not all(isinstance(key, str) for key in raw_project):
        return None
    project = cast(dict[str, Any], data)
    if project.get("project_root") != str(root):
        return None
    profile = project.get("profile")
    if not isinstance(profile, str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", profile):
        return None
    return root, profile


def _safe_id(value: Any, maximum: int = 200) -> str:
    if not isinstance(value, (str, int)):
        return "unknown"
    return str(value)[:maximum]


def _buffer_path(root: Path, profile: str, session_id: str, turn_id: str) -> Path:
    key = hashlib.sha256(f"{profile}\0{session_id}\0{turn_id}".encode()).hexdigest()
    return root / ".curatormd" / "sde-buffer" / f"{key}.json"


def _new_sde_id(root: Path, profile: str, session_id: str, turn_id: str) -> str:
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    seed = f"{root}\0{profile}\0{session_id}\0{turn_id}\0{timestamp}"
    return hashlib.sha256(seed.encode()).hexdigest()[:12].upper()


def _write_buffer(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".sde.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _prune_buffers(directory: Path) -> None:
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - 7 * 24 * 60 * 60
    for path in directory.glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


# Keep the bounded before/after capture flow together; its guards are intentional.
# pylint: disable=too-many-locals,too-many-branches,too-many-return-statements
def capture(event_name: str, envelope: dict[str, Any]) -> dict[str, Any] | None:
    """Capture only bounded SDE vocabulary and safe identifiers from one event."""
    identity = _project_profile(envelope)
    if identity is None:
        return None
    root, profile = identity
    if event_name == "UserPromptSubmit":
        text = envelope.get("prompt", "")
    elif event_name == "Stop":
        text = envelope.get("last_assistant_message", "")
    else:
        return None
    if not isinstance(text, str) or not text:
        return None
    cues = match_sde_cues(text[:100_000])
    session_id = _safe_id(envelope.get("session_id"))
    turn_id = _safe_id(envelope.get("turn_id") or envelope.get("submission_id"))
    buffer_path = _buffer_path(root, profile, session_id, turn_id)
    buffer_dir = buffer_path.parent

    if event_name == "UserPromptSubmit":
        if not cues:
            return None
        sde_digest = _new_sde_id(root, profile, session_id, turn_id)
        _write_buffer(
            buffer_path,
            {
                "sde_id": f"SDE-{sde_digest}",
                "before": cues,
                "session_ref": hashlib.sha256(session_id.encode()).hexdigest()[:16],
                "turn_ref": hashlib.sha256(turn_id.encode()).hexdigest()[:16],
            },
        )
        _prune_buffers(buffer_dir)
        return {"buffered": True, "sde_id": f"SDE-{sde_digest}"}

    before: dict[str, list[str]] = {}
    buffered: dict[str, Any] = {}
    lock_path = buffer_dir / ".lock"
    if buffer_path.exists():
        try:
            with lock_path.open("a+") as lock:
                os.chmod(lock_path, 0o600)
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                buffered = json.loads(buffer_path.read_text(encoding="utf-8"))
                buffer_path.unlink(missing_ok=True)
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            if isinstance(buffered.get("before"), dict):
                before = buffered["before"]
        except (OSError, ValueError, json.JSONDecodeError):
            buffered = {}
    if not cues and not before:
        return None
    sde_id = buffered.get("sde_id")
    if not isinstance(sde_id, str):
        sde_digest = _new_sde_id(root, profile, session_id, turn_id)
        sde_id = f"SDE-{sde_digest}"
    all_cues: dict[str, list[str]] = {}
    for category in sorted(set(before) | set(cues)):
        all_cues[category] = sorted(set(before.get(category, ())) | set(cues.get(category, ())))
    event_digest = hashlib.sha256(sde_id.encode()).hexdigest()
    result = curatormd.native_projection_record(
        str(root),
        f"codex-sde:{event_digest}",
        "codex:sde:thread",
        {
            "candidate_type": "significant_development_event",
            "sde_id": sde_id,
            "before": before,
            "after": cues,
            "cue_categories": list(all_cues),
            "matched_vocabulary": sorted({word for words in all_cues.values() for word in words}),
            "review_safe_summary": {
                "text": None,
                "status": "unavailable",
                "generator": "cue-only-capture",
            },
            "evidence_policy": "vocabulary_only_no_prompt_or_response_text",
            "session_ref": buffered.get("session_ref")
            or hashlib.sha256(session_id.encode()).hexdigest()[:16],
            "turn_ref": buffered.get("turn_ref")
            or hashlib.sha256(turn_id.encode()).hexdigest()[:16],
        },
        profile=profile,
    )
    return result


def main() -> int:
    """Read one hook event; capture failures never interrupt the caller."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, choices=("UserPromptSubmit", "Stop"))
    args = parser.parse_args()
    try:
        envelope = json.load(sys.stdin)
        if isinstance(envelope, dict):
            raw_envelope = cast(dict[object, object], envelope)
            if all(isinstance(key, str) for key in raw_envelope):
                capture(args.event, cast(dict[str, Any], envelope))
    except Exception:  # pylint: disable=broad-exception-caught
        # Capture is best effort and must never block the Codex turn.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
