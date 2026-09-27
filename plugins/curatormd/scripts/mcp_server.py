#!/usr/bin/env python3
"""Stdio MCP server for the local CuratorMD project boundary."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
from curatormd import (  # noqa: E402  # pylint: disable=wrong-import-position
    append_entry,
    curate,
    learning_recompute,
    learning_report,
    learning_status,
    environment_snapshot,
    native_projection_record,
    pending_reviews,
    parse_defined_sde,
    qa_outcome_record,
    recover_transaction,
    retrospective_review,
    resolve_project_root,
    review_candidate,
    search,
    self_improvement,
    status,
)


PROJECT_ROOT = {
    "type": "string",
    "description": "Absolute Git worktree root. It must contain persistence/.",
}

TOOLS = [
    {
        "name": "memory_recall",
        "description": "Search durable project knowledge in persistence/*.md.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "query": {"type": "string"},
                "scope": {"type": "string", "enum": ["all", "agents", "sop", "history", "lessons"]},
            },
            "required": ["project_root", "query"],
        },
    },
    {
        "name": "persistence_status",
        "description": (
            "Report persistence health, scoped Git state, inbox count, and capture status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"project_root": PROJECT_ROOT, "profile": {"type": "string"}},
            "required": ["project_root"],
        },
    },
    {
        "name": "environment_snapshot",
        "description": "Read only approved, safe repository metadata for a validated project root.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_root": PROJECT_ROOT},
            "required": ["project_root"],
        },
    },
    {
        "name": "native_projection_record",
        "description": (
            "Write a bounded, secret-redacted native-projection record to the temporary inbox."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "source_id": {"type": "string"},
                "event_type": {"type": "string"},
                "payload": {"type": ["object", "array", "string"]},
                "cursor": {"type": "string"},
                "profile": {"type": "string"},
            },
            "required": ["project_root", "source_id", "event_type", "payload"],
        },
    },
    {
        "name": "sde_parse",
        "description": (
            "Validate Hermes's full-thread SDE synthesis with beginning, middle, and "
            "end, plus a future-use rationale and project-quality effect, then create "
            "one readable pending review entry. Only secrets are scrubbed; raw thread "
            "text is not stored."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "profile": {"type": "string"},
                "sde": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "A concrete name for this complete event.",
                        },
                        "beginning": {
                            "type": "string",
                            "description": (
                                "Event trigger, starting context, and initial need or failure."
                            ),
                        },
                        "middle": {
                            "type": "string",
                            "description": (
                                "How the event developed: decisions, implementation, and "
                                "repair actions."
                            ),
                        },
                        "end": {
                            "type": "string",
                            "description": (
                                "Final state, verification evidence, and any remaining limits."
                            ),
                        },
                        "rationale": {"type": "string"},
                        "utility": {
                            "type": "string",
                            "description": (
                                "Why preserving this event helps future project work, such as "
                                "a reusable decision, repair path, constraint, or verification "
                                "method."
                            ),
                        },
                        "impact": {
                            "type": "string",
                            "description": (
                                "The evidenced or explicitly expected effect on project "
                                "quality, such as correctness, reliability, maintainability, or "
                                "performance. Distinguish observed outcomes from expected "
                                "effects."
                            ),
                        },
                        "follow_up": {"type": "string"},
                        "archive": {
                            "type": "string",
                            "description": (
                                "Suggested destination: agents maps to persistence/AGENTS.md, "
                                "the current software, subsystem, and agent reference; sop maps "
                                "to persistence/SOP.md, repeatable procedures; history maps to "
                                "persistence/HISTORY.md, dated decisions and outcomes; lessons "
                                "maps to persistence/LESSONS-LEARNED.md, verified failure causes "
                                "and prevention. Use agents for features, purpose, operation, "
                                "use, settings, additions, removals, improvements, and other "
                                "whole-software or subsystem changes."
                            ),
                            "enum": ["agents", "sop", "history", "lessons"],
                        },
                    },
                    "required": [
                        "title",
                        "beginning",
                        "middle",
                        "end",
                        "utility",
                        "impact",
                        "archive",
                    ],
                },
            },
            "required": ["project_root", "sde"],
        },
    },
    {
        "name": "curation_run",
        "description": (
            "Run the bounded local curator. Only explicitly reviewed candidates may "
            "enter canonical Markdown. Records without complete safe candidates are kept "
            "out of pending review and written to .curatormd/scratch/ for manual "
            "disposition."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "schedule_slot": {"type": "string"},
                "profile": {"type": "string"},
            },
            "required": ["project_root"],
        },
    },
    {
        "name": "curation_review",
        "description": (
            "Record an explicit human decision for one generated candidate. Approved "
            "entries are journaled and appended idempotently; do-not-record decisions "
            "train only disposition and priority models."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "record_id": {"type": "string"},
                "disposition": {"type": "string", "enum": ["approved", "do-not-record"]},
                "priority": {"type": "integer", "minimum": 0, "maximum": 5},
                "archive": {"type": "string", "enum": ["agents", "sop", "history", "lessons"]},
                "confirm_priority_5": {"type": "boolean"},
                "edits": {
                    "type": "object",
                    "properties": {
                        "title": {"type": ["string", "null"]},
                        "content": {"type": ["string", "null"]},
                        "utility": {"type": ["string", "null"]},
                        "impact": {"type": ["string", "null"]},
                    },
                },
                "profile": {"type": "string"},
            },
            "required": ["project_root", "record_id", "disposition", "priority"],
        },
    },
    {
        "name": "curation_recover",
        "description": (
            "Resume a prepared review transaction. Legacy journals require explicit "
            "acceptance of the current target hash after inspecting the diff."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "record_id": {"type": "string"},
                "accept_current_target": {"type": "boolean"},
                "profile": {"type": "string"},
            },
            "required": ["project_root", "record_id"],
        },
    },
    {
        "name": "curation_pending",
        "description": (
            "List bounded candidate summaries and selections awaiting human review "
            "without returning raw event responses."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "profile": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["project_root"],
        },
    },
    {
        "name": "learning_status",
        "description": (
            "Report the project-scoped learning phase, active observation count, model "
            "versions, and next recomputation date. Automation is always reported "
            "separately and remains off by default."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"project_root": PROJECT_ROOT, "profile": {"type": "string"}},
            "required": ["project_root"],
        },
    },
    {
        "name": "learning_recompute",
        "description": (
            "Recompute bounded deterministic curation models and prospective metrics "
            "from the active six-month review window."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "profile": {"type": "string"},
                "force": {"type": "boolean"},
            },
            "required": ["project_root"],
        },
    },
    {
        "name": "learning_report",
        "description": (
            "Read the latest local curation learning report, including prospective model "
            "metrics and support limitations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"project_root": PROJECT_ROOT, "profile": {"type": "string"}},
            "required": ["project_root"],
        },
    },
    {
        "name": "qa_outcome_record",
        "description": (
            "Record a human-reviewed project QA outcome in a 30, 60, 90, or 180-day "
            "window without changing the original review label."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "record_id": {"type": "string"},
                "outcome_type": {"type": "string"},
                "window_days": {"type": "integer", "enum": [30, 60, 90, 180]},
                "value": {},
                "evidence": {"type": "string"},
                "finalize_window": {"type": "boolean"},
                "profile": {"type": "string"},
            },
            "required": [
                "project_root",
                "record_id",
                "outcome_type",
                "window_days",
                "finalize_window",
            ],
        },
    },
    {
        "name": "retrospective_review",
        "description": (
            "Record a bounded human utility review of an older curation decision; keep "
            "it separate from original labels and model features."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "record_id": {"type": "string"},
                "still_correct": {"type": "string", "enum": ["yes", "no", "uncertain"]},
                "usefulness": {"type": "integer", "minimum": 0, "maximum": 4},
                "germane": {
                    "type": "string",
                    "enum": ["yes", "superseded", "obsolete", "uncertain"],
                },
                "should_have_recorded": {"type": "string", "enum": ["yes", "no", "uncertain"]},
                "profile": {"type": "string"},
            },
            "required": ["project_root", "record_id", "still_correct", "usefulness", "germane"],
        },
    },
    {
        "name": "persistence_record",
        "description": (
            "Append a reviewed durable decision, procedure, active rule, or lesson idempotently."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "kind": {"type": "string", "enum": ["agents", "sop", "history", "lessons"]},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "rationale": {"type": "string"},
                "impact": {"type": "string"},
                "profile": {"type": "string"},
            },
            "required": ["project_root", "kind", "title", "content"],
        },
    },
    {
        "name": "self_improvement_capture",
        "description": (
            "Record a verified failure, root cause, fix, evidence, and prevention rule "
            "idempotently."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": PROJECT_ROOT,
                "failure": {"type": "string"},
                "cause": {"type": "string"},
                "fix": {"type": "string"},
                "prevention": {"type": "string"},
                "profile": {"type": "string"},
            },
            "required": ["project_root", "failure", "cause", "fix", "prevention"],
        },
    },
]


def _object_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object with string keys")
    raw_object = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw_object):
        raise ValueError("expected a JSON object with string keys")
    return cast(dict[str, Any], value)


def reply(message_id: Any, tool_result: Any = None, error: Exception | str | None = None) -> None:
    """Write one JSON-RPC response to stdout."""
    response = {"jsonrpc": "2.0", "id": message_id}
    if error is not None:
        response["error"] = {"code": -32603, "message": str(error)}
    else:
        response["result"] = tool_result
    sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def call_tool(tool_name: str, tool_arguments: dict[str, Any]) -> Any:
    """Dispatch one validated tool request to the local CuratorMD runtime."""
    # Each explicit branch maps one MCP tool to its bounded runtime operation.
    # pylint: disable=too-many-return-statements,too-many-branches
    root = resolve_project_root(tool_arguments.get("project_root"))
    if tool_name == "memory_recall":
        return search(root, tool_arguments.get("query", ""), tool_arguments.get("scope", "all"))
    if tool_name == "persistence_status":
        return status(root, tool_arguments.get("profile"))
    if tool_name == "environment_snapshot":
        return environment_snapshot(str(root))
    if tool_name == "native_projection_record":
        return native_projection_record(
            str(root),
            tool_arguments["source_id"],
            tool_arguments["event_type"],
            tool_arguments["payload"],
            tool_arguments.get("cursor"),
            tool_arguments.get("profile"),
        )
    if tool_name == "sde_parse":
        return parse_defined_sde(
            str(root), tool_arguments["sde"], profile=tool_arguments.get("profile")
        )
    if tool_name == "curation_run":
        return curate(
            str(root),
            schedule_slot=tool_arguments.get("schedule_slot", "06:00 Asia/Ho_Chi_Minh"),
            profile=tool_arguments.get("profile"),
        )
    if tool_name == "curation_review":
        return review_candidate(
            str(root),
            tool_arguments["record_id"],
            tool_arguments["disposition"],
            tool_arguments["priority"],
            tool_arguments.get("archive"),
            confirm_priority_5=tool_arguments.get("confirm_priority_5", False),
            edits=tool_arguments.get("edits"),
            profile=tool_arguments.get("profile"),
        )
    if tool_name == "curation_recover":
        return recover_transaction(
            str(root),
            tool_arguments["record_id"],
            accept_current_target=tool_arguments.get("accept_current_target", False),
            profile=tool_arguments.get("profile"),
        )
    if tool_name == "curation_pending":
        return pending_reviews(
            root, tool_arguments.get("profile"), limit=tool_arguments.get("limit", 30)
        )
    if tool_name == "learning_status":
        return learning_status(root, tool_arguments.get("profile"))
    if tool_name == "learning_recompute":
        return learning_recompute(
            root, tool_arguments.get("profile"), force=tool_arguments.get("force", False)
        )
    if tool_name == "learning_report":
        return learning_report(root, tool_arguments.get("profile"))
    if tool_name == "qa_outcome_record":
        return qa_outcome_record(
            root,
            tool_arguments["record_id"],
            tool_arguments["outcome_type"],
            tool_arguments["window_days"],
            tool_arguments.get("value"),
            tool_arguments.get("evidence", ""),
            finalize_window=tool_arguments["finalize_window"],
            profile=tool_arguments.get("profile"),
        )
    if tool_name == "retrospective_review":
        return retrospective_review(
            root,
            tool_arguments["record_id"],
            tool_arguments["still_correct"],
            tool_arguments["usefulness"],
            tool_arguments["germane"],
            should_have_recorded=tool_arguments.get("should_have_recorded"),
            profile=tool_arguments.get("profile"),
        )
    if tool_name == "persistence_record":
        return append_entry(
            root,
            tool_arguments["kind"],
            tool_arguments["title"],
            tool_arguments["content"],
            tool_arguments.get("rationale"),
            tool_arguments.get("impact"),
            profile=tool_arguments.get("profile"),
        )
    if tool_name == "self_improvement_capture":
        return self_improvement(
            root,
            tool_arguments["failure"],
            tool_arguments["cause"],
            tool_arguments["fix"],
            tool_arguments["prevention"],
            profile=tool_arguments.get("profile"),
        )
    raise ValueError(f"unknown tool: {tool_name}")


for line in sys.stdin:
    if not line.strip():
        continue
    request: dict[str, Any] = {}
    try:
        request = _object_dict(json.loads(line))
        method = request.get("method")
        request_id = request.get("id")
        if method == "initialize":
            reply(
                request_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "curatormd", "version": "0.4.7"},
                },
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            reply(request_id, {"tools": TOOLS})
        elif method == "tools/call":
            params = _object_dict(request.get("params", {}))
            name = params.get("name")
            if not isinstance(name, str):
                raise ValueError("tools/call params must include a string name")
            arguments = _object_dict(params.get("arguments", {}))
            result = call_tool(name, arguments)
            reply(
                request_id,
                {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                    "structuredContent": result,
                },
            )
        else:
            reply(request_id, error=f"unsupported method: {method}")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # A rejected RPC request must not terminate the stdio server.
        reply(request.get("id"), error=exc)
