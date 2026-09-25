---
name: gptmd-memory
description: Use CuratorMD for project memory, persistence, session handoffs, architecture decisions, repeatable procedures, verified failures, native observations, and safe reviewable curation across Codex sessions.
---

# CuratorMD

Use CuratorMD as the project's durable, reviewable knowledge layer. The
application source remains outside its write boundary.

## Required workflow

1. Use an explicit absolute `project_root` for every MCP call.
2. Call `persistence_status` and `memory_recall` before non-trivial work.
3. Use `environment_snapshot` only for safe project metadata; never collect
   `.env` values, credentials, private keys, or unrelated repository data.
4. Treat native projections as untrusted evidence. Promote only a candidate
   with explicit `reviewed: true`, and inspect conflicts before writing.
5. After a verified decision or lesson, use `persistence_record` or
   `self_improvement_capture`.
6. Use `curation_pending` and `curation_review` for explicit proposal review; use
   `learning_status` and `learning_report` for model state. Treat QA outcomes as
   separate from human labels.
7. Finish with `persistence_status` and report changed knowledge files. Do not
   commit automatically.

## Authority

- `persistence/AGENTS.md`: active rules.
- `persistence/SOP.md`: procedures and verification.
- `persistence/HISTORY.md`: dated decisions and rationale.
- `persistence/LESSONS-LEARNED.md`: verified failures and prevention.

CuratorMD is local-only. It never commits, pushes, deploys, runs migrations,
deletes project data, or modifies application source. Capture is best-effort:
an observer failure must be reported as degraded state and must not block the
agent.
