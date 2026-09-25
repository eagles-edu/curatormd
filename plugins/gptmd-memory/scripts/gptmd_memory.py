#!/usr/bin/env python3
"""Local-first CuratorMD primitives for an explicitly scoped project."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


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
        return {str(k)[:120]: redact_payload(v, key=str(k)) for k, v in list(value.items())[:100]}
    if isinstance(value, list):
        return [redact_payload(item, key=key) for item in value[:100]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_text(str(value)[:8_000])


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_git(root: Path, *args: str, timeout: int = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False, timeout=timeout)


def resolve_project_root(project_root: str | os.PathLike[str] | None, *, allow_default: bool = False) -> Path:
    """Fail closed unless the path resolves to the Git worktree root with persistence/."""
    if project_root is None:
        if not allow_default:
            raise CuratorError("project_root is required and must be an absolute path")
        configured = os.environ.get("GPTMD_PROJECT_ROOT")
        candidate = Path(configured).expanduser() if configured else Path.cwd()
    else:
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
            data = json.loads(package.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result["package.json"]["name"] = data.get("name")
                result["package.json"]["scripts"] = sorted(str(k) for k in (data.get("scripts") or {}) if isinstance(k, str))
                result["package.json"]["dependencies"] = sorted(str(k) for k in (data.get("dependencies") or {}) if isinstance(k, str))
                result["package.json"]["devDependencies"] = sorted(str(k) for k in (data.get("devDependencies") or {}) if isinstance(k, str))
        except (OSError, json.JSONDecodeError):
            result["package.json"]["parse"] = "unavailable"
    return result


def _persistence_health(root: Path) -> dict[str, Any]:
    stores = []
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
    if not isinstance(data, dict) or data.get("project_root") != str(root):
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
                merged[key] = {**(latest.get(key) or {}), **value}
            elif key == "curator_store_hashes" and isinstance(value, dict):
                merged[key] = {**(latest.get(key) or {}), **value}
            elif key == "observer" and isinstance(value, dict):
                old = latest.get(key) or {}
                old_seen, new_seen = str(old.get("last_seen_at") or ""), str(value.get("last_seen_at") or "")
                merged[key] = dict(value if new_seen >= old_seen else old)
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
            record = json.loads(path.read_text(encoding="utf-8"))
            terminal = isinstance(record, dict) and (record.get("finalized") is True or record.get("suppressed") is True)
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
        payload = dict(payload)
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


def _append_reviewed(
    root: Path,
    kind: str,
    title: str,
    content: str,
    rationale: str,
    impact: str,
    *,
    record_id: str | None = None,
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
    for line in raw.splitlines():
        if line.startswith(marker_prefix):
            if line == f"{marker_prefix}{content_hash} -->":
                return {"written": False, "duplicate": True, "kind": kind, "file": str(path.relative_to(root)), "title": title, "record_id": record_id}
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
    updated = raw.rstrip() + "\n" + entry if raw.strip() else f"# {path.stem}\n{entry}"
    _atomic_text(path, updated)
    return {"written": True, "duplicate": False, "kind": kind, "file": str(path.relative_to(root)), "title": title, "record_id": record_id}


@contextlib.contextmanager
def curation_lock(root: Path) -> Iterator[dict[str, Any]]:
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
    records = []
    inbox = root / ".curatormd" / "native-inbox"
    if not inbox.is_dir():
        return records
    for path in sorted(inbox.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("project_root") == str(root): records.append(data)
    return records


def _record_path(root: Path, record_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", record_id):
        raise ValueError("invalid record_id")
    return _inbox_dir(root) / f"{record_id}.json"


def _candidate_for(root: Path, record: dict[str, Any], profile: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    from curation_learning import extract_features, meaningful, predict, snapshot
    has_meaning, reason = meaningful(record)
    if not has_meaning:
        return None, None, reason
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    summary = payload.get("review_safe_summary") if isinstance(payload.get("review_safe_summary"), dict) else {}
    if not isinstance(summary.get("text"), str) or not summary.get("text", "").strip():
        from curation_learning import safe_summary
        summary = safe_summary(payload)
        payload["review_safe_summary"] = summary
        record["payload"] = payload
    text = summary.get("text")
    if not isinstance(text, str) or not text.strip():
        return None, None, "safe summary unavailable"
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    proposed = predict(root, profile, record)
    probability = float(proposed.get("disposition_probability", 0.5))
    priority_probs = proposed.get("priority_probabilities", {})
    if proposed.get("priority_model_status") == "fit":
        priority = int(max(range(6), key=lambda item: float(priority_probs.get(str(item), 0.0))))
    else:
        priority = 1
    archive_probs = proposed.get("archive_probabilities", {})
    if proposed.get("archive_model_status") == "fit":
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
    title = re.sub(r"\s+", " ", title_hint).strip().rstrip(".!?")[:120] or "CuratorMD event"
    candidate = {
        "kind": archive,
        "title": title,
        "content": text.strip(),
        "utility": "Preserves the bounded result for future project work.",
        "impact": "Human review required; no archive change occurs while pending.",
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
    selection = review.get("selection", {})
    disposition = selection.get("disposition", {}).get("selected") if isinstance(selection.get("disposition"), dict) else None
    if disposition not in {"approved", "do-not-record"}:
        return None
    priority = selection.get("priority", {}).get("selected") if isinstance(selection.get("priority"), dict) else None
    archive = selection.get("archive", {}).get("selected") if isinstance(selection.get("archive"), dict) else None
    human_edits = review.get("human_edits") if isinstance(review.get("human_edits"), dict) else {}
    proposal = record.get("proposal") if isinstance(record.get("proposal"), dict) else {}
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
    from curation_learning import _json_read, _write, learning_root
    record_id = transaction["record_id"]
    candidate = transaction["candidate"]
    disposition = transaction["disposition"]
    store_hashes = state.setdefault("curator_store_hashes", {})
    archive_result = None
    if disposition == "approved":
        archive_result = _append_reviewed(
            root, transaction["archive"], candidate["title"], candidate["content"],
            candidate.get("utility", ""), candidate.get("impact", ""),
            record_id=record_id, expected_hash=store_hashes.get(transaction["archive"]),
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
        _atomic_json(record_path, current)
    state.setdefault("processed", {})[record_id] = str(transaction["fingerprint"])
    state["curator_store_hashes"] = store_hashes
    _save_state(root, state, profile)
    transaction["status"] = "committed"
    transaction["committed_at"] = iso_now()
    from curation_learning import _write, learning_root
    _write(learning_root(root, profile) / "transactions" / f"{record_id}-r{transaction['review_revision']}.json", transaction)
    return {"record_id": record_id, "disposition": disposition, "archive": archive_result, "learning": learning_result, "duplicate": bool(archive_result and archive_result.get("duplicate"))}


def _finalize_review(root: Path, profile: str | None, state: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    from curation_learning import _json_read, learning_root
    review = record.get("review") if isinstance(record.get("review"), dict) else None
    candidate = record.get("candidate") if isinstance(record.get("candidate"), dict) else None
    if not candidate:
        raise CuratorError("reviewed record has no candidate")
    if review is None:
        # Compatibility for explicitly reviewed schema-v2 candidates.
        review = {"reviewed": True, "selection": {"disposition": {"selected": "approved"}, "priority": {"selected": None}, "archive": {"selected": candidate.get("kind")}}, "finalized_at": iso_now(), "review_source": "legacy-human"}
        record["review"] = review
    selection = review.get("selection") if isinstance(review.get("selection"), dict) else {}
    disposition = selection.get("disposition", {}).get("selected") if isinstance(selection.get("disposition"), dict) else None
    if not review.get("reviewed") or disposition not in {"approved", "do-not-record"}:
        raise CuratorError("review is incomplete")
    archive = selection.get("archive", {}).get("selected") if isinstance(selection.get("archive"), dict) else None
    if disposition == "approved" and archive not in STORE_KINDS:
        raise CuratorError("approved review requires a valid archive selection")
    revision = int(record.get("review_revision", 1))
    observation = _observation_for(record, review, candidate, revision) if review.get("review_source", "human") == "human" else None
    learning_dir = learning_root(root, profile)
    journal = learning_dir / "transactions" / f"{record['record_id']}-r{revision}.json"
    prior = _json_read(journal, None)
    if isinstance(prior, dict):
        if prior.get("status") == "committed":
            return {"record_id": record["record_id"], "disposition": disposition, "duplicate": True}
        transaction = prior
    else:
        transaction = {
            "schema_version": 1, "status": "prepared", "project_root": str(root),
            "record_id": record["record_id"], "fingerprint": record.get("fingerprint", ""),
            "review_revision": revision, "review": review, "candidate": candidate,
            "disposition": disposition, "archive": archive, "observation": observation,
            "prepared_at": iso_now(),
        }
        from curation_learning import _write
        _write(journal, transaction)
    return _apply_transaction(root, profile, state, transaction)


def _recover_transactions(root: Path, profile: str | None, state: dict[str, Any]) -> list[dict[str, Any]]:
    from curation_learning import _json_read, learning_root
    pending = []
    directory = learning_root(root, profile) / "transactions"
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        transaction = _json_read(path, None)
        if not isinstance(transaction, dict) or transaction.get("project_root") != str(root) or transaction.get("status") == "committed":
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
    if isinstance(priority, bool) or not isinstance(priority, int) or priority not in range(6):
        raise ValueError("priority must be an integer from 0 through 5")
    if edits is not None and not isinstance(edits, dict):
        raise ValueError("edits must be an object")
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
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("finalized") is True:
            edits = edits or {}
            candidate = record.get("candidate")
            if not isinstance(candidate, dict): raise CuratorError("record has no generated candidate")
            if any(value is not None and value != candidate.get(key) for key, value in edits.items()):
                raise CuratorError("review revisions may correct labels only; candidate text is immutable after finalization")
            selection = (record.get("review") or {}).get("selection", {})
            previous_disposition = (selection.get("disposition") or {}).get("selected")
            previous_priority = (selection.get("priority") or {}).get("selected")
            previous_archive = (selection.get("archive") or {}).get("selected")
            if (previous_disposition, previous_priority, previous_archive) == (disposition, priority, archive):
                return {"record_id": record_id, "disposition": disposition, "reviewed": True, "duplicate": True, "review_revision": record.get("review_revision", 1)}
            previous_review = dict(record.get("review") or {})
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
        candidate = record.get("candidate")
        if not isinstance(candidate, dict): raise CuratorError("record has no generated candidate")
        review = record.get("review") if isinstance(record.get("review"), dict) else {}
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
        written, rejected, ambiguous, suppressed, duplicates, conflicts, recovered = [], [], [], [], [], [], []
        recovered.extend(_recover_transactions(root, profile, state))
        records = _load_inbox(root)
        for record in records:
            record_id = str(record.get("record_id") or "")
            fingerprint = str(record.get("fingerprint") or "")
            if not record_id or not fingerprint: continue
            if record.get("finalized") is True:
                duplicates.append(record_id)
                continue
            if record.get("reviewed") is not True or not isinstance(record.get("candidate"), dict):
                if not isinstance(record.get("candidate"), dict):
                    candidate, generated, reason = _candidate_for(root, record, profile)
                    if candidate is None:
                        record["suppressed"] = reason == "routine lifecycle event"
                        if record["suppressed"]: suppressed.append({"record_id": record_id, "reason": reason})
                        else: ambiguous.append({"record_id": record_id, "reason": reason})
                        if record["suppressed"]: _atomic_json(_record_path(root, record_id), record)
                        continue
                    record["candidate"], record["proposal"], record["review"], record["proposal_timestamp"] = candidate, generated["proposal"], generated["review"], iso_now()
                    record["prediction_snapshot"] = generated["prediction_snapshot"]
                    _atomic_json(_record_path(root, record_id), record)
                ambiguous.append({"record_id": record_id, "candidate": record.get("candidate", {}).get("title"), "reason": "awaiting human review"})
                continue
            try:
                result = _finalize_review(root, profile, state, record)
            except (CuratorError, ValueError, OSError) as exc:
                conflicts.append(f"{record_id}: {exc}")
                continue
            if result.get("disposition") == "approved": written.append(result)
            else: rejected.append(result)
            processed[record_id] = fingerprint
        inbox_cursor = [str(item.get("cursor")) for item in records if item.get("cursor")]
        state["processed"] = dict(list(processed.items())[-10_000:])
        state["cursor"] = max(inbox_cursor, default=state.get("cursor"))
        state["last_run_finished_at"] = iso_now()
        state["lock"] = None
        state["capture_status"] = "healthy" if (state.get("observer") or {}).get("last_seen_at") else "degraded"
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
            "ambiguous": ambiguous, "suppressed": suppressed, "duplicates": duplicates,
            "conflicts": conflicts, "recovered": recovered, "expired_inbox_records": removed,
            "learning": learning, "retention": retention, "state": str(_state_path(root, profile)),
            "lock": "released",
        }


def search(root: Path, query: str, scope: str = "all", limit: int = 40) -> dict[str, Any]:
    query = clean(query, "query", 500)
    terms = [term.lower() for term in re.findall(r"\S+", query)]
    if not terms: raise ValueError("query must contain at least one search term")
    paths = store_paths(root)
    selected = paths if scope == "all" else {scope: paths.get(scope)}
    if scope != "all" and selected[scope] is None: raise ValueError(f"unknown scope: {scope}")
    matches = []
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
    observer = state.get("observer") or {}
    capture_status = "healthy" if observer.get("status") == "healthy" else state.get("capture_status", "degraded")
    records = _load_inbox(root)
    pending = sum(record.get("finalized") is not True and record.get("suppressed") is not True for record in records)
    return {"root": str(root), "stores": _persistence_health(root)["stores"], "git": _git_state(root), "inbox_records": len(records), "pending_reviews": pending, "capture_status": capture_status, "learning": learning_status_impl(root, profile), "state": str(_state_path(root, profile)), "schedule_slot": state.get("schedule_slot")}


def append_entry(root: Path, kind: str, title: str, content: str, rationale: str | None = None, impact: str | None = None, *, profile: str | None = None) -> dict[str, Any]:
    with curation_lock(root):
        state = _load_state(root, profile)
        result = _append_reviewed(root, kind, title, content, rationale or "", impact or "", expected_hash=(state.get("curator_store_hashes") or {}).get(kind))
        if result.get("written"):
            path = store_paths(root)[kind]
            state.setdefault("curator_store_hashes", {})[kind] = sha256_text(path.read_text(encoding="utf-8"))
            _save_state(root, state, profile)
        return result


def learning_status(root: Path, profile: str | None = None) -> dict[str, Any]:
    from curation_learning import status as learning_status_impl
    return learning_status_impl(root, profile)


def _safe_review_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("candidate_type") != "significant_development_event":
        return None
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
        "cue_categories": categories,
        "matched_vocabulary": terms,
    }


def pending_reviews(root: Path, profile: str | None = None, *, limit: int = 30) -> dict[str, Any]:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
        raise ValueError("limit must be an integer from 1 through 100")
    items = []
    for record in _load_inbox(root):
        if record.get("finalized") is True or record.get("suppressed") is True:
            continue
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        candidate = record.get("candidate") if isinstance(record.get("candidate"), dict) else None
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
    from curation_learning import _json_read, learning_root, record_qa_outcome
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
    observation = _json_read(observation_path, {})
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
            finalized = set(current.get("qa_finalized_windows", []))
            finalized.add(window_days)
            current["qa_finalized_windows"] = sorted(finalized)
            current["qa_windows_finalized"] = all(item in finalized for item in (30, 60, 90, 180))
        observation = update_observation(root, profile, observation_path, finalize_qa)
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
    from curation_learning import _json_read, learning_root, record_retrospective
    if still_correct not in {"yes", "no", "uncertain"}:
        raise ValueError("still_correct must be yes, no, or uncertain")
    if isinstance(usefulness, bool) or not isinstance(usefulness, int) or usefulness not in range(5):
        raise ValueError("usefulness must be an integer from 0 through 4")
    if germane not in {"yes", "superseded", "obsolete", "uncertain"}:
        raise ValueError("germane must be yes, superseded, obsolete, or uncertain")
    if should_have_recorded is not None and should_have_recorded not in {"yes", "no", "uncertain"}:
        raise ValueError("should_have_recorded must be yes, no, or uncertain")
    directory = learning_root(root, profile) / "observations"
    matches = sorted(directory.glob(f"{record_id}-r*.json")) if directory.exists() else []
    if not matches: raise CuratorError("learning observation was not found")
    observation_path = matches[-1]
    observation = _json_read(observation_path, {})
    existing_reviews = sorted((learning_root(root, profile) / "retrospective-audits").glob(f"{record_id}-r*.json"))
    if existing_reviews:
        previous = _json_read(existing_reviews[-1], {})
        same = (previous.get("still_correct"), previous.get("usefulness"), previous.get("germane"), previous.get("should_have_recorded")) == (still_correct, usefulness, germane, should_have_recorded)
        if same:
            return {"written": False, "duplicate": True, "record_id": record_id, "review_revision": previous.get("review_revision")}
    revision = len(existing_reviews) + 1
    review = {"schema_version": 1, "record_id": record_id, "review_revision": revision, "reviewed_at": iso_now(), "still_correct": still_correct, "usefulness": usefulness, "germane": germane, "should_have_recorded": should_have_recorded}
    result = record_retrospective(root, profile, record_id, review)
    from curation_learning import update_observation
    observation = update_observation(root, profile, observation_path, lambda current: current.update({"retrospective_finalized": True}))
    return result


def self_improvement(root: Path, failure: str, cause: str, fix: str, prevention: str, *, profile: str | None = None) -> dict[str, Any]:
    failure, cause, fix, prevention = clean(failure, "failure", 2_000), clean(cause, "cause", 2_000), clean(fix, "fix", 4_000), clean(prevention, "prevention", 2_000)
    return append_entry(root, "lessons", f"Verified fix: {failure[:120]}", f"{fix}\n\n**Evidence:** The failure was reproduced or observed, and the fix was verified.", rationale=f"{failure}\n\n{cause}", impact=prevention, profile=profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", help="Absolute Git worktree root")
    parser.add_argument("--profile", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status"); sub.add_parser("snapshot")
    search_parser = sub.add_parser("search"); search_parser.add_argument("query"); search_parser.add_argument("--scope", default="all", choices=["all", *STORE_NAMES])
    record_parser = sub.add_parser("record"); record_parser.add_argument("kind", choices=STORE_NAMES); record_parser.add_argument("title"); record_parser.add_argument("content"); record_parser.add_argument("--rationale"); record_parser.add_argument("--impact")
    observe_parser = sub.add_parser("observe"); observe_parser.add_argument("source_id"); observe_parser.add_argument("event_type"); observe_parser.add_argument("payload_json"); observe_parser.add_argument("--cursor")
    curate_parser = sub.add_parser("curate"); curate_parser.add_argument("--schedule-slot", default="06:00 Asia/Ho_Chi_Minh")
    review_parser = sub.add_parser("review"); review_parser.add_argument("record_id"); review_parser.add_argument("disposition", choices=["approved", "do-not-record"]); review_parser.add_argument("--priority", required=True, type=int, choices=range(6)); review_parser.add_argument("--archive", choices=STORE_NAMES); review_parser.add_argument("--confirm-priority-5", action="store_true"); review_parser.add_argument("--edits-json")
    learning_status_parser = sub.add_parser("learning-status")
    pending_parser = sub.add_parser("pending-reviews"); pending_parser.add_argument("--limit", type=int, default=30)
    learning_recompute_parser = sub.add_parser("learning-recompute"); learning_recompute_parser.add_argument("--force", action="store_true")
    sub.add_parser("learning-report")
    improve_parser = sub.add_parser("improve"); improve_parser.add_argument("failure"); improve_parser.add_argument("cause"); improve_parser.add_argument("fix"); improve_parser.add_argument("prevention")
    args = parser.parse_args()
    try:
        root = resolve_project_root(args.project_root, allow_default=True)
        if args.command == "status": result = status(root, args.profile)
        elif args.command == "snapshot": result = environment_snapshot(str(root))
        elif args.command == "search": result = search(root, args.query, args.scope)
        elif args.command == "record": result = append_entry(root, args.kind, args.title, args.content, args.rationale, args.impact, profile=args.profile)
        elif args.command == "observe": result = native_projection_record(root, args.source_id, args.event_type, json.loads(args.payload_json), args.cursor, args.profile)
        elif args.command == "curate": result = curate(root, schedule_slot=args.schedule_slot, profile=args.profile)
        elif args.command == "review": result = review_candidate(root, args.record_id, args.disposition, args.priority, args.archive, confirm_priority_5=args.confirm_priority_5, edits=json.loads(args.edits_json) if args.edits_json else None, profile=args.profile)
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
