---
name: sde-curation
description: Turn a significant development event from the full available thread into a factual, reviewable CuratorMD proposal with verified implementation and recovery evidence.
---

# CuratorMD significant development events

Use this skill when a thread contains a durable project decision, feature,
recovery, incident, or verified repair. Vocabulary matches alone are never an
SDE and must never become a persistence entry.

## Development sequence

Start each development task with a concise summary and success criteria. Then
work through all five stages in order: (1) troubleshooting and root cause,
(2) remediation plan, (3) implementation, (4) testing, and (5) completion
verification and summary. Do not stop at an error: continue safe diagnosis and
repair, or provide the cause and concrete manual/automatic recovery paths.

## Read the full available discussion

1. Use the current conversation and, when needed, the bound Hermes profile's
   session search to review the complete relevant thread, including the
   initiating request, decisions, implementation, failures, repair steps, and
   verification results.
2. Synthesize the discussion into the defined fields below. Preserve normal
   technical nouns, project names, paths, commands, and meaningful outcomes.
   Scrub credentials and secrets only. Do not invent missing facts.
3. Do not store raw prompts, responses, tool arguments, or whole transcripts.
   The synthesis is the durable candidate; full-thread review happens before
   calling the MCP.
4. If implementation or verification is incomplete, state that plainly and do
   not call it successful. If the evidence is too thin, do not create an SDE.

## Decide whether the event merits an SDE

Create an SDE when the full thread shows a consequential project change or
decision with durable value: a software or subsystem feature/change, a design
trade-off, a verified failure and reusable repair, or a meaningful quality,
runtime, security, data, or configuration outcome. Include additions,
removals, improvements, and modernization when they change how the project
works or how future work should proceed.

Do not infer an SDE from trigger words, a routine lifecycle event, a search or
question, formatting-only work, a transient action, or the size of a diff.
Require a coherent trigger, decisions/work, and outcome or remaining limit.
Partial or blocked work can qualify when its root cause, recovery, risk, or
unresolved decision is worth retaining; label unverified results. Do not
duplicate existing durable knowledge unless the event adds material evidence
or a meaningful change.

## Defined SDE fields

Call `sde_parse` once with one complete event proposal containing:

- `title`: a concise, concrete name for the feature, decision, or repair. Aim
  for 4–10 words; lead with the important action or outcome. Omit the SDE ID,
  setup narration, cue vocabulary, and verification details. Prefer
  `Add Codex hook for development event review` over a sentence describing
  every step in the event. Use terms a project contributor can understand
  without knowing CuratorMD's internal vocabulary.
- `beginning`: when and why the event started, including the trigger, context,
  and initial failure or need.
- `middle`: how the event developed, including important decisions,
  implemented changes, and manual or automatic recovery paths.
- `end`: the resulting state and evidence, including verification results,
  unresolved limits, and whether the implementation completed.
- `utility` (required): why preserving this event helps future project work. Name the
  reusable decision, repair path, constraint, or verification method; do not
  say only that the result is being preserved.
- `impact` (required): the evidenced or explicitly expected effect on project quality,
  such as correctness, reliability, maintainability, or performance. Separate
  observed outcomes from expected effects and do not claim an improvement that
  was not verified.
- `rationale`, `follow_up`: optional useful detail.
- `archive`: suggested destination (`agents`, `sop`, `history`, or `lessons`)
  selected using the archive rules above. The archive suggestion does not
  approve the candidate; the human reviewer still makes the final choice.

The MCP validates the three chronological sections and renders them into one
complete candidate entry. Keep one event together; do not split its beginning,
middle, and end into separate proposals. It scrubs secrets and writes only
this bounded synthesis to the project's temporary inbox. It never stores the
raw thread.
Read the resulting candidate and call `curation_review` only after a human
chooses approve or do-not-record.

## Archive selection

- `persistence/AGENTS.md` (`agents`): the active project/agent reference.
  It describes the current software and subsystems, their features, purpose,
  operation, use, and settings, along with active project and agent rules.
  Route SDEs here when they describe additions,
  removals, improvements, or other changes to the software as a whole or to
  one of its subsystems. Future readers look here to learn what the system
  does, why it exists, how it operates, and how its parts fit together.
- `persistence/SOP.md` (`sop`): repeatable procedures, including
  troubleshooting and recovery steps; future readers look here to perform the
  procedure.
- `persistence/HISTORY.md` (`history`):
  dated decisions and outcomes that matter as chronology but do not primarily
  update the current software or subsystem reference; future readers look here
  for what happened and when.
- `persistence/LESSONS-LEARNED.md` (`lessons`):
  verified failure causes and prevention rules; future readers look here to
  avoid repeating a known failure.

For every SDE, choose the file that answers the future reader's likely
question. Keep one canonical account; do not copy the same narrative into
multiple files. A `history` entry may point to an updated `agents` reference
when chronology and current system knowledge both matter.

One event can support more than one useful artifact, but write each document
for its purpose; do not copy the same narrative into every archive.

## Errors and recovery

Never stop at an error. Identify the cause, explain the safe repair, carry it
out when authorized, and verify it. If blocked, give a concrete manual path and
the available automatic retry path.

- `curation_run` automatically retries prepared transactions that have a
  captured target hash.
- Use `curation_recover` for a prepared transaction. For a legacy transaction
  with no target hash, inspect the target diff first, then set
  `accept_current_target: true` only if the current file should be the recovery
  baseline.
- To correct a failed, unfinalized decision, submit a new `curation_review`.
  The system supersedes the old prepared transaction and keeps its audit data.
- Never reset, overwrite, commit, or delete a consumer's project data to make
  recovery pass.
