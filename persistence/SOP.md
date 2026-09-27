# Standard operating procedures

## Start a system-repository change

Read all four persistence files, inspect the relevant CuratorMD-owned implementation, then make the narrowest change that preserves consumer-repository isolation.

## Validate Python analysis

Keep each maintained Python module in `pyrightconfig.json` so command-line
Pyright and Pylance analyze the same project scope. Preserve strict checking
for typed learning/model code. For JSON-heavy boundary modules, use an explicit
file-level mode and narrow loaded values before nested access. Run `pyright`
from the repository root and require zero diagnostics.

## Enable a consumer repository

Use `plugins/curatormd/scripts/enable_repo.py` with an absolute Git root, a dedicated Hermes profile, and an unused local schedule. Preserve existing consumer files and keep generated runtime state ignored.

## SDE capture

Capture only bounded vocabulary cues and safe metadata in automatic hooks. Cue words alone are not an SDE and must not become candidate prose.

Use the `sde-curation` Hermes skill to inspect the full relevant thread and submit one complete SDE proposal through `sde_parse`: beginning (trigger and context), middle (decisions and work), and end (outcome and verification). Preserve substantive project meaning and scrub credentials/secrets only. Never persist the raw prompt, response, tool arguments, or complete transcript. Keep the single structured synthesis pending until a human reviews it.

Every SDE proposal must state `utility` and `impact` concretely. `utility` explains what future project work can reuse from the event, such as a decision, repair path, constraint, or verification method. `impact` states the evidenced or explicitly expected effect on project quality, such as correctness, reliability, maintainability, or performance; distinguish observed results from expectations. Neither field describes review status or generic preservation value.

Route an SDE to `agents` when it updates the reusable description of the software or a subsystem: features, purpose, operation, use, settings, additions, removals, improvements, and other changes to the system or its parts. Use `history` when the SDE primarily records chronology that does not change that current reference. Use `sop` for repeatable procedures and `lessons` for verified failure causes and prevention.

The four canonical files serve different retrieval needs: `persistence/AGENTS.md` is the current project, software/subsystem, and agent reference; `persistence/SOP.md` contains repeatable procedures; `persistence/HISTORY.md` records dated decisions and outcomes; `persistence/LESSONS-LEARNED.md` records verified failure causes and prevention rules. Put each fact where a future reader would look for that kind of answer, and avoid duplicating the same narrative across files.

## Recover a failed review

1. Inspect `persistence_status`, the prepared transaction, and the complete target-file diff. Do not reset, overwrite, or commit the consumer's edits.
2. Retry `curation_run` for automatic recovery. New prepared transactions contain the target hash captured at approval time; recovery appends only if the target is unchanged and uses an idempotent record marker.
3. For one transaction, call `curation_recover`. A legacy journal without a baseline hash requires diff review and explicit `accept_current_target: true`.
4. If a prepared but unfinalized proposal is wrong, submit a corrected `curation_review`. The older prepared revision becomes superseded and will not append.
5. If recovery remains blocked, report the exact conflicting file and give the manual command below. Never stop at the first error without a cause and a repair plan.

```bash
python3 plugins/curatormd/scripts/curatormd.py \
  --project-root /absolute/path/to/repo --profile repo-coding recover RECORD_ID

# Only after reviewing the complete diff for a legacy journal:
python3 plugins/curatormd/scripts/curatormd.py \
  --project-root /absolute/path/to/repo --profile repo-coding recover RECORD_ID \
  --accept-current-target
```
