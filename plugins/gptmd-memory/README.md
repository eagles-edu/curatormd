# CuratorMD

CuratorMD is the local-only project intelligence layer for Codex and Hermes.
It keeps durable knowledge in four reviewable Markdown files under a project's
`persistence/` directory and keeps unreviewed native observations in the
ignored `.curatormd/native-inbox/` directory.

For the complete user guide—including every MCP tool, CLI workflow, Python
function inventory, model formulas and limits, and SVG diagrams—see
[`docs/CURATORMD-USER-GUIDE.md`](../../docs/CURATORMD-USER-GUIDE.md).

The observer is project-scoped and best-effort. It records bounded, redacted
metadata from the configured Hermes profile; capture failure never blocks the
agent. A curator run can promote only an explicitly reviewed candidate. It
does not commit, push, deploy, run migrations, delete data, or modify
application source.

## Significant Development Event capture

The bundled Codex hooks inspect submitted prompts and completed assistant
responses for the SDE vocabulary in `hooks/sde_capture.py`. A match creates a
before/after candidate in that repository's ignored native inbox. The payload
contains only matched vocabulary, cue categories, and hashed session/turn
references; it never stores prompt or response text. Capture is best-effort and
never blocks a turn. Candidates remain unreviewed until a person approves or
rejects them. Hooks run only in repositories with a matching ignored
`.curatormd/project.json` root/profile marker, written by `enable_repo.py`.
Codex requires the user to inspect and trust plugin hooks once in `/hooks`.
See [`docs/SDE-CAPTURE.md`](../../docs/SDE-CAPTURE.md) for the trigger vocabulary
and capture boundaries.

## MCP tools

- `memory_recall` — search the four persistence documents.
- `persistence_status` — inspect document health and CuratorMD state.
- `environment_snapshot` — collect safe project metadata without reading env
  values, credentials, private keys, or unrelated repository data.
- `native_projection_record` — append a redacted, idempotent native projection.
- `curation_run` — create bounded proposals, recover interrupted finalizations,
  and promote only explicitly reviewed candidates.
- `curation_pending` — list pending summaries and review selections without raw
  event responses.
- `curation_review` — record an explicit human disposition, priority, archive,
  and optional text corrections. Approved writes use a durable journal and
  stable record markers. Corrected labels create a superseding observation
  while preserving the prior review for audit.
- `learning_status`, `learning_recompute`, and `learning_report` — inspect or
  recompute project-scoped models and prospective metrics. Training uses the
  active six-month human-label window and recomputes at most every 21 days.
- `qa_outcome_record` and `retrospective_review` — record later project outcomes
  separately from the original human label.
- `persistence_record` — append a reviewed durable decision, procedure, rule,
  or lesson idempotently.
- `self_improvement_capture` — record a verified failure/fix lesson.

All tools require an explicit absolute `project_root` that resolves to the
project's Git worktree root. The MCP server identifier is the machine-safe
`curatormd`; the plugin package remains `gptmd-memory` for marketplace
compatibility.

Learning state lives outside each repository under a profile-and-worktree
hash boundary. Separate repositories do not share observations, models, QA
outcomes, review state, or transaction journals. Per-worktree locking
serializes writes; state updates merge observer and curator data safely.
Automatic approval and rejection remain disabled.

Each Hermes profile receives the `gptmd-memory` workflow skill and the
`curation-learning` review/report skill from this package. Repository onboarding
reconciles profile skills and MCP configuration against the shared source.

## Knowledge authority

- `persistence/AGENTS.md` — current active rules.
- `persistence/SOP.md` — repeatable procedures and verification steps.
- `persistence/HISTORY.md` — dated decisions and rationale.
- `persistence/LESSONS-LEARNED.md` — verified failures, fixes, and prevention.

The plugin refuses common credential patterns, uses owner-readable state, and
never sends project data to a remote service.
