#!/usr/bin/env python3
"""Bounded learning, review, and QA state for CuratorMD.

All files live in the existing profile-and-project-scoped plugin state.  The
module uses only the Python standard library so deployments stay portable.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import fcntl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

SCHEMA_VERSION = 1
ACTIVE_WINDOW_DAYS = 183
RETENTION_DAYS = 274
RECOMPUTE_DAYS = 21
MIN_MODEL_ROWS = 12
MAX_TRAINING_ROWS = 2500
CATEGORY_FIELDS = (
    "event_type", "provider", "profile", "model", "platform", "scope",
    "activity_class", "status", "result_class", "failure_class",
)
BOOLEAN_FIELDS = (
    "changed_project", "decision_made", "configuration_changed",
    "dependency_changed", "interface_changed", "architecture_changed",
    "documentation_changed", "security_changed", "data_changed",
    "tests_executed", "safe_summary_available",
)
COUNT_FIELDS = ("tests_passed", "tests_failed", "tests_skipped", "files_changed_count", "error_count", "tool_count")
ARCHIVES = ("agents", "sop", "history", "lessons")
DISPOSITIONS = ("pending", "approved", "do-not-record")
PRIORITIES = (0, 1, 2, 3, 4, 5)


def _as_object(value: Any) -> dict[str, Any]:
    """Give decoded JSON objects a useful type after the runtime shape check."""
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def learning_root(root: Path, profile: str | None = None) -> Path:
    from gptmd_memory import plugin_data_root
    return plugin_data_root(root, profile) / "learning"


def _json_read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError) as exc:
        from gptmd_memory import CuratorError
        raise CuratorError(f"learning data is unreadable: {path.name}") from exc


def _write(path: Path, value: Any) -> None:
    from gptmd_memory import atomic_json
    atomic_json(path, value)


def _record_path(root: Path, profile: str | None, collection: str, record_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", record_id)[:180]
    path = learning_root(root, profile) / collection / f"{safe_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    return path


def update_observation(root: Path, profile: str | None, path: Path, update: Any) -> dict[str, Any]:
    """Apply a small observation update under a profile/project scoped lock."""
    lock_dir = learning_root(root, profile) / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = lock_dir / "observations.lock"
    with lock_path.open("a+") as handle:
        os.chmod(lock_path, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        observation = _json_read(path, None)
        if not isinstance(observation, dict):
            from gptmd_memory import CuratorError
            raise CuratorError("learning observation disappeared during update")
        update(observation)
        _write(path, observation)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return cast(dict[str, Any], observation)


def _bounded_text(value: Any, limit: int = 1200) -> str:
    from gptmd_memory import redact_text
    if not isinstance(value, str):
        return ""
    value = redact_text(value).replace("\x00", " ").strip()
    return value[:limit].strip()


def safe_summary(payload: Any) -> dict[str, Any]:
    """Build a bounded local summary before generic payload redaction."""
    from gptmd_memory import redact_text
    if not isinstance(payload, dict):
        return {"text": None, "status": "unavailable", "bounded": True, "sanitized": True, "generator": "local"}
    payload = cast(dict[str, Any], payload)
    supplied = _as_object(payload.get("review_safe_summary"))
    text = _bounded_text(supplied.get("text"))
    if text:
        return {"text": text, "status": "generated", "bounded": True, "sanitized": True, "generator": str(supplied.get("generator") or "producer")[:80]}
    result = _as_object(payload.get("result"))
    facts: list[str] = []
    activity = result.get("activity_class")
    status = result.get("status")
    result_class = result.get("result_class")
    if isinstance(activity, str): facts.append(activity.replace("_", " "))
    if isinstance(result_class, str): facts.append(result_class.replace("_", " "))
    if isinstance(status, str): facts.append(status)
    tests = _as_object(result.get("tests"))
    failed = tests.get("failed")
    passed = tests.get("passed")
    if isinstance(failed, int) and failed > 0: facts.append(f"{failed} test(s) failed")
    elif isinstance(passed, int) and passed > 0: facts.append(f"{passed} test(s) passed")
    changes: list[str] = []
    for field, label in (("architecture_changed", "architecture"), ("configuration_changed", "configuration"), ("dependency_changed", "dependencies"), ("interface_changed", "interface"), ("security_changed", "security"), ("data_changed", "data"), ("documentation_changed", "documentation")):
        if result.get(field) is True: changes.append(label)
    if changes: facts.append("changed " + ", ".join(changes))
    if result.get("decision_made") is True: facts.append("recorded a project decision")
    text = _bounded_text("; ".join(facts))
    if text:
        return {"text": text, "status": "generated", "bounded": True, "sanitized": True, "generator": "local-structured"}
    response = payload.get("response")
    if isinstance(response, str) and response.strip() and response.strip() != "[REDACTED]":
        # Keep one bounded sentence only; do not preserve logs or fenced code.
        response = re.sub(r"```.*?```", " ", response, flags=re.S)
        response = re.sub(r"https?://\S+", "[URL]", response)
        response = re.sub(r"\s+", " ", redact_text(response)).strip()
        sentence = re.split(r"(?<=[.!?])\s+", response, maxsplit=1)[0]
        text = _bounded_text(sentence)
        if text:
            return {"text": text, "status": "generated", "bounded": True, "sanitized": True, "generator": "local-extract"}
    return {"text": None, "status": "unavailable", "bounded": True, "sanitized": True, "generator": "local"}


def extract_features(record: dict[str, Any]) -> dict[str, Any]:
    from gptmd_memory import redact_payload
    raw_payload = record.get("payload")
    payload = _as_object(raw_payload)
    result = _as_object(payload.get("result"))
    summary = _as_object(payload.get("review_safe_summary"))
    tests = _as_object(result.get("tests"))
    features: dict[str, Any] = {
        "event_type": str(record.get("event_type") or payload.get("event") or "unknown"),
        "provider": payload.get("provider", "unknown"),
        "profile": payload.get("profile", "unknown"),
        "model": payload.get("model", "unknown"),
        "platform": payload.get("platform", "unknown"),
        "scope": payload.get("scope", "unknown"),
        "activity_class": result.get("activity_class", "unknown"),
        "status": result.get("status", "unknown"),
        "result_class": result.get("result_class", "unknown"),
        "failure_class": result.get("failure_class", "unknown"),
        "changed_project": result.get("changed_project", False),
        "decision_made": result.get("decision_made", False),
        "configuration_changed": result.get("configuration_changed", False),
        "dependency_changed": result.get("dependency_changed", False),
        "interface_changed": result.get("interface_changed", False),
        "architecture_changed": result.get("architecture_changed", False),
        "documentation_changed": result.get("documentation_changed", False),
        "security_changed": result.get("security_changed", False),
        "data_changed": result.get("data_changed", False),
        "tests_executed": tests.get("executed", False),
        "tests_passed": tests.get("passed", 0),
        "tests_failed": tests.get("failed", 0),
        "tests_skipped": tests.get("skipped", 0),
        "files_changed_count": result.get("files_changed_count", 0),
        "error_count": result.get("error_count", 0),
        "tool_count": len(payload.get("tool_names", [])) if isinstance(payload.get("tool_names"), list) else 0,
        "safe_summary_available": bool(summary.get("text")),
    }
    return _as_object(redact_payload(features))


def meaningful(record: dict[str, Any]) -> tuple[bool, str]:
    """Return whether a captured event has enough bounded evidence to propose."""
    event = str(record.get("event_type") or "")
    if event in {"agent:start", "agent:step"}:
        return False, "routine lifecycle event"
    payload = _as_object(record.get("payload"))
    result = _as_object(payload.get("result"))
    if any(result.get(key) is True for key in (
        "changed_project", "decision_made", "configuration_changed",
        "dependency_changed", "interface_changed", "architecture_changed",
        "documentation_changed", "security_changed", "data_changed",
    )):
        return True, "project change or decision reported"
    tests = _as_object(result.get("tests"))
    failed = tests.get("failed")
    if result.get("status") in {"failure", "partial", "blocked"} or (
        isinstance(failed, int) and failed > 0
    ):
        return True, "failure or incomplete result reported"
    summary = _as_object(payload.get("review_safe_summary"))
    summary_text = summary.get("text")
    if isinstance(summary_text, str) and summary_text.strip():
        return True, "bounded semantic summary available"
    fallback_summary = safe_summary(payload)
    fallback_text = fallback_summary.get("text")
    if isinstance(fallback_text, str) and fallback_text.strip():
        return True, "bounded fallback summary available"
    return False, "routine or insufficient evidence"


def _vector(features: dict[str, Any], vocabulary: list[str]) -> list[float]:
    index = {name: i for i, name in enumerate(vocabulary)}
    values = [0.0] * len(vocabulary)
    for field in CATEGORY_FIELDS:
        key = f"{field}={features.get(field, 'unknown')}"
        values[index.get(key, index.get(f"{field}=__OTHER__", 0))] = 1.0
    for field in BOOLEAN_FIELDS:
        values[index.get(f"{field}=true" if features.get(field) is True else f"{field}=false", 0)] = 1.0
    for field in COUNT_FIELDS:
        try: count = max(0.0, float(features.get(field, 0) or 0))
        except (TypeError, ValueError): count = 0.0
        values[index.get(f"{field}=log1p", 0)] = math.log1p(count)
    return values


def _vocabulary(rows: list[dict[str, Any]]) -> list[str]:
    values = {"__INTERCEPT__"}
    for field in CATEGORY_FIELDS:
        found = {str(row.get(field) or "unknown") for row in rows}
        values.update(f"{field}={value}" for value in found)
        values.add(f"{field}=__OTHER__")
    for field in BOOLEAN_FIELDS:
        values.update((f"{field}=true", f"{field}=false"))
    values.update(f"{field}=log1p" for field in COUNT_FIELDS)
    return sorted(values)


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-min(value, 35.0))
        return 1.0 / (1.0 + z)
    z = math.exp(max(value, -35.0))
    return z / (1.0 + z)


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _fit_binary(rows: list[dict[str, Any]], vectors: list[list[float]], target: str) -> dict[str, Any]:
    labels = [1.0 if row.get(target) == "approved" else 0.0 for row in rows]
    positives = sum(labels)
    n = len(labels)
    prior = (positives + 1.0) / (n + 2.0)
    if n < MIN_MODEL_ROWS or positives in {0.0, float(n)}:
        return {"status": "insufficient_support", "prior": prior, "positive": int(positives), "n": n}
    width = len(vectors[0])
    beta = [0.0] * width
    intercept_idx = 0
    beta[intercept_idx] = math.log(prior / (1.0 - prior))
    learning_rate, ridge = 0.12, 0.8
    for _ in range(320):
        grad = [0.0] * width
        for vector, label in zip(vectors, labels):
            x = [1.0, *vector[1:]]
            p = _sigmoid(_dot(beta, x))
            err = p - label
            for j, value in enumerate(x): grad[j] += err * value / n
        for j in range(1, width): grad[j] += ridge * beta[j] / n
        change = 0.0
        for j in range(width):
            step = learning_rate * grad[j]
            beta[j] -= step
            change = max(change, abs(step))
        if change < 1e-7: break
    return {"status": "fit", "prior": prior, "positive": int(positives), "n": n, "coefficients": beta, "ridge": ridge}


def _fit_softmax(rows: list[dict[str, Any]], vectors: list[list[float]], target: str, classes: list[str]) -> dict[str, Any]:
    labels = [str(row.get(target)) for row in rows]
    counts = {kind: labels.count(kind) for kind in classes}
    n = len(labels)
    priors = {kind: (counts[kind] + 1.0) / (n + len(classes)) for kind in classes}
    if n < MIN_MODEL_ROWS or sum(value > 0 for value in counts.values()) < 2:
        return {"status": "insufficient_support", "priors": priors, "counts": counts, "n": n}
    width = len(vectors[0])
    weights = [[0.0] * width for _ in classes]
    for i, kind in enumerate(classes): weights[i][0] = math.log(priors[kind])
    learning_rate, ridge = 0.08, 0.9
    for _ in range(360):
        grads = [[0.0] * width for _ in classes]
        for vector, label in zip(vectors, labels):
            x = [1.0, *vector[1:]]
            logits = [_dot(weight, x) for weight in weights]
            peak = max(logits)
            exps = [math.exp(max(-50.0, score - peak)) for score in logits]
            denom = sum(exps) or 1.0
            probs = [value / denom for value in exps]
            for i, kind in enumerate(classes):
                err = probs[i] - (1.0 if kind == label else 0.0)
                for j, value in enumerate(x): grads[i][j] += err * value / n
        largest = 0.0
        for i in range(len(classes)):
            for j in range(width):
                if j: grads[i][j] += ridge * weights[i][j] / n
                step = learning_rate * grads[i][j]
                weights[i][j] -= step
                largest = max(largest, abs(step))
        if largest < 1e-7: break
    return {"status": "fit", "priors": priors, "counts": counts, "n": n, "classes": classes, "coefficients": weights, "ridge": ridge}


def _fit_ordinal(rows: list[dict[str, Any]], vectors: list[list[float]]) -> dict[str, Any]:
    labels = [int(row.get("priority", 0)) for row in rows]
    counts = {str(value): labels.count(value) for value in PRIORITIES}
    n = len(rows)
    priors = {str(value): (counts[str(value)] + 1.0) / (n + len(PRIORITIES)) for value in PRIORITIES}
    if n < MIN_MODEL_ROWS or len(set(labels)) < 2:
        return {"status": "insufficient_support", "priors": priors, "counts": counts, "n": n}
    width = len(vectors[0])
    beta = [0.0] * width
    cumulative: list[float] = []
    for k in range(5):
        rate = (sum(label <= k for label in labels) + 1.0) / (n + 2.0)
        cumulative.append(math.log(rate / (1.0 - rate)))
    # Monotone threshold parameterization: theta[k] = theta[k-1] + exp(delta[k]).
    theta0 = cumulative[0]
    deltas = [math.log(max(0.02, cumulative[k] - cumulative[k - 1])) for k in range(1, 5)]
    rate, ridge = 0.025, 0.6
    for _ in range(700):
        theta = [theta0]
        for delta in deltas: theta.append(theta[-1] + math.exp(max(-5.0, min(5.0, delta))))
        gt = [0.0] * 5
        gb = [0.0] * width
        for label, vector in zip(labels, vectors):
            x = [0.0, *vector[1:]]
            shift = _dot(beta, x)
            fy = _sigmoid(theta[label] - shift) if label < 5 else 1.0
            fp = _sigmoid(theta[label - 1] - shift) if label > 0 else 0.0
            prob = max(1e-10, fy - fp)
            sy = fy * (1.0 - fy) if label < 5 else 0.0
            sp = fp * (1.0 - fp) if label > 0 else 0.0
            if label < 5: gt[label] -= sy / prob
            if label > 0: gt[label - 1] += sp / prob
            for j, value in enumerate(x): gb[j] += (sy - sp) * value / prob
        for j in range(1, width): gb[j] = gb[j] / n + ridge * beta[j] / n
        gb[0] = 0.0
        gt = [value / n for value in gt]
        g0 = sum(gt)
        gd = [sum(gt[k] for k in range(i + 1, 5)) * math.exp(max(-5.0, min(5.0, deltas[i]))) for i in range(4)]
        largest = abs(rate * g0)
        theta0 -= rate * g0
        for i in range(4):
            step = rate * gd[i]
            deltas[i] -= step
            largest = max(largest, abs(step))
        for j in range(width):
            step = rate * gb[j]
            beta[j] -= step
            largest = max(largest, abs(step))
        if largest < 2e-6: break
    return {"status": "fit", "n": n, "counts": counts, "priors": priors, "theta0": theta0, "deltas": deltas, "coefficients": beta, "ridge": ridge, "iterations": 700}


def _predict_binary(model: dict[str, Any], vector: list[float]) -> float:
    if model.get("status") != "fit": return float(model.get("prior", 0.5))
    return _sigmoid(_dot(model["coefficients"], [1.0, *vector[1:]]))


def _predict_softmax(model: dict[str, Any], vector: list[float]) -> dict[str, float]:
    if model.get("status") != "fit": return dict(model.get("priors", {}))
    x = [1.0, *vector[1:]]
    scores = [_dot(weight, x) for weight in model["coefficients"]]
    peak = max(scores)
    values = [math.exp(max(-50.0, item - peak)) for item in scores]
    total = sum(values) or 1.0
    return {kind: value / total for kind, value in zip(model["classes"], values)}


def _predict_ordinal(model: dict[str, Any], vector: list[float]) -> dict[str, float]:
    if model.get("status") != "fit": return dict(model.get("priors", {}))
    theta = [model["theta0"]]
    for delta in model["deltas"]: theta.append(theta[-1] + math.exp(max(-5.0, min(5.0, delta))))
    shift = _dot(model["coefficients"], [0.0, *vector[1:]])
    cumulative = [_sigmoid(value - shift) for value in theta]
    values = {"0": cumulative[0]}
    for k in range(1, 5): values[str(k)] = max(0.0, cumulative[k] - cumulative[k - 1])
    values["5"] = max(0.0, 1.0 - cumulative[4])
    total = sum(values.values()) or 1.0
    return {kind: value / total for kind, value in values.items()}


def predict(root: Path, profile: str | None, record: dict[str, Any]) -> dict[str, Any]:
    directory = learning_root(root, profile) / "models"
    bundle = _json_read(directory / "latest.json", {})
    features = extract_features(record)
    vocabulary = bundle.get("feature_vocabulary", [])
    if not vocabulary:
        return {"disposition_probability": 0.5, "priority_probabilities": {str(i): 1.0 / 6.0 for i in PRIORITIES}, "archive_probabilities": {name: 0.25 for name in ARCHIVES}, "model_version": "prior-only", "approval_model_status": "insufficient_support", "priority_model_status": "insufficient_support", "archive_model_status": "insufficient_support", "features": features}
    vector = _vector(features, vocabulary)
    approval = _predict_binary(bundle.get("approval_model", {}), vector)
    priority = _predict_ordinal(bundle.get("priority_model", {}), vector)
    archive = _predict_softmax(bundle.get("archive_model", {}), vector)
    return {"disposition_probability": approval, "priority_probabilities": priority, "archive_probabilities": archive, "model_version": bundle.get("model_version", "unknown"), "approval_model_status": bundle.get("approval_model", {}).get("status", "unknown"), "priority_model_status": bundle.get("priority_model", {}).get("status", "unknown"), "archive_model_status": bundle.get("archive_model", {}).get("status", "unknown"), "features": features}


def snapshot(root: Path, profile: str | None, record: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    path = _record_path(root, profile, "predictions", str(record["record_id"]))
    prior = _json_read(path, None)
    if isinstance(prior, dict):
        return _as_object(prior)
    prediction = predict(root, profile, record)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_id": record["record_id"],
        "revision": 1,
        "predicted_at": now,
        "feature_extractor_version": "1",
        "features": prediction.pop("features"),
        "prediction": prediction,
        "proposal": proposal,
        "automation": {"enabled": False, "phase": "phase-1-human-only"},
    }
    _write(path, snapshot)
    return snapshot


def _active_rows(root: Path, profile: str | None, now: datetime) -> list[dict[str, Any]]:
    directory = learning_root(root, profile) / "observations"
    rows: list[dict[str, Any]] = []
    cutoff = now - timedelta(days=ACTIVE_WINDOW_DAYS)
    paths: list[Path] = sorted(directory.glob("*.json")) if directory.exists() else []
    for path in paths:
        row_value = _json_read(path, None)
        if not isinstance(row_value, dict):
            continue
        row = _as_object(row_value)
        if (row.get("active", True) is not True
                or row.get("review_source") != "human" or row.get("analysis_eligible") is not True): continue
        try: reviewed = datetime.fromisoformat(str(row.get("review_timestamp", "")).replace("Z", "+00:00"))
        except ValueError: continue
        if reviewed >= cutoff and row.get("review_source") == "human": rows.append(row)
    rows.sort(key=lambda item: (item.get("review_timestamp", ""), item.get("record_id", "")))
    if len(rows) > MAX_TRAINING_ROWS:
        rows = rows[-MAX_TRAINING_ROWS:]
    return rows


def _metrics(root: Path, profile: str | None, rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("record_id")): row for row in rows}
    scored: list[tuple[dict[str, Any], dict[str, Any]]] = []
    prediction_dir = learning_root(root, profile) / "predictions"
    prediction_paths: list[Path] = sorted(prediction_dir.glob("*.json")) if prediction_dir.exists() else []
    for path in prediction_paths:
        pred_value = _json_read(path, None)
        if not isinstance(pred_value, dict):
            continue
        pred = _as_object(pred_value)
        row = by_id.get(str(pred.get("record_id")))
        if row and pred.get("predicted_at", "") < row.get("review_timestamp", ""):
            scored.append((pred, row))
    n = len(scored)
    approval_loss = approval_brier = 0.0
    priority_error = priority_signed = priority_exact = priority_within_one = 0.0
    tp = fp = tn = fn = 0
    archive_correct = archive_n = 0
    archive_loss = 0.0
    calibration_bins: list[dict[str, Any]] = [{"n": 0, "predicted_sum": 0.0, "observed_sum": 0} for _ in range(5)]
    disposition_corrections = priority_corrections = archive_corrections = text_corrections = 0
    for pred, row in scored:
        p = min(1.0 - 1e-12, max(1e-12, float(pred.get("prediction", {}).get("disposition_probability", 0.5))))
        y = 1.0 if row.get("disposition") == "approved" else 0.0
        approval_loss += -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))
        approval_brier += (p - y) ** 2
        predicted_approved = p >= 0.5
        tp += predicted_approved and y == 1.0
        fp += predicted_approved and y == 0.0
        tn += (not predicted_approved) and y == 0.0
        fn += (not predicted_approved) and y == 1.0
        bin_index = min(4, int(p * 5))
        calibration_bins[bin_index]["n"] += 1
        calibration_bins[bin_index]["predicted_sum"] += p
        calibration_bins[bin_index]["observed_sum"] += int(y)
        pp = pred.get("prediction", {}).get("priority_probabilities", {})
        predicted_priority = max(PRIORITIES, key=lambda k: (float(pp.get(str(k), 0.0)), -k))
        human_priority = int(row.get("priority", 0))
        error = predicted_priority - human_priority
        priority_error += abs(error)
        priority_signed += error
        priority_exact += predicted_priority == human_priority
        priority_within_one += abs(error) <= 1
        corrections = row.get("corrections", {})
        disposition_corrections += corrections.get("disposition_changed") is True
        priority_corrections += corrections.get("priority_changed") is True
        text_corrections += corrections.get("text_changed") is True
        if row.get("disposition") == "approved" and row.get("archive") in ARCHIVES:
            ap = pred.get("prediction", {}).get("archive_probabilities", {})
            predicted_archive = max(ARCHIVES, key=lambda k: float(ap.get(k, 0.0)))
            archive_correct += predicted_archive == row.get("archive")
            archive_n += 1
            archive_probability = min(1.0 - 1e-12, max(1e-12, float(ap.get(row.get("archive"), 0.0))))
            archive_loss -= math.log(archive_probability)
            archive_corrections += corrections.get("archive_changed") is True
    calibration: list[dict[str, Any]] = []
    for index, item in enumerate(calibration_bins):
        if item["n"]:
            calibration.append({"bin": f"{index * 0.2:.1f}-{(index + 1) * 0.2:.1f}", "n": item["n"], "mean_predicted": item["predicted_sum"] / item["n"], "observed_rate": item["observed_sum"] / item["n"]})
    return {
        "prospective_prediction_count": n,
        "approval_log_loss": approval_loss / n if n else None,
        "approval_brier_score": approval_brier / n if n else None,
        "approval_accuracy": (tp + tn) / n if n else None,
        "approval_precision": tp / (tp + fp) if tp + fp else None,
        "approval_recall": tp / (tp + fn) if tp + fn else None,
        "approval_false_rejection_rate": fn / (tp + fn) if tp + fn else None,
        "calibration_bins": calibration,
        "priority_exact_agreement": priority_exact / n if n else None,
        "priority_within_one_agreement": priority_within_one / n if n else None,
        "priority_mae": priority_error / n if n else None,
        "priority_signed_bias": priority_signed / n if n else None,
        "disposition_correction_rate": disposition_corrections / n if n else None,
        "priority_correction_rate": priority_corrections / n if n else None,
        "text_correction_rate": text_corrections / n if n else None,
        "archive_sample_count": archive_n,
        "archive_accuracy": archive_correct / archive_n if archive_n else None,
        "archive_log_loss": archive_loss / archive_n if archive_n else None,
        "archive_correction_rate": archive_corrections / archive_n if archive_n else None,
    }


def _qa_summary(root: Path, profile: str | None) -> dict[str, Any]:
    directory = learning_root(root, profile) / "qa-outcomes"
    counts: dict[str, dict[str, int]] = {}
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        item = _json_read(path, {})
        key = f"{item.get('outcome_type', 'unknown')}@{item.get('window_days', 'unknown')}d"
        value = str(item.get("value"))
        counts.setdefault(key, {})[value] = counts.setdefault(key, {}).get(value, 0) + 1
    retrospectives = learning_root(root, profile) / "retrospective-audits"
    reviews = [_json_read(path, {}) for path in sorted(retrospectives.glob("*.json"))] if retrospectives.exists() else []
    usefulness = [item.get("usefulness") for item in reviews if isinstance(item.get("usefulness"), int)]
    return {"outcomes_by_type_and_window": counts, "retrospective_review_count": len(reviews), "mean_retrospective_usefulness": sum(usefulness) / len(usefulness) if usefulness else None}


def recompute(root: Path, profile: str | None = None, *, force: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    directory = learning_root(root, profile)
    model_dir = directory / "models"
    model_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    latest_path = model_dir / "latest.json"
    latest = _as_object(_json_read(latest_path, {}))
    if not force and latest.get("trained_at"):
        try:
            last = datetime.fromisoformat(str(latest["trained_at"]).replace("Z", "+00:00"))
            if now - last < timedelta(days=RECOMPUTE_DAYS):
                return {"recomputed": False, "reason": "not_due", "trained_at": latest["trained_at"], "next_due_at": (last + timedelta(days=RECOMPUTE_DAYS)).isoformat().replace("+00:00", "Z")}
        except ValueError: pass
    rows = _active_rows(root, profile, now)
    features = [item.get("features", {}) for item in rows]
    vocabulary = _vocabulary(features)
    vectors = [_vector(item, vocabulary) for item in features]
    approval_rows: list[dict[str, Any]] = [{**item, "approved_target": item.get("disposition")} for item in rows]
    priority_rows: list[dict[str, Any]] = [{**item, "priority_target": str(item.get("priority", 0))} for item in rows]
    archive_rows: list[dict[str, Any]] = [{**item, "archive_target": item.get("archive")} for item in rows if item.get("disposition") == "approved" and item.get("archive") in ARCHIVES]
    index = {str(item.get("record_id")): i for i, item in enumerate(rows)}
    approval_model = _fit_binary(approval_rows, vectors, "approved_target")
    priority_model = _fit_ordinal(priority_rows, vectors)
    archive_vectors = [vectors[index[str(item["record_id"])]] for item in archive_rows]
    archive_model = _fit_softmax(archive_rows, archive_vectors, "archive_target", list(ARCHIVES))
    version_source = json.dumps({"trained_at": now.isoformat(), "ids": [item.get("record_id") for item in rows], "vocabulary": vocabulary}, sort_keys=True)
    version = hashlib.sha256(version_source.encode()).hexdigest()[:16]
    bundle: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "model_version": version,
        "trained_at": now.isoformat().replace("+00:00", "Z"),
        "window_start": (now - timedelta(days=ACTIVE_WINDOW_DAYS)).date().isoformat(),
        "window_end": now.date().isoformat(),
        "observation_count": len(rows),
        "feature_extractor_version": "1",
        "feature_vocabulary": vocabulary,
        "approval_model": approval_model,
        "priority_model": priority_model,
        "archive_model": archive_model,
        "automation_eligibility": {"eligible": False, "reason": "automation remains disabled until prospective evidence gates are implemented and explicitly enabled"},
        "automation_enabled": False,
    }
    metrics = _metrics(root, profile, rows)
    inbox = root / ".curatormd" / "native-inbox"
    pending = 0
    if inbox.exists():
        for item_path in inbox.glob("*.json"):
            item = _as_object(_json_read(item_path, {}))
            pending += item.get("finalized") is not True and item.get("suppressed") is not True
    report: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "generated_at": bundle["trained_at"], "phase": "phase-1-human-only" if rows else "phase-0-instrumentation", "automation_enabled": False, "active_observations": len(rows), "approved": sum(item.get("disposition") == "approved" for item in rows), "rejected": sum(item.get("disposition") == "do-not-record" for item in rows), "pending": pending, "models": {"approval": approval_model["status"], "priority": priority_model["status"], "archive": archive_model["status"]}, "metrics": metrics, "qa": _qa_summary(root, profile), "automation_eligibility": {"eligible": False, "reason": "automatic decisions remain disabled; human review is required"}, "note": "QA outcomes and retrospective reviews remain separate from original labels; automation is disabled."}
    _write(model_dir / f"model-{version}.json", bundle)
    _write(latest_path, bundle)
    _write(directory / "reports" / "latest.json", report)
    return {"recomputed": True, "model_version": version, "observation_count": len(rows), "metrics": metrics, "automation_enabled": False}


def status(root: Path, profile: str | None = None) -> dict[str, Any]:
    directory = learning_root(root, profile)
    bundle = _as_object(_json_read(directory / "models" / "latest.json", {}))
    rows = _active_rows(root, profile, datetime.now(timezone.utc))
    return {"phase": "phase-1-human-only" if bundle else "phase-0-instrumentation", "automation_enabled": False, "active_observations": len(rows), "model_version": bundle.get("model_version"), "last_recompute": bundle.get("trained_at"), "next_recompute_due": _next_due(bundle.get("trained_at")), "models": {name: bundle.get(f"{name}_model", {}).get("status", "not-trained") for name in ("approval", "priority", "archive")}}


def _next_due(value: Any) -> str | None:
    if not isinstance(value, str): return None
    try: when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: return None
    return (when + timedelta(days=RECOMPUTE_DAYS)).isoformat().replace("+00:00", "Z")


def report(root: Path, profile: str | None = None) -> dict[str, Any]:
    directory = learning_root(root, profile)
    return _json_read(directory / "reports" / "latest.json", {"phase": "phase-0-instrumentation", "automation_enabled": False, "metrics": {}, "note": "No learning report has been generated."})


def save_observation(root: Path, profile: str | None, observation: dict[str, Any]) -> dict[str, Any]:
    path = _record_path(root, profile, "observations", f"{observation['record_id']}-r{observation.get('review_revision', 1)}")
    existing = _json_read(path, None)
    if existing is not None:
        if existing != observation:
            from gptmd_memory import CuratorError
            raise CuratorError("a different learning observation already exists for this record revision")
        return {"written": False, "duplicate": True, "path": str(path)}
    _write(path, observation)
    return {"written": True, "duplicate": False, "path": str(path)}


def record_qa_outcome(root: Path, profile: str | None, record_id: str, outcome: dict[str, Any]) -> dict[str, Any]:
    path = _record_path(root, profile, "qa-outcomes", f"{record_id}-{outcome['outcome_id']}")
    from gptmd_memory import create_json_once
    if not create_json_once(path, outcome):
        return {"written": False, "duplicate": True, "outcome_id": outcome["outcome_id"]}
    return {"written": True, "duplicate": False, "outcome_id": outcome["outcome_id"]}


def record_retrospective(root: Path, profile: str | None, record_id: str, review: dict[str, Any]) -> dict[str, Any]:
    path = _record_path(root, profile, "retrospective-audits", f"{record_id}-r{review['review_revision']}")
    from gptmd_memory import create_json_once
    if not create_json_once(path, review):
        existing = _json_read(path, {})
        fields = ("still_correct", "usefulness", "germane", "should_have_recorded")
        if all(existing.get(field) == review.get(field) for field in fields):
            return {"written": False, "duplicate": True, "record_id": record_id, "review_revision": review["review_revision"]}
        from gptmd_memory import CuratorError
        raise CuratorError("a retrospective review already exists for this record; revise it explicitly")
    return {"written": True, "record_id": record_id, "review_revision": review["review_revision"]}


def prune(root: Path, profile: str | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    directory = learning_root(root, profile)
    removed = 0
    held = 0
    observations = directory / "observations"
    paths: list[Path] = sorted(observations.glob("*.json")) if observations.exists() else []
    for path in paths:
        row = _as_object(_json_read(path, {}))
        try: reviewed = datetime.fromisoformat(str(row.get("review_timestamp", "")).replace("Z", "+00:00"))
        except ValueError: held += 1; continue
        if reviewed >= cutoff: continue
        if row.get("qa_windows_finalized") is not True or row.get("retrospective_finalized") is not True:
            held += 1
            continue
        record_id = str(row.get("record_id") or "")
        for collection in ("predictions", "qa-outcomes", "retrospective-audits"):
            related = directory / collection
            if related.exists():
                items: list[Path] = list(related.glob(f"{record_id}*.json"))
                for item in items:
                    item.unlink()
        transactions = directory / "transactions"
        if transactions.exists():
            transaction_paths: list[Path] = list(transactions.glob(f"{record_id}-r*.json"))
            for item in transaction_paths:
                transaction = _json_read(item, {})
                if transaction.get("status") == "committed": item.unlink()
        path.unlink()
        removed += 1
    return {"removed_observations": removed, "held_for_maturity": held, "retention_days": RETENTION_DAYS}
