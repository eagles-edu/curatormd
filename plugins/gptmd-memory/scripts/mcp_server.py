#!/usr/bin/env python3
"""Stdio MCP server for the local CuratorMD project boundary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gptmd_memory import (  # noqa: E402
    append_entry,
    curate,
    learning_recompute,
    learning_report,
    learning_status,
    environment_snapshot,
    native_projection_record,
    pending_reviews,
    qa_outcome_record,
    retrospective_review,
    resolve_project_root,
    review_candidate,
    search,
    self_improvement,
    status,
)


PROJECT_ROOT = {"type": "string", "description": "Absolute Git worktree root. It must contain persistence/."}

TOOLS = [
    {"name": "memory_recall", "description": "Search durable project knowledge in persistence/*.md.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "query": {"type": "string"}, "scope": {"type": "string", "enum": ["all", "agents", "sop", "history", "lessons"]}}, "required": ["project_root", "query"]}},
    {"name": "persistence_status", "description": "Report persistence health, scoped Git state, inbox count, and capture status.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "profile": {"type": "string"}}, "required": ["project_root"]}},
    {"name": "environment_snapshot", "description": "Read only approved, safe repository metadata for a validated project root.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT}, "required": ["project_root"]}},
    {"name": "native_projection_record", "description": "Write a bounded, secret-redacted native-projection record to the temporary inbox.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "source_id": {"type": "string"}, "event_type": {"type": "string"}, "payload": {"type": ["object", "array", "string"]}, "cursor": {"type": "string"}, "profile": {"type": "string"}}, "required": ["project_root", "source_id", "event_type", "payload"]}},
    {"name": "curation_run", "description": "Run the bounded local curator. Only explicitly reviewed candidates may enter canonical Markdown.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "schedule_slot": {"type": "string"}, "profile": {"type": "string"}}, "required": ["project_root"]}},
    {"name": "curation_review", "description": "Record an explicit human decision for one generated candidate. Approved entries are journaled and appended idempotently; do-not-record decisions train only disposition and priority models.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "record_id": {"type": "string"}, "disposition": {"type": "string", "enum": ["approved", "do-not-record"]}, "priority": {"type": "integer", "minimum": 0, "maximum": 5}, "archive": {"type": "string", "enum": ["agents", "sop", "history", "lessons"]}, "confirm_priority_5": {"type": "boolean"}, "edits": {"type": "object", "properties": {"title": {"type": ["string", "null"]}, "content": {"type": ["string", "null"]}, "utility": {"type": ["string", "null"]}, "impact": {"type": ["string", "null"]}}}, "profile": {"type": "string"}}, "required": ["project_root", "record_id", "disposition", "priority"]}},
    {"name": "curation_pending", "description": "List bounded candidate summaries and selections awaiting human review without returning raw event responses.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "profile": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": ["project_root"]}},
    {"name": "learning_status", "description": "Report the project-scoped learning phase, active observation count, model versions, and next recomputation date. Automation is always reported separately and remains off by default.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "profile": {"type": "string"}}, "required": ["project_root"]}},
    {"name": "learning_recompute", "description": "Recompute bounded deterministic curation models and prospective metrics from the active six-month review window.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "profile": {"type": "string"}, "force": {"type": "boolean"}}, "required": ["project_root"]}},
    {"name": "learning_report", "description": "Read the latest local curation learning report, including prospective model metrics and support limitations.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "profile": {"type": "string"}}, "required": ["project_root"]}},
    {"name": "qa_outcome_record", "description": "Record a human-reviewed project QA outcome in a 30, 60, 90, or 180-day window without changing the original review label.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "record_id": {"type": "string"}, "outcome_type": {"type": "string"}, "window_days": {"type": "integer", "enum": [30, 60, 90, 180]}, "value": {}, "evidence": {"type": "string"}, "finalize_window": {"type": "boolean"}, "profile": {"type": "string"}}, "required": ["project_root", "record_id", "outcome_type", "window_days", "finalize_window"]}},
    {"name": "retrospective_review", "description": "Record a bounded human utility review of an older curation decision; keep it separate from original labels and model features.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "record_id": {"type": "string"}, "still_correct": {"type": "string", "enum": ["yes", "no", "uncertain"]}, "usefulness": {"type": "integer", "minimum": 0, "maximum": 4}, "germane": {"type": "string", "enum": ["yes", "superseded", "obsolete", "uncertain"]}, "should_have_recorded": {"type": "string", "enum": ["yes", "no", "uncertain"]}, "profile": {"type": "string"}}, "required": ["project_root", "record_id", "still_correct", "usefulness", "germane"]}},
    {"name": "persistence_record", "description": "Append a reviewed durable decision, procedure, active rule, or lesson idempotently.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "kind": {"type": "string", "enum": ["agents", "sop", "history", "lessons"]}, "title": {"type": "string"}, "content": {"type": "string"}, "rationale": {"type": "string"}, "impact": {"type": "string"}, "profile": {"type": "string"}}, "required": ["project_root", "kind", "title", "content"]}},
    {"name": "self_improvement_capture", "description": "Record a verified failure, root cause, fix, evidence, and prevention rule idempotently.", "inputSchema": {"type": "object", "properties": {"project_root": PROJECT_ROOT, "failure": {"type": "string"}, "cause": {"type": "string"}, "fix": {"type": "string"}, "prevention": {"type": "string"}, "profile": {"type": "string"}}, "required": ["project_root", "failure", "cause", "fix", "prevention"]}},
]


def reply(request_id, result=None, error=None):
    response = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        response["error"] = {"code": -32603, "message": str(error)}
    else:
        response["result"] = result
    sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def call_tool(name: str, arguments: dict):
    root = resolve_project_root(arguments.get("project_root"))
    if name == "memory_recall":
        return search(root, arguments.get("query", ""), arguments.get("scope", "all"))
    if name == "persistence_status":
        return status(root, arguments.get("profile"))
    if name == "environment_snapshot":
        return environment_snapshot(str(root))
    if name == "native_projection_record":
        return native_projection_record(str(root), arguments["source_id"], arguments["event_type"], arguments["payload"], arguments.get("cursor"), arguments.get("profile"))
    if name == "curation_run":
        return curate(str(root), schedule_slot=arguments.get("schedule_slot", "06:00 Asia/Ho_Chi_Minh"), profile=arguments.get("profile"))
    if name == "curation_review":
        return review_candidate(str(root), arguments["record_id"], arguments["disposition"], arguments["priority"], arguments.get("archive"), confirm_priority_5=arguments.get("confirm_priority_5", False), edits=arguments.get("edits"), profile=arguments.get("profile"))
    if name == "curation_pending":
        return pending_reviews(root, arguments.get("profile"), limit=arguments.get("limit", 30))
    if name == "learning_status":
        return learning_status(root, arguments.get("profile"))
    if name == "learning_recompute":
        return learning_recompute(root, arguments.get("profile"), force=arguments.get("force", False))
    if name == "learning_report":
        return learning_report(root, arguments.get("profile"))
    if name == "qa_outcome_record":
        return qa_outcome_record(root, arguments["record_id"], arguments["outcome_type"], arguments["window_days"], arguments.get("value"), arguments.get("evidence", ""), finalize_window=arguments["finalize_window"], profile=arguments.get("profile"))
    if name == "retrospective_review":
        return retrospective_review(root, arguments["record_id"], arguments["still_correct"], arguments["usefulness"], arguments["germane"], should_have_recorded=arguments.get("should_have_recorded"), profile=arguments.get("profile"))
    if name == "persistence_record":
        return append_entry(root, arguments["kind"], arguments["title"], arguments["content"], arguments.get("rationale"), arguments.get("impact"), profile=arguments.get("profile"))
    if name == "self_improvement_capture":
        return self_improvement(root, arguments["failure"], arguments["cause"], arguments["fix"], arguments["prevention"], profile=arguments.get("profile"))
    raise ValueError(f"unknown tool: {name}")


for line in sys.stdin:
    if not line.strip():
        continue
    request = {}
    try:
        request = json.loads(line)
        method = request.get("method")
        request_id = request.get("id")
        if method == "initialize":
            reply(request_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "curatormd", "version": "0.4.7"}})
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            reply(request_id, {"tools": TOOLS})
        elif method == "tools/call":
            result = call_tool(request["params"]["name"], request["params"].get("arguments", {}))
            reply(request_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}], "structuredContent": result})
        else:
            reply(request_id, error=f"unsupported method: {method}")
    except Exception as exc:  # Keep the server alive after a rejected request.
        reply(request.get("id"), error=exc)
