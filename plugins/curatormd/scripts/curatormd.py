#!/usr/bin/env python3
"""Local-first CuratorMD primitives for an explicitly scoped project."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator, cast


STORE_NAMES = {
    "agents": "AGENTS.md",
    "sop": "SOP.md",
    "history": "HISTORY.md",
    "lessons": "LESSONS-LEARNED.md",
}
STORE_KINDS = frozenset(STORE_NAMES)
INBOX_RETENTION_DAYS = 30
MAX_PAYLOAD_BYTES = 24_000
SCHEMA_VERSION = 3

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.I | re.S),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:password|passwd|token|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[:=]\s*[^\s<>{}\[\]]{8,}"),
    re.compile(r"(?i)\b(?:https?|redis|postgres(?:ql)?)://[^\s/@:]+:[^\s/@]+@"),
)
SECRET_KEY_RE = re.compile(r"(?i)(?:password|passwd|token|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|private[_-]?key)")


class CuratorError(RuntimeError):
    """A safe, user-facing CuratorMD failure."""


class CurationBusy(CuratorError):
    """Another curator currently owns the project lock."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def clean(value: Any, field: str, limit: int = 20_000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    if "\x00" in value:
        raise ValueError(f"{field} contains a NUL byte")
    if len(value) > limit:
        raise ValueError(f"{field} exceeds the {limit}-character limit")
    return value.strip()


def _object_dict(value: Any) -> dict[str, Any]:
    """Narrow a value loaded from JSON to an object with string keys."""
    if not isinstance(value, dict):
        return {}
    entries = cast(dict[object, Any], value)
    return {key: item for key, item in entries.items() if isinstance(key, str)}


def reject_secrets(*values: str | None) -> None:
    combined = "\n".join(value or "" for value in values)
    for pattern in SECRET_PATTERNS:
        if pattern.search(combined):
            raise ValueError("Refusing to persist content that resembles a credential or private key")


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redact_payload(value: Any, *, key: str = "") -> Any:
    if SECRET_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_text(value[:8_000])
    if isinstance(value, dict):
        entries = cast(dict[object, Any], value)
        return {str(k)[:120]: redact_payload(v, key=str(k)) for k, v in list(entries.items())[:100]}
    if isinstance(value, list):
        values = cast(list[Any], value)
        return [redact_payload(item, key=key) for item in values[:100]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_text(str(value)[:8_000])


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_git(root: Path, *args: str, timeout: int = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False, timeout=timeout)


def resolve_project_root(project_root: str | os.PathLike[str] | None) -> Path:
    """Fail closed unless the path resolves to the Git worktree root with persistence/."""
    if project_root is None:
        raise CuratorError("project_root is required and must be an absolute path")
    candidate = Path(project_root).expanduser()
    if not candidate.is_absolute():
        raise CuratorError("project_root must be an absolute path")
    try:
        root = candidate.resolve(strict=True)
    except OSError as exc:
        raise CuratorError(f"project_root is missing or unreadable: {candidate}") from exc
    if not root.is_dir():
        raise CuratorError("project_root must be a directory")
    result = _run_git(root, "rev-parse", "--show-toplevel")
    if result.returncode != 0 or not result.stdout.strip():
        raise CuratorError("project_root must be inside a Git worktree")
    try:
        worktree = Path(result.stdout.strip()).resolve(strict=True)
    except OSError as exc:
        raise CuratorError("Git worktree root is unavailable") from exc
    if root != worktree:
        raise CuratorError(f"project_root must be the Git worktree root: {worktree}")
    if not (root / "persistence").is_dir():
        raise CuratorError("project_root must contain persistence/")
    return root


def store_paths(root: Path) -> dict[str, Path]:
    persistence = root / "persistence"
    return {key: persistence / filename for key, filename in STORE_NAMES.items()}


def _safe_relpath(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return "[outside-project]"


def _file_metadata(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        return {"path": relative, "present": False}
    data = path.read_bytes()
    return {"path": relative, "present": True, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _approved_manifest_metadata(root: Path) -> dict[str, Any]:
    manifests = [
        "package.json", "package-lock.json", "nuxt.config.ts", "tsconfig.json",
        "Dockerfile", "compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml",
        ".github/workflows", ".circleci/config.yml",
    ]
    result: dict[str, Any] = {}
    for relative in manifests:
        path = root / relative
        if path.is_dir():
            result[relative] = {"present": True, "files": sorted(_safe_relpath(item, root) for item in path.rglob("*") if item.is_file())[:100]}
        else:
            result[relative] = _file_metadata(root, relative)
    package = root / "package.json"
    if package.is_file():
        try:
            package_data = _object_dict(json.loads(package.read_text(encoding="utf-8")))
            metadata = _object_dict(result.get("package.json"))
            metadata["name"] = package_data.get("name")
            for field in ("scripts", "dependencies", "devDependencies"):
                section = _object_dict(package_data.get(field))
                metadata[field] = sorted(section)
            result["package.json"] = metadata
        except (OSError, json.JSONDecodeError):
            metadata = _object_dict(result.get("package.json"))
            metadata["parse"] = "unavailable"
            result["package.json"] = metadata
    return result


def _persistence_health(root: Path) -> dict[str, Any]:
    stores: list[dict[str, Any]] = []
    for name, path in store_paths(root).items():
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        stores.append({
            "store": name, "file": str(path.relative_to(root)), "exists": path.exists(),
            "bytes": len(text.encode()), "lines": len(text.splitlines()),
            "merge_conflict_markers": any(marker in text for marker in ("<<<<<<<", "=======", ">>>>>>>")),
        })
    return {"stores": stores, "healthy": all(item["exists"] and not item["merge_conflict_markers"] for item in stores)}


def _git_state(root: Path) -> dict[str, Any]:
    branch = _run_git(root, "branch", "--show-current").stdout.strip()
    status = _run_git(root, "status", "--short", "--untracked-files=all").stdout.splitlines()
    diff = _run_git(root, "diff", "--", "persistence").stdout
    staged = _run_git(root, "diff", "--cached", "--", "persistence").stdout
    return {
        "branch": branch or "detached", "status": status[:200], "status_truncated": len(status) > 200,
        "persistence_diff_sha256": sha256_text(diff + "\n" + staged), "persistence_diff_bytes": len((diff + staged).encode()),
    }


def environment_snapshot(project_root: str | os.PathLike[str]) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    manifests = _approved_manifest_metadata(root)
    return {
        "schema_version": SCHEMA_VERSION, "project_root": str(root), "captured_at": iso_now(),
        "git": _git_state(root), "approved_manifests": manifests,
        "ci_container_markers": {
            "github_workflows": (root / ".github/workflows").is_dir(), "circleci": (root / ".circleci/config.yml").is_file(),
            "dockerfiles": sorted(path.name for path in root.glob("Dockerfile*")),
            "compose_files": sorted(path.name for path in root.glob("*compose*.y*ml")),
        },
        "known_commands": {"package_scripts": manifests.get("package.json", {}).get("scripts", []), "fixed": ["git status --short", "npm run build", "hermes status", "codex doctor"]},
        "persistence": _persistence_health(root),
    }


def _plugin_data_root(root: Path, profile: str | None = None) -> Path:
    configured = os.environ.get("CURATORMD_PLUGIN_DATA")
    base = Path(configured).expanduser() if configured else Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser() / "PLUGIN_DATA"
    profile_name = clean(profile or os.environ.get("HERMES_PROFILE", "default"), "profile", 120)
    return base / "curatormd" / profile_name / sha256_text(str(root))[:24]


def plugin_data_root(root: Path, profile: str | None = None) -> Path:
    """Return the private CuratorMD data directory for a project and profile."""
    return _plugin_data_root(root, profile)


def _state_path(root: Path, profile: str | None = None) -> Path:
    return _plugin_data_root(root, profile) / "state.json"


def _load_state(root: Path, profile: str | None = None) -> dict[str, Any]:
    path = _state_path(root, profile)
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "project_root": str(root), "processed": {}, "cursor": None, "observer": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CuratorError(f"CuratorMD state is unreadable: {path}") from exc
    data = _object_dict(data)
    if data.get("project_root") != str(root):
        raise CuratorError("CuratorMD state belongs to another project")
    return data


def _atomic_json(path: Path, data: Any, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def atomic_json(path: Path, data: Any, *, mode: int = 0o600) -> None:
    """Atomically write JSON using CuratorMD's private file permissions."""
    _atomic_json(path, data, mode=mode)


def _create_json_once(path: Path, data: Any, *, mode: int = 0o600) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            return False
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return True
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def create_json_once(path: Path, data: Any, *, mode: int = 0o600) -> bool:
    """Create a JSON file without replacing an existing record."""
    return _create_json_once(path, data, mode=mode)


def _save_state(root: Path, state: dict[str, Any], profile: str | None = None) -> None:
    state_path = _state_path(root, profile)
    state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = state_path.parent / "state.lock"
    with lock_path.open("a+") as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        latest = _load_state(root, profile)
        merged = dict(latest)
        for key, value in state.items():
            if key == "processed" and isinstance(value, dict):
                merged[key] = {**_object_dict(latest.get(key)), **_object_dict(value)}
            elif key == "curator_store_hashes" and isinstance(value, dict):
                merged[key] = {**_object_dict(latest.get(key)), **_object_dict(value)}
            elif key == "observer" and isinstance(value, dict):
                old = _object_dict(latest.get(key))
                new = _object_dict(value)
                old_seen, new_seen = str(old.get("last_seen_at") or ""), str(new.get("last_seen_at") or "")
                merged[key] = dict(new if new_seen >= old_seen else old)
            else:
                merged[key] = value
        merged["schema_version"] = SCHEMA_VERSION
        merged["project_root"] = str(root)
        _atomic_json(state_path, merged)
        state.clear()
        state.update(merged)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _inbox_dir(root: Path) -> Path:
    path = root / ".curatormd" / "native-inbox"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(root / ".curatormd", 0o700)
    os.chmod(path, 0o700)
    return path


def _cleanup_inbox(root: Path) -> int:
    cutoff = utc_now() - timedelta(days=INBOX_RETENTION_DAYS)
    removed = 0
    for path in _inbox_dir(root).glob("*.json"):
        try:
            record = _object_dict(json.loads(path.read_text(encoding="utf-8")))
            terminal = record.get("finalized") is True or record.get("suppressed") is True
            if terminal and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
                path.unlink()
                removed += 1
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return removed


def native_projection_record(project_root: str | os.PathLike[str], source_id: str, event_type: str, payload: Any, cursor: str | None = None, profile: str | None = None) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    source_id = clean(source_id, "source_id", 300)
    event_type = clean(event_type, "event_type", 120)
    if not isinstance(payload, (dict, list, str)):
        raise ValueError("payload must be an object, array, or string")
    if isinstance(payload, dict):
        from curation_learning import safe_summary
        payload = _object_dict(payload)
        payload["review_safe_summary"] = safe_summary(payload)
        # The summary is prepared first; raw conversation fields never enter the inbox.
        if "response" in payload:
            payload["response"] = "[REDACTED]"
        if "message" in payload:
            payload["message"] = "[REDACTED]"
    safe_payload = redact_payload(payload)
    if len(canonical_json(safe_payload).encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError(f"payload exceeds the {MAX_PAYLOAD_BYTES}-byte limit")
    fingerprint = sha256_text(canonical_json({"source_id": source_id, "event_type": event_type, "payload": safe_payload}))
    record_id = sha256_text(f"{source_id}:{fingerprint}")[:32]
    record = {
        "schema_version": SCHEMA_VERSION, "record_id": record_id, "project_root": str(root),
        "source_id": source_id, "event_type": event_type, "fingerprint": fingerprint,
        "cursor": clean(cursor, "cursor", 300) if cursor else None, "captured_at": iso_now(),
        "reviewed": False, "payload": safe_payload,
    }
    path = _inbox_dir(root) / f"{record_id}.json"
    duplicate = not _create_json_once(path, record)
    state = _load_state(root, profile)
    state["observer"] = {"last_seen_at": record["captured_at"], "last_source_id": source_id, "status": "healthy", "inbox": ".curatormd/native-inbox/"}
    state["capture_status"] = "healthy"
    if cursor:
        state["cursor"] = cursor
    _save_state(root, state, profile)
    _cleanup_inbox(root)
    return {"written": not duplicate, "duplicate": duplicate, "record_id": record_id, "file": _safe_relpath(path, root), "capture": "healthy"}


def parse_defined_sde(
    project_root: str | os.PathLike[str], sde: dict[str, Any], *, profile: str | None = None,
) -> dict[str, Any]:
    """Validate a Hermes-produced SDE definition and queue a readable review candidate."""
    root = resolve_project_root(project_root)
    required = ("title", "beginning", "middle", "end")
    optional = ("rationale", "utility", "impact", "follow_up")
    allowed = {*required, *optional, "archive"}
    if set(sde) - allowed:
        raise ValueError("sde contains unsupported fields")
    parsed = {
        key: redact_text(clean(sde.get(key), f"sde.{key}", 300 if key == "title" else 4_000))
        for key in required
    }
    for key in optional:
        value = sde.get(key)
        if value is not None:
            parsed[key] = redact_text(clean(value, f"sde.{key}", 2_000))
    archive = sde.get("archive", "history")
    if archive not in STORE_KINDS:
        raise ValueError("sde.archive must be agents, sop, history, or lessons")
    body = [
        f"## {parsed['title']}",
        f"**Beginning — trigger and context:** {parsed['beginning']}",
        f"**Middle — decisions and work:** {parsed['middle']}",
        f"**End — outcome and verification:** {parsed['end']}",
    ]
    for key, label in (("rationale", "Rationale"), ("utility", "Future utility"), ("impact", "Project impact"), ("follow_up", "Follow-up")):
        if parsed.get(key):
            body.append(f"**{label}:** {parsed[key]}")
    content = "\n\n".join(body)
    source_id = "defined-sde:" + sha256_text(canonical_json(parsed))[:32]
    result = native_projection_record(
        root,
        source_id,
        "codex:sde:parsed",
        {
            "candidate_type": "defined_sde",
            "candidate_title": parsed["title"],
            "candidate_archive": archive,
            "review_safe_summary": {"text": content, "status": "generated", "generator": "defined-sde-schema"},
            "parsed_sde": parsed,
            "evidence_policy": "semantic_synthesis_secret_scan_raw_thread_not_stored",
        },
        profile=profile,
    )
    return {**result, "candidate_title": parsed["title"], "archive_suggestion": archive, "content": content}


def _knowledge_conflict(root: Path, path: Path, expected_hash: str | None = None) -> bool:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if any(marker in text for marker in ("<<<<<<<", "=======", ">>>>>>>")):
        return True
    changed = bool(_run_git(root, "status", "--short", "--", str(path.relative_to(root))).stdout.strip())
    if not changed:
        return False
    current_hash = sha256_text(text)
    return not expected_hash or current_hash != expected_hash


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def _find_persisted_fingerprint(root: Path, fingerprint: str) -> str | None:
    """Find an exact review fingerprint already present in canonical Markdown."""
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        return None
    for path in store_paths(root).values():
        if path.is_file() and fingerprint in path.read_text(encoding="utf-8"):
            return str(path.relative_to(root))
    return None


def _append_reviewed(
    root: Path,
    kind: str,
    title: str,
    content: str,
    rationale: str,
    impact: str,
    *,
    record_id: str | None = None,
    fingerprint: str | None = None,
    expected_hash: str | None = None,
) -> dict[str, Any]:
    title, content = clean(title, "title", 300), clean(content, "content")
    rationale, impact = rationale.strip(), impact.strip()
    reject_secrets(title, content, rationale, impact)
    if kind not in STORE_KINDS:
        raise ValueError(f"kind must be one of: {', '.join(sorted(STORE_KINDS))}")
    record_id = record_id or sha256_text(canonical_json([kind, title, content, rationale, impact]))[:32]
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", record_id):
        raise ValueError("record_id contains unsupported characters")
    path = store_paths(root)[kind]
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    marker_prefix = f"<!-- curatormd:record_id={record_id};content_sha256="
    content_hash = sha256_text(canonical_json([kind, title, content, rationale, impact]))
    fingerprint_file = _find_persisted_fingerprint(root, fingerprint or "") if fingerprint else None
    if fingerprint_file:
        return {
            "written": False, "duplicate": True, "already_present": True,
            "warning": f"fingerprint already present in {fingerprint_file}",
            "deletion_pending": True, "kind": kind, "file": fingerprint_file,
            "title": title, "record_id": record_id,
        }
    for existing_path in store_paths(root).values():
        if not existing_path.is_file():
            continue
        for line in existing_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(marker_prefix):
                if line == f"{marker_prefix}{content_hash} -->":
                    existing_file = str(existing_path.relative_to(root))
                    return {
                        "written": False, "duplicate": True, "already_present": True,
                        "warning": f"record already present in {existing_file}",
                        "deletion_pending": True, "kind": kind, "file": existing_file,
                        "title": title, "record_id": record_id,
                    }
                raise CuratorError(f"record_id already exists with different content: {record_id}")
    if _knowledge_conflict(root, path, expected_hash):
        raise CuratorError(f"knowledge document has unresolved or uncommitted edits: {path.relative_to(root)}")
    today = datetime.now().date().isoformat()
    if kind == "history":
        entry = f"## {today} — {title}\n\n**Decision:** {content}\n"
        if rationale: entry += f"\n**Rationale:** {rationale}\n"
        if impact: entry += f"\n**Impact:** {impact}\n"
    elif kind == "lessons":
        entry = f"## {title}\n\n**Date:** {today}\n\n**Lesson:** {content}\n"
        if rationale: entry += f"\n**Trigger / root cause:** {rationale}\n"
        if impact: entry += f"\n**Preventative rule:** {impact}\n"
    elif kind == "sop":
        entry = f"## {title}\n\n**Added:** {today}\n\n{content}\n"
        if impact: entry += f"\n**Verification:** {impact}\n"
    else:
        entry = f"- {content}\n" + (f"  - **Why:** {rationale}\n" if rationale else "")
    entry = f"\n{entry.rstrip()}\n\n{marker_prefix}{content_hash} -->\n"
    if fingerprint and re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        entry += f"<!-- curatormd:fingerprint={fingerprint} -->\n"
    updated = raw.rstrip() + "\n" + entry if raw.strip() else f"# {path.stem}\n{entry}"
    _atomic_text(path, updated)
    return {"written": True, "duplicate": False, "kind": kind, "file": str(path.relative_to(root)), "title": title, "record_id": record_id}


@contextlib.contextmanager
def curation_lock(root: Path) -> Generator[dict[str, Any], None, None]:
    lock_path = root / ".curatormd" / "curation.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(lock_path.parent, 0o700)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CurationBusy("another CuratorMD run holds the project lock") from exc
        owner = {"pid": os.getpid(), "started_at": iso_now(), "lock": str(lock_path.relative_to(root))}
        handle.seek(0)
        handle.truncate()
        json.dump(owner, handle)
        handle.flush()
        yield owner
    finally:
        with contextlib.suppress(OSError): fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _load_inbox(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    inbox = root / ".curatormd" / "native-inbox"
    if not inbox.is_dir():
        return records
    for path in sorted(inbox.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        record = _object_dict(data)
        if record.get("project_root") == str(root): records.append(record)
    return records


def _record_path(root: Path, record_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", record_id):
        raise ValueError("invalid record_id")
    return _inbox_dir(root) / f"{record_id}.json"


def _has_text_leaf(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip()) and value.strip() not in {"[REDACTED]", "unknown"}
    if isinstance(value, list):
        return any(_has_text_leaf(item) for item in cast(list[Any], value))
    if isinstance(value, dict):
        return any(_has_text_leaf(item) for item in cast(dict[object, Any], value).values())
    return False


def _has_disposition_content(value: Any) -> bool:
    """Check for actual event/candidate content, ignoring projection metadata."""
    text_fields = {"title", "content", "beginning", "middle", "end", "summary", "text", "response", "message", "utility", "impact", "rationale", "follow_up"}
    nested_fields = {"requested_candidate", "parsed_sde"}
    cue_fields = {"before", "after", "matched_vocabulary", "cue_categories"}
    if isinstance(value, dict):
        value_object = _object_dict(value)
        result = _object_dict(value_object.get("result"))
        if result:
            change_fields = (
                "changed_project", "decision_made", "configuration_changed", "dependency_changed",
                "interface_changed", "architecture_changed", "documentation_changed",
                "security_changed", "data_changed",
            )
            if any(result.get(field) is True for field in change_fields):
                return True
            if result.get("status") in {"failure", "partial", "blocked"}:
                return True
        for key, item in value_object.items():
            if key in text_fields and isinstance(item, str) and item.strip() not in {"", "[REDACTED]", "unknown"}:
                return True
            if key == "review_safe_summary" and _object_dict(item).get("text"):
                return _has_text_leaf(_object_dict(item).get("text"))
            if key in nested_fields and _has_disposition_content(item):
                return True
            if key in cue_fields and _has_text_leaf(item):
                return True
            if key == "result" and _has_disposition_content(item):
                return True
        return False
    if isinstance(value, list):
        return any(_has_disposition_content(item) for item in cast(list[Any], value))
    if isinstance(value, str):
        return bool(value.strip()) and value.strip() != "[REDACTED]"
    return False


def _candidate_is_reviewable(value: Any) -> bool:
    candidate = _object_dict(value)
    return all(isinstance(candidate.get(key), str) and bool(candidate[key].strip()) for key in ("title", "content"))


def _record_candidate_is_reviewable(record: dict[str, Any]) -> bool:
    if not _candidate_is_reviewable(record.get("candidate")):
        return False
    payload = _object_dict(record.get("payload"))
    return payload.get("candidate_type") != "significant_development_event"


def _scratch_incomplete_record(root: Path, record: dict[str, Any], reason: str) -> dict[str, Any]:
    """Preserve an incomplete, redacted inbox item for manual disposition."""
    record_id = clean(record.get("record_id"), "record_id", 180)
    _record_path(root, record_id)  # Validate the identifier before using it in a path.
    scratch_dir = root / ".curatormd" / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root / ".curatormd", 0o700)
    os.chmod(scratch_dir, 0o700)
    payload = redact_payload(_object_dict(record.get("payload")))
    artifact = {
        "schema_version": 1,
        "record_id": record_id,
        "source_id": redact_text(str(record.get("source_id") or ""))[:300],
        "event_type": redact_text(str(record.get("event_type") or ""))[:120],
        "captured_at": str(record.get("captured_at") or ""),
        "status": "awaiting-manual-disposition",
        "reason": redact_text(reason)[:500],
        "payload": payload,
        "candidate": redact_payload(record.get("candidate")) if isinstance(record.get("candidate"), dict) else None,
        "manual_disposition": {"decision": None, "notes": ""},
    }
    path = scratch_dir / f"{record_id}.json"
    created = _create_json_once(path, artifact)
    return {"record_id": record_id, "file": str(path.relative_to(root)), "created": created}


def _candidate_for(root: Path, record: dict[str, Any], profile: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    from curation_learning import extract_features, meaningful, predict, snapshot
    has_meaning, reason = meaningful(record)
    if not has_meaning:
        return None, None, reason
    payload = _object_dict(record.get("payload"))
    summary = _object_dict(payload.get("review_safe_summary"))
    if not isinstance(summary.get("text"), str) or not summary.get("text", "").strip():
        from curation_learning import safe_summary
        summary = safe_summary(payload)
        payload["review_safe_summary"] = summary
        record["payload"] = payload
    text = summary.get("text")
    if not isinstance(text, str) or not text.strip():
        return None, None, "safe summary unavailable"
    result = _object_dict(payload.get("result"))
    parsed_sde = _object_dict(payload.get("parsed_sde"))
    proposed = predict(root, profile, record)
    probability = float(proposed.get("disposition_probability", 0.5))
    priority_probs = _object_dict(proposed.get("priority_probabilities"))
    if proposed.get("priority_model_status") == "fit":
        priority = int(max(range(6), key=lambda item: float(priority_probs.get(str(item), 0.0))))
    else:
        priority = 1
    archive_probs = _object_dict(proposed.get("archive_probabilities"))
    requested_archive = payload.get("candidate_archive")
    if isinstance(requested_archive, str) and requested_archive in STORE_KINDS:
        archive = requested_archive
    elif proposed.get("archive_model_status") == "fit":
        archive = max(("agents", "sop", "history", "lessons"), key=lambda item: float(archive_probs.get(item, 0.0)))
    else:
        archive = "history"
    disposition = "approved" if probability >= 0.5 else "do-not-record"
    failure = result.get("status") in {"failure", "partial", "blocked"} or (isinstance(result.get("failure_class"), str) and result.get("failure_class") not in {"none", "unknown", ""})
    if failure:
        archive = "lessons"
    title_hint = payload.get("candidate_title")
    if not isinstance(title_hint, str) or not title_hint.strip():
        title_hint = text
    title = re.sub(r"\s+", " ", title_hint).strip().rstrip(".!?")
    # SDE identifiers belong in metadata/content, not at the start of the human title.
    title = re.sub(r"^SDE-[A-F0-9]{12}:\s*", "", title, flags=re.IGNORECASE)
    if len(title) > 300:
        title = title[:297].rsplit(" ", 1)[0].rstrip(".,;:-") + "..."
    title = title or "CuratorMD event"
    if payload.get("candidate_type") == "defined_sde" and parsed_sde:
        beginning = str(parsed_sde.get("beginning") or "the situation described in this event")[:500]
        middle = str(parsed_sde.get("middle") or "the decisions and work described in this event")[:1200]
        end = str(parsed_sde.get("end") or "the outcome described in this event")[:1500]
        utility = str(parsed_sde.get("utility") or f"Helps future work address {beginning} by preserving the decisions and implementation path: {middle}")
        impact = str(parsed_sde.get("impact") or f"Observed outcome and verification: {end}")
    else:
        utility = str(payload.get("candidate_utility") or "The source event does not specify a concrete future-use benefit.")
        impact = str(payload.get("candidate_impact") or "The source event does not state an evidenced project-quality effect.")
    candidate = {
        "kind": archive,
        "title": title,
        "content": text.strip(),
        "utility": utility,
        "impact": impact,
    }
    proposal = {
        "disposition": disposition,
        "disposition_probability": probability,
        "priority": priority,
        "priority_probabilities": priority_probs,
        "archive": archive,
        "archive_probabilities": archive_probs,
        "model_version": proposed.get("model_version", "prior-only"),
        "features": extract_features(record),
        "summary_status": summary.get("status", "unavailable"),
    }
    selection = {
        "disposition": {"selected": "pending", "options": ["pending", "approved", "do-not-record"]},
        "priority": {"selected": priority, "options": [0, 1, 2, 3, 4, 5]},
        "archive": {"selected": archive, "options": ["agents", "sop", "history", "lessons"]},
    }
    review = {"reviewed": False, "selection": selection, "human_edits": {"title": None, "content": None, "utility": None, "impact": None}, "finalized_at": None}
    prediction = snapshot(root, profile, record, proposal)
    return candidate, {"proposal": proposal, "review": review, "prediction_snapshot": prediction}, reason


def _observation_for(record: dict[str, Any], review: dict[str, Any], candidate: dict[str, Any], revision: int) -> dict[str, Any] | None:
    from curation_learning import extract_features
    selection = _object_dict(review.get("selection"))
    disposition = _object_dict(selection.get("disposition")).get("selected")
    if disposition not in {"approved", "do-not-record"}:
        return None
    priority = _object_dict(selection.get("priority")).get("selected")
    archive = _object_dict(selection.get("archive")).get("selected")
    human_edits = _object_dict(review.get("human_edits"))
    proposal = _object_dict(record.get("proposal"))
    archive_final = archive if disposition == "approved" else None
    ai_priority = proposal.get("priority")
    ai_archive = proposal.get("archive")
    return {
        "schema_version": 1,
        "observation_id": f"{record['record_id']}-r{revision}",
        "record_id": record["record_id"],
        "review_revision": revision,
        "supersedes_observation_id": review.get("supersedes_observation_id"),
        "event_timestamp": record.get("captured_at"),
        "proposal_timestamp": record.get("proposal_timestamp", record.get("captured_at")),
        "review_timestamp": review.get("finalized_at", iso_now()),
        "features": extract_features(record),
        "ai_proposal": {"disposition": proposal.get("disposition"), "disposition_probability": proposal.get("disposition_probability"), "priority": ai_priority, "archive": ai_archive, "model_version": proposal.get("model_version")},
        "disposition": disposition,
        "priority": priority,
        "archive": archive_final,
        "corrections": {
            "disposition_changed": disposition != proposal.get("disposition"),
            "priority_changed": priority != ai_priority if isinstance(priority, int) and isinstance(ai_priority, int) else None,
            "archive_changed": archive_final != ai_archive if disposition == "approved" else None,
            "text_changed": any(bool(human_edits.get(key)) for key in ("title", "content", "utility", "impact")),
        },
        "review_source": "human",
        "audit": {"producer_schema_version": record.get("schema_version", 1), "feature_extractor_version": "1", "proposal_generator_version": "1"},
        "analysis_eligible": isinstance(priority, int) and not isinstance(priority, bool),
        "qa_windows_finalized": False,
        "retrospective_finalized": False,
        "active": True,
    }


def _apply_transaction(root: Path, profile: str | None, state: dict[str, Any], transaction: dict[str, Any]) -> dict[str, Any]:
    from curation_learning import write_json, learning_root
    record_id = transaction["record_id"]
    candidate = transaction["candidate"]
    disposition = transaction["disposition"]
    store_hashes = state.setdefault("curator_store_hashes", {})
    archive_result = None
    if disposition == "approved":
        archive_result = _append_reviewed(
            root, transaction["archive"], candidate["title"], candidate["content"],
            candidate.get("utility", ""), candidate.get("impact", ""),
            record_id=record_id,
            fingerprint=transaction.get("fingerprint"),
            expected_hash=transaction.get("target_hash") or store_hashes.get(transaction["archive"]),
        )
        archive_path = store_paths(root)[transaction["archive"]]
        store_hashes[transaction["archive"]] = sha256_text(archive_path.read_text(encoding="utf-8"))
    learning_result = None
    if transaction.get("observation"):
        from curation_learning import save_observation
        learning_result = save_observation(root, profile, transaction["observation"])
        superseded_id = transaction["observation"].get("supersedes_observation_id")
        if superseded_id:
            old_path = learning_root(root, profile) / "observations" / f"{superseded_id}.json"
            if old_path.is_file():
                def supersede(old_observation: dict[str, Any]) -> None:
                    old_observation["active"] = False
                    old_observation["superseded_by_observation_id"] = transaction["observation"]["observation_id"]
                from curation_learning import update_observation
                update_observation(root, profile, old_path, supersede)
    record_path = _record_path(root, record_id)
    if record_path.exists():
        current = json.loads(record_path.read_text(encoding="utf-8"))
        current["review"] = transaction["review"]
        current["candidate"] = candidate
        current["reviewed"] = True
        current["finalized"] = True
        current["finalized_at"] = transaction["review"].get("finalized_at")
        current["review_revision"] = transaction["review_revision"]
        current["finalization"] = {"archive": archive_result, "learning": learning_result}
        if archive_result and archive_result.get("duplicate"):
            current["deletion_pending"] = True
            current["duplicate_warning"] = archive_result.get("warning", "already present")
        _atomic_json(record_path, current)
    state.setdefault("processed", {})[record_id] = str(transaction["fingerprint"])
    state["curator_store_hashes"] = store_hashes
    _save_state(root, state, profile)
    transaction["status"] = "committed"
    transaction["committed_at"] = iso_now()
    from curation_learning import write_json, learning_root
    write_json(learning_root(root, profile) / "transactions" / f"{record_id}-r{transaction['review_revision']}.json", transaction)
    return {"record_id": record_id, "disposition": disposition, "archive": archive_result, "learning": learning_result, "duplicate": bool(archive_result and archive_result.get("duplicate"))}


def _finalize_review(root: Path, profile: str | None, state: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    from curation_learning import read_json, learning_root
    review = record.get("review") if isinstance(record.get("review"), dict) else None
    candidate = record.get("candidate") if isinstance(record.get("candidate"), dict) else None
    if not candidate:
        raise CuratorError("reviewed record has no candidate")
    if review is None:
        # Compatibility for explicitly reviewed schema-v2 candidates.
        review = {"reviewed": True, "selection": {"disposition": {"selected": "approved"}, "priority": {"selected": None}, "archive": {"selected": candidate.get("kind")}}, "finalized_at": iso_now(), "review_source": "legacy-human"}
        record["review"] = review
    selection = _object_dict(review.get("selection"))
    disposition = _object_dict(selection.get("disposition")).get("selected")
    if not review.get("reviewed") or disposition not in {"approved", "do-not-record"}:
        raise CuratorError("review is incomplete")
    archive = _object_dict(selection.get("archive")).get("selected")
    if disposition == "approved" and (not isinstance(archive, str) or archive not in STORE_KINDS):
        raise CuratorError("approved review requires a valid archive selection")
    revision = int(record.get("review_revision", 1))
    observation = _observation_for(record, review, candidate, revision) if review.get("review_source", "human") == "human" else None
    learning_dir = learning_root(root, profile)
    journal = learning_dir / "transactions" / f"{record['record_id']}-r{revision}.json"
    prior = _object_dict(read_json(journal, None))
    if prior.get("status") == "prepared":
        prior_selection = _object_dict(_object_dict(prior.get("review")).get("selection"))
        current_selection = _object_dict(review.get("selection"))
        same_decision = (
            prior.get("disposition") == disposition
            and prior.get("archive") == archive
            and prior.get("candidate") == candidate
            and prior_selection == current_selection
        )
        if not same_decision:
            prior["status"] = "superseded"
            prior["superseded_at"] = iso_now()
            from curation_learning import write_json
            write_json(journal, prior)
            revision += 1
            record["review_revision"] = revision
            observation = _observation_for(record, review, candidate, revision) if review.get("review_source", "human") == "human" else None
            journal = learning_dir / "transactions" / f"{record['record_id']}-r{revision}.json"
            prior = None
    if prior:
        if prior.get("status") == "committed":
            return {"record_id": record["record_id"], "disposition": disposition, "duplicate": True}
        transaction = prior
    else:
        target_hash = None
        if disposition == "approved" and review.get("review_source") == "human":
            if not isinstance(archive, str):
                raise CuratorError("approved review requires a valid archive selection")
            target_path = store_paths(root)[archive]
            target_hash = sha256_text(target_path.read_text(encoding="utf-8") if target_path.exists() else "")
        transaction = {
            "schema_version": 1, "status": "prepared", "project_root": str(root),
            "record_id": record["record_id"], "fingerprint": record.get("fingerprint", ""),
            "review_revision": revision, "review": review, "candidate": candidate,
            "disposition": disposition, "archive": archive, "target_hash": target_hash,
            "observation": observation,
            "prepared_at": iso_now(),
        }
        from curation_learning import write_json
        write_json(journal, transaction)
    return _apply_transaction(root, profile, state, transaction)


def recover_transaction(
    project_root: str | os.PathLike[str], record_id: str, *,
    accept_current_target: bool = False, profile: str | None = None,
) -> dict[str, Any]:
    """Resume one prepared review; legacy journals need explicit baseline acceptance."""
    from curation_learning import read_json, write_json, learning_root
    root = resolve_project_root(project_root)
    with curation_lock(root):
        directory = learning_root(root, profile) / "transactions"
        matches = sorted(directory.glob(f"{clean(record_id, 'record_id', 180)}-r*.json"))
        prepared = [item for item in matches if read_json(item, {}).get("status") == "prepared"]
        if not prepared:
            return {"record_id": record_id, "recovered": False, "reason": "no prepared transaction"}
        path = prepared[-1]
        transaction = read_json(path, {})
        if not transaction.get("target_hash"):
            if not accept_current_target:
                raise CuratorError("legacy transaction needs manual baseline approval; rerun with --accept-current-target after reviewing the target diff")
            archive = transaction.get("archive")
            if archive not in STORE_KINDS:
                raise CuratorError("prepared transaction has no valid archive")
            target = store_paths(root)[archive]
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if any(marker in current for marker in ("<<<<<<<", "=======", ">>>>>>>")):
                raise CuratorError("manual recovery refused a target with merge-conflict markers")
            transaction["target_hash"] = sha256_text(current)
            transaction["manual_recovery_baseline_at"] = iso_now()
            write_json(path, transaction)
        state = _load_state(root, profile)
        return {**_apply_transaction(root, profile, state, transaction), "recovered": True}


def _recover_transactions(root: Path, profile: str | None, state: dict[str, Any]) -> list[dict[str, Any]]:
    from curation_learning import read_json, learning_root
    pending: list[dict[str, Any]] = []
    directory = learning_root(root, profile) / "transactions"
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        transaction = read_json(path, None)
        if not transaction or transaction.get("project_root") != str(root) or transaction.get("status") in {"committed", "superseded", "cancelled"}:
            continue
        try:
            pending.append(_apply_transaction(root, profile, state, transaction))
        except CuratorError as exc:
            pending.append({"record_id": transaction.get("record_id"), "recovery_error": str(exc)})
    return pending


def review_candidate(
    project_root: str | os.PathLike[str], record_id: str, disposition: str, priority: int,
    archive: str | None = None, *, confirm_priority_5: bool = False,
    edits: dict[str, str | None] | None = None, profile: str | None = None,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    if disposition not in {"approved", "do-not-record"}:
        raise ValueError("disposition must be approved or do-not-record")
    if isinstance(priority, bool) or priority not in range(6):
        raise ValueError("priority must be an integer from 0 through 5")
    if edits and set(edits) - {"title", "content", "utility", "impact"}:
        raise ValueError("edits may contain only title, content, utility, and impact")
    if priority == 5 and not confirm_priority_5:
        raise ValueError("priority 5 requires confirm_priority_5=true")
    if disposition == "approved" and archive not in STORE_KINDS:
        raise ValueError("approved reviews require archive: agents, sop, history, or lessons")
    if disposition == "do-not-record":
        archive = None
    with curation_lock(root):
        path = _record_path(root, clean(record_id, "record_id", 180))
        if not path.is_file(): raise CuratorError("native inbox record was not found")
        record = _object_dict(json.loads(path.read_text(encoding="utf-8")))
        if record.get("finalized") is True:
            edits = edits or {}
            candidate = _object_dict(record.get("candidate"))
            if not candidate: raise CuratorError("record has no generated candidate")
            if any(value is not None and value != candidate.get(key) for key, value in edits.items()):
                raise CuratorError("review revisions may correct labels only; candidate text is immutable after finalization")
            previous_review = _object_dict(record.get("review"))
            selection = _object_dict(previous_review.get("selection"))
            previous_disposition = _object_dict(selection.get("disposition")).get("selected")
            previous_priority = _object_dict(selection.get("priority")).get("selected")
            previous_archive = _object_dict(selection.get("archive")).get("selected")
            if (previous_disposition, previous_priority, previous_archive) == (disposition, priority, archive):
                return {"record_id": record_id, "disposition": disposition, "reviewed": True, "duplicate": True, "review_revision": record.get("review_revision", 1)}
            previous_observation_id = f"{record_id}-r{int(record.get('review_revision', 1))}"
            revision = int(record.get("review_revision", 1)) + 1
            review = dict(previous_review)
            review["supersedes_observation_id"] = previous_observation_id
            review["revision_history"] = list(previous_review.get("revision_history", [])) + [{"review_revision": int(record.get("review_revision", 1)), "review": previous_review}]
            review["selection"] = {
                "disposition": {"selected": disposition, "options": ["approved", "do-not-record"]},
                "priority": {"selected": priority, "options": [0, 1, 2, 3, 4, 5]},
                "archive": {"selected": archive, "options": ["agents", "sop", "history", "lessons"]},
            }
            review["review_source"] = "human"
            review["finalized_at"] = iso_now()
            review["reviewed"] = True
            record["review"] = review
            record["review_revision"] = revision
            state = _load_state(root, profile)
            result = _finalize_review(root, profile, state, record)
            return {**result, "reviewed": True, "review_revision": revision, "supersedes_observation_id": previous_observation_id}
        candidate = _object_dict(record.get("candidate"))
        if not candidate: raise CuratorError("record has no generated candidate")
        review = _object_dict(record.get("review"))
        edits = edits or {}
        final_candidate = dict(candidate)
        human_edits = {}
        for key in ("title", "content", "utility", "impact"):
            value = edits.get(key)
            if value is not None:
                value = clean(value, f"edits.{key}", 20_000 if key == "content" else 4_000)
                reject_secrets(value)
                final_candidate[key] = value
                human_edits[key] = value if value != candidate.get(key) else None
            else:
                human_edits[key] = None
        review.update({
            "reviewed": True,
            "review_source": "human",
            "selection": {
                "disposition": {"selected": disposition, "options": ["approved", "do-not-record"]},
                "priority": {"selected": priority, "options": [0, 1, 2, 3, 4, 5]},
                "archive": {"selected": archive, "options": ["agents", "sop", "history", "lessons"]},
            },
            "human_edits": human_edits,
            "finalized_at": iso_now(),
        })
        record["candidate"] = final_candidate
        record["review"] = review
        record["reviewed"] = True
        record["review_revision"] = int(record.get("review_revision", 1))
        _atomic_json(path, record)
        state = _load_state(root, profile)
        result = _finalize_review(root, profile, state, record)
        return {**result, "reviewed": True, "review_revision": record["review_revision"]}


def curate(project_root: str | os.PathLike[str], *, schedule_slot: str = "06:00 Asia/Ho_Chi_Minh", profile: str | None = None) -> dict[str, Any]:
    from curation_learning import prune, recompute
    root = resolve_project_root(project_root)
    with curation_lock(root) as owner:
        state = _load_state(root, profile)
        state["lock"], state["schedule_slot"], state["last_run_started_at"] = owner, schedule_slot, owner["started_at"]
        _save_state(root, state, profile)
        removed = _cleanup_inbox(root)
        processed = state.setdefault("processed", {})
        written: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []
        suppressed: list[dict[str, Any]] = []
        duplicates: list[str | dict[str, Any]] = []
        conflicts: list[str] = []
        recovered: list[dict[str, Any]] = []
        scratch: list[dict[str, Any]] = []
        empty_removed: list[str] = []
        recovered.extend(_recover_transactions(root, profile, state))
        records = _load_inbox(root)
        for record in records:
            record_id = str(record.get("record_id") or "")
            fingerprint = str(record.get("fingerprint") or "")
            if not record_id or not fingerprint: continue
            if record.get("suppressed") is True:
                suppressed.append({"record_id": record_id, "reason": record.get("suppression_reason", "previously suppressed")})
                continue
            if record.get("finalized") is True:
                duplicates.append(record_id)
                continue
            existing_candidate = record.get("candidate")
            if isinstance(existing_candidate, dict) and not _record_candidate_is_reviewable(record):
                payload = _object_dict(record.get("payload"))
                if not _has_disposition_content(payload) and not _has_disposition_content(existing_candidate):
                    _record_path(root, record_id).unlink(missing_ok=True)
                    empty_removed.append(record_id)
                else:
                    reason = "cue-only SDE; submit a full-thread synthesis with sde_parse" if payload.get("candidate_type") == "significant_development_event" else "candidate is missing a non-empty title or content"
                    scratch_result = _scratch_incomplete_record(root, record, reason)
                    scratch.append({**scratch_result, "reason": reason})
                    ambiguous.append({"record_id": record_id, "reason": reason, "scratch_file": scratch_result["file"]})
                continue
            if record.get("reviewed") is not True or not isinstance(record.get("candidate"), dict):
                if not isinstance(record.get("candidate"), dict):
                    candidate, generated, reason = _candidate_for(root, record, profile)
                    if candidate is None:
                        payload = _object_dict(record.get("payload"))
                        if not _has_disposition_content(payload):
                            _record_path(root, record_id).unlink(missing_ok=True)
                            empty_removed.append(record_id)
                        elif reason == "routine lifecycle event":
                            record["suppressed"] = True
                            record["suppression_reason"] = reason
                            suppressed.append({"record_id": record_id, "reason": reason})
                            _atomic_json(_record_path(root, record_id), record)
                        else:
                            scratch_result = _scratch_incomplete_record(root, record, reason)
                            scratch.append({**scratch_result, "reason": reason})
                            ambiguous.append({"record_id": record_id, "reason": reason, "scratch_file": scratch_result["file"]})
                        continue
                    if generated is None:
                        raise CuratorError("candidate generation returned no review proposal")
                    record["candidate"], record["proposal"], record["review"], record["proposal_timestamp"] = candidate, generated["proposal"], generated["review"], iso_now()
                    record["prediction_snapshot"] = generated["prediction_snapshot"]
                    _atomic_json(_record_path(root, record_id), record)
                ambiguous.append({"record_id": record_id, "candidate": _object_dict(record.get("candidate")).get("title"), "reason": "awaiting human review"})
                continue
            try:
                result = _finalize_review(root, profile, state, record)
            except (CuratorError, ValueError, OSError) as exc:
                conflicts.append(f"{record_id}: {exc}")
                continue
            archive_result = _object_dict(result.get("archive"))
            if archive_result.get("already_present"):
                duplicates.append({
                    "record_id": record_id,
                    "warning": archive_result.get("warning", "already present"),
                    "deletion_pending": True,
                })
            elif result.get("disposition") == "approved": written.append(result)
            else: rejected.append(result)
            processed[record_id] = fingerprint
        inbox_cursor: list[str] = [
            cursor for item in records
            if isinstance((cursor := item.get("cursor")), str)
        ]
        state["processed"] = dict(list(processed.items())[-10_000:])
        state["cursor"] = max(inbox_cursor, default=state.get("cursor"))
        state["last_run_finished_at"] = iso_now()
        state["lock"] = None
        observer = _object_dict(state.get("observer"))
        state["capture_status"] = "healthy" if observer.get("last_seen_at") else "degraded"
        _save_state(root, state, profile)
        try:
            learning = recompute(root, profile)
        except (CuratorError, ValueError, OSError, ArithmeticError) as exc:
            learning = {"recomputed": False, "error": str(exc)}
        try:
            retention = prune(root, profile)
        except (CuratorError, ValueError, OSError) as exc:
            retention = {"error": str(exc)}
        return {
            "project_root": str(root), "schedule_slot": schedule_slot,
            "capture": state["capture_status"], "written": written, "rejected": rejected,
            "ambiguous": ambiguous, "scratch": scratch, "empty_removed": empty_removed,
            "suppressed": suppressed, "duplicates": duplicates,
            "conflicts": conflicts, "recovered": recovered, "expired_inbox_records": removed,
            "learning": learning, "retention": retention, "state": str(_state_path(root, profile)),
            "lock": "released",
        }


def search(root: Path, query: str, scope: str = "all", limit: int = 40) -> dict[str, Any]:
    query = clean(query, "query", 500)
    terms = [term.lower() for term in re.findall(r"\S+", query)]
    if not terms: raise ValueError("query must contain at least one search term")
    paths = store_paths(root)
    if scope == "all":
        selected = paths
    elif scope in paths:
        selected = {scope: paths[scope]}
    else:
        raise ValueError(f"unknown scope: {scope}")
    matches: list[dict[str, Any]] = []
    for name, path in selected.items():
        if not path.exists(): continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if all(term in line.lower() for term in terms):
                matches.append({"store": name, "file": str(path.relative_to(root)), "line": number, "text": redact_text(line[:1000])})
                if len(matches) >= limit: return {"query": query, "matches": matches, "truncated": True}
    return {"query": query, "matches": matches, "truncated": False}


def status(root: Path, profile: str | None = None) -> dict[str, Any]:
    from curation_learning import status as learning_status_impl
    state = _load_state(root, profile)
    observer = _object_dict(state.get("observer"))
    capture_status = "healthy" if observer.get("status") == "healthy" else state.get("capture_status", "degraded")
    records = _load_inbox(root)
    pending = sum(
        _record_candidate_is_reviewable(record)
        and record.get("finalized") is not True
        and record.get("suppressed") is not True
        for record in records
    )
    return {"root": str(root), "stores": _persistence_health(root)["stores"], "git": _git_state(root), "inbox_records": len(records), "pending_reviews": pending, "capture_status": capture_status, "learning": learning_status_impl(root, profile), "state": str(_state_path(root, profile)), "schedule_slot": state.get("schedule_slot")}


def append_entry(root: Path, kind: str, title: str, content: str, rationale: str | None = None, impact: str | None = None, *, profile: str | None = None) -> dict[str, Any]:
    with curation_lock(root):
        state = _load_state(root, profile)
        result = _append_reviewed(root, kind, title, content, rationale or "", impact or "", expected_hash=_object_dict(state.get("curator_store_hashes")).get(kind))
        if result.get("written"):
            path = store_paths(root)[kind]
            state.setdefault("curator_store_hashes", {})[kind] = sha256_text(path.read_text(encoding="utf-8"))
            _save_state(root, state, profile)
        return result


def learning_status(root: Path, profile: str | None = None) -> dict[str, Any]:
    from curation_learning import status as learning_status_impl
    return learning_status_impl(root, profile)


def _safe_review_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("candidate_type") not in {"significant_development_event", "defined_sde"}:
        return None
    if payload.get("candidate_type") == "defined_sde":
        parsed = payload.get("parsed_sde")
        if not isinstance(parsed, dict):
            return None
        return {"candidate_type": "defined_sde", "parsed_sde": parsed}
    from sde_vocabulary import safe_sde_cues
    sde_id = payload.get("sde_id")
    if not isinstance(sde_id, str) or not re.fullmatch(r"SDE-[A-F0-9]{12}", sde_id):
        return None
    before = safe_sde_cues(payload.get("before"))
    after = safe_sde_cues(payload.get("after"))
    categories = sorted(set(before) | set(after))
    terms = sorted({term for cues in (before, after) for values in cues.values() for term in values})
    return {
        "candidate_type": "significant_development_event",
        "sde_id": sde_id,
        "before": before,
        "after": after,
        "before_summary": redact_text(str(payload.get("before_summary"))[:360]) if isinstance(payload.get("before_summary"), str) else None,
        "after_summary": redact_text(str(payload.get("after_summary"))[:360]) if isinstance(payload.get("after_summary"), str) else None,
        "cue_categories": categories,
        "matched_vocabulary": terms,
        "parsed_sde": payload.get("parsed_sde") if isinstance(payload.get("parsed_sde"), dict) else None,
    }


def pending_reviews(root: Path, profile: str | None = None, *, limit: int = 30) -> dict[str, Any]:
    if isinstance(limit, bool) or limit < 1 or limit > 100:
        raise ValueError("limit must be an integer from 1 through 100")
    items: list[dict[str, Any]] = []
    for record in _load_inbox(root):
        if record.get("finalized") is True or record.get("suppressed") is True:
            continue
        payload = _object_dict(record.get("payload"))
        candidate = record.get("candidate") if _record_candidate_is_reviewable(record) else None
        if candidate is None:
            continue
        items.append({
            "record_id": record.get("record_id"),
            "event_type": record.get("event_type"),
            "captured_at": record.get("captured_at"),
            "review_safe_summary": payload.get("review_safe_summary"),
            "concise_payload": _safe_review_payload(payload),
            "candidate": candidate,
            "proposal": record.get("proposal"),
            "review": record.get("review"),
            "status": "pending-review" if candidate else "candidate-generation-pending",
        })
        if len(items) >= limit: break
    return {"pending_count": len(items), "limit": limit, "records": items}


def learning_recompute(root: Path, profile: str | None = None, *, force: bool = False) -> dict[str, Any]:
    from curation_learning import recompute
    return recompute(root, profile, force=force)


def learning_report(root: Path, profile: str | None = None) -> dict[str, Any]:
    from curation_learning import report
    return report(root, profile)


def qa_outcome_record(
    root: Path,
    record_id: str,
    outcome_type: str,
    window_days: int,
    value: Any,
    evidence: str = "",
    *,
    finalize_window: bool = False,
    profile: str | None = None,
) -> dict[str, Any]:
    from curation_learning import read_json, learning_root, record_qa_outcome
    if window_days not in {30, 60, 90, 180}:
        raise ValueError("window_days must be one of 30, 60, 90, or 180")
    outcome_type = clean(outcome_type, "outcome_type", 80)
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", outcome_type):
        raise ValueError("outcome_type must be a lowercase identifier")
    if isinstance(value, str):
        value = clean(value, "value", 300)
        reject_secrets(value)
    elif not isinstance(value, (bool, int, float)) and value is not None:
        raise ValueError("value must be a string, number, boolean, or null")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("value must be finite")
    evidence = evidence.strip()
    if evidence:
        reject_secrets(evidence)
        if len(evidence) > 1000: raise ValueError("evidence exceeds 1000 characters")
    directory = learning_root(root, profile) / "observations"
    matches = sorted(directory.glob(f"{record_id}-r*.json")) if directory.exists() else []
    if not matches: raise CuratorError("learning observation was not found")
    observation_path = matches[-1]
    observation = _object_dict(read_json(observation_path, {}))
    occurred_at = iso_now()
    outcome_key = sha256_text(canonical_json([record_id, window_days, outcome_type, value, evidence]))[:24]
    outcome = {
        "schema_version": 1, "outcome_id": outcome_key, "record_id": record_id,
        "event_timestamp": observation.get("event_timestamp"), "occurred_at": occurred_at,
        "window_days": window_days, "outcome_type": outcome_type,
        "value": value, "evidence": evidence or None, "reviewed_by_human": True,
    }
    result = record_qa_outcome(root, profile, record_id, outcome)
    if finalize_window:
        from curation_learning import update_observation
        def finalize_qa(current: dict[str, Any]) -> None:
            finalized_values = current.get("qa_finalized_windows", [])
            finalized = set(cast(list[int], finalized_values))
            finalized.add(window_days)
            current["qa_finalized_windows"] = sorted(finalized)
            current["qa_windows_finalized"] = all(item in finalized for item in (30, 60, 90, 180))
        update_observation(root, profile, observation_path, finalize_qa)
    return {**result, "window_finalized": finalize_window, "finalized_windows": observation.get("qa_finalized_windows", [])}


def retrospective_review(
    root: Path,
    record_id: str,
    still_correct: str,
    usefulness: int,
    germane: str,
    *,
    should_have_recorded: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    from curation_learning import read_json, learning_root, record_retrospective
    if still_correct not in {"yes", "no", "uncertain"}:
        raise ValueError("still_correct must be yes, no, or uncertain")
    if isinstance(usefulness, bool) or usefulness not in range(5):
        raise ValueError("usefulness must be an integer from 0 through 4")
    if germane not in {"yes", "superseded", "obsolete", "uncertain"}:
        raise ValueError("germane must be yes, superseded, obsolete, or uncertain")
    if should_have_recorded is not None and should_have_recorded not in {"yes", "no", "uncertain"}:
        raise ValueError("should_have_recorded must be yes, no, or uncertain")
    directory = learning_root(root, profile) / "observations"
    matches = sorted(directory.glob(f"{record_id}-r*.json")) if directory.exists() else []
    if not matches: raise CuratorError("learning observation was not found")
    observation_path = matches[-1]
    existing_reviews = sorted((learning_root(root, profile) / "retrospective-audits").glob(f"{record_id}-r*.json"))
    if existing_reviews:
        previous = _object_dict(read_json(existing_reviews[-1], {}))
        same = (previous.get("still_correct"), previous.get("usefulness"), previous.get("germane"), previous.get("should_have_recorded")) == (still_correct, usefulness, germane, should_have_recorded)
        if same:
            return {"written": False, "duplicate": True, "record_id": record_id, "review_revision": previous.get("review_revision")}
    revision = len(existing_reviews) + 1
    review = {"schema_version": 1, "record_id": record_id, "review_revision": revision, "reviewed_at": iso_now(), "still_correct": still_correct, "usefulness": usefulness, "germane": germane, "should_have_recorded": should_have_recorded}
    result = record_retrospective(root, profile, record_id, review)
    from curation_learning import update_observation
    def finalize_retrospective(current: dict[str, Any]) -> None:
        current["retrospective_finalized"] = True
    update_observation(root, profile, observation_path, finalize_retrospective)
    return result


def self_improvement(root: Path, failure: str, cause: str, fix: str, prevention: str, *, profile: str | None = None) -> dict[str, Any]:
    failure, cause, fix, prevention = clean(failure, "failure", 2_000), clean(cause, "cause", 2_000), clean(fix, "fix", 4_000), clean(prevention, "prevention", 2_000)
    return append_entry(root, "lessons", f"Verified fix: {failure[:120]}", f"{fix}\n\n**Evidence:** The failure was reproduced or observed, and the fix was verified.", rationale=f"{failure}\n\n{cause}", impact=prevention, profile=profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, help="Absolute Git worktree root")
    parser.add_argument("--profile", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status"); sub.add_parser("snapshot")
    search_parser = sub.add_parser("search"); search_parser.add_argument("query"); search_parser.add_argument("--scope", default="all", choices=["all", *STORE_NAMES])
    record_parser = sub.add_parser("record"); record_parser.add_argument("kind", choices=STORE_NAMES); record_parser.add_argument("title"); record_parser.add_argument("content"); record_parser.add_argument("--rationale"); record_parser.add_argument("--impact")
    observe_parser = sub.add_parser("observe"); observe_parser.add_argument("source_id"); observe_parser.add_argument("event_type"); observe_parser.add_argument("payload_json"); observe_parser.add_argument("--cursor")
    sde_parser = sub.add_parser("sde-parse"); sde_parser.add_argument("sde_json", help="JSON object with title, beginning, middle, end, and optional rationale, utility, impact, follow_up, archive")
    curate_parser = sub.add_parser("curate"); curate_parser.add_argument("--schedule-slot", default="06:00 Asia/Ho_Chi_Minh")
    review_parser = sub.add_parser("review"); review_parser.add_argument("record_id"); review_parser.add_argument("disposition", choices=["approved", "do-not-record"]); review_parser.add_argument("--priority", required=True, type=int, choices=range(6)); review_parser.add_argument("--archive", choices=STORE_NAMES); review_parser.add_argument("--confirm-priority-5", action="store_true"); review_parser.add_argument("--edits-json")
    recover_parser = sub.add_parser("recover"); recover_parser.add_argument("record_id"); recover_parser.add_argument("--accept-current-target", action="store_true", help="For legacy prepared transactions only: approve the current target hash after manually reviewing its diff")
    sub.add_parser("learning-status")
    pending_parser = sub.add_parser("pending-reviews"); pending_parser.add_argument("--limit", type=int, default=30)
    learning_recompute_parser = sub.add_parser("learning-recompute"); learning_recompute_parser.add_argument("--force", action="store_true")
    sub.add_parser("learning-report")
    improve_parser = sub.add_parser("improve"); improve_parser.add_argument("failure"); improve_parser.add_argument("cause"); improve_parser.add_argument("fix"); improve_parser.add_argument("prevention")
    args = parser.parse_args()
    try:
        root = resolve_project_root(args.project_root)
        if args.command == "status": result = status(root, args.profile)
        elif args.command == "snapshot": result = environment_snapshot(str(root))
        elif args.command == "search": result = search(root, args.query, args.scope)
        elif args.command == "record": result = append_entry(root, args.kind, args.title, args.content, args.rationale, args.impact, profile=args.profile)
        elif args.command == "observe": result = native_projection_record(root, args.source_id, args.event_type, json.loads(args.payload_json), args.cursor, args.profile)
        elif args.command == "sde-parse": result = parse_defined_sde(root, json.loads(args.sde_json), profile=args.profile)
        elif args.command == "curate": result = curate(root, schedule_slot=args.schedule_slot, profile=args.profile)
        elif args.command == "review": result = review_candidate(root, args.record_id, args.disposition, args.priority, args.archive, confirm_priority_5=args.confirm_priority_5, edits=json.loads(args.edits_json) if args.edits_json else None, profile=args.profile)
        elif args.command == "recover": result = recover_transaction(root, args.record_id, accept_current_target=args.accept_current_target, profile=args.profile)
        elif args.command == "learning-status": result = learning_status(root, args.profile)
        elif args.command == "pending-reviews": result = pending_reviews(root, args.profile, limit=args.limit)
        elif args.command == "learning-recompute": result = learning_recompute(root, args.profile, force=args.force)
        elif args.command == "learning-report": result = learning_report(root, args.profile)
        else: result = self_improvement(root, args.failure, args.cause, args.fix, args.prevention, profile=args.profile)
        print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"written": False, "error": str(exc)}), file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
