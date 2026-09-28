# Standard operating procedures

## Start a system-repository change

Read all four persistence files, inspect the relevant CuratorMD-owned implementation, then make the narrowest change that preserves consumer-repository isolation.

## Validate Python analysis

Keep each maintained Python module in `pyrightconfig.json` so command-line
Pyright and Pylance analyze the same project scope. Preserve strict checking
for typed learning/model code. For JSON-heavy boundary modules, use an explicit
file-level mode and narrow loaded values before nested access. Run `pyright`
from the repository root and require zero diagnostics.

## Repair and document test or configuration failures

1. Reproduce the reported failure with the repository interpreter and the same test or configuration command. Record the test name, expected value, actual value, and active configuration.
2. Trace the result to the owning implementation and check the intended behavior against this SOP and the relevant caller. Distinguish an implementation defect from an assertion or configuration that no longer matches the contract.
3. Make the narrowest repair in the owning source, configuration, or test. Change an assertion only after confirming the intended behavior; do not hide a real regression by weakening the check.
4. Rerun the focused case, then the full relevant suite. For Python changes, run project Pyright and the configured Pylint check. Run `git diff --check` before considering the repair verified.
5. Immediately after verification, add the confirmed cause and repeatable repair or recovery steps to this SOP. If the failure reveals a prevention rule rather than a recurring procedure, record that rule in `persistence/LESSONS-LEARNED.md` as well.

### Verified curation assertion repair (2026-09-28)

The two failures recorded during the plugin rename were stale test expectations, not runtime defects:

- `test_unreviewed_projection_is_ambiguous_and_not_promoted` expected one ambiguous item but received none. Its `{ "note": "candidate" }` payload had no disposition content, so curation removes the empty projection. The test now checks `empty_removed`, no pending review or scratch item, and no canonical archive write.
- `test_vocabulary_only_sde_capture_never_becomes_proposal_text` expected one suppressed item but received none. Cue-only SDE metadata is retained in `.curatormd/scratch/` with `awaiting-manual-disposition`; it must not enter pending review or be labeled as a routine suppression. The test now checks the scratch artifact and its reason.

To verify these cases and the complete suite, run:

```bash
./.venv/bin/python -m unittest discover -s plugins/curatormd/tests -v
pyright --project .
pylint --errors-only $(git ls-files '*.py')
git diff --check
```

The verified run passed all 19 tests, strict Pyright (`0 errors, 0 warnings, 0 informations`), Pylint with `--errors-only`, and the diff check. No production code change was needed; the assertions were corrected to match the established empty-projection and cue-only SDE handling.

### Verified Pylance workspace-setting repair (2026-09-28)

When this repository has `pyrightconfig.json`, Pylance reports `settingsNotOverridable` if `.vscode/settings.json` also sets `python.analysis.extraPaths` or `python.analysis.typeCheckingMode`. Remove those duplicate workspace settings. Keep strictness and import search paths in `pyrightconfig.json` (`typeCheckingMode` and the relevant execution-environment `extraPaths`) so Pylance and command-line Pyright share the project configuration. Preserve unrelated workspace settings such as the project interpreter and formatter.

Validate with `python3 -m json.tool .vscode/settings.json` and `pyright --project .`. If the old diagnostics remain in VS Code after the settings are fixed, refresh the Problems panel or reload the window.

### Verified Pylint line-length repair (2026-09-28)

For `C0301:line-too-long` in Python tests, keep the configured 88-character limit. Split long test strings into adjacent literals inside parentheses so Python preserves the exact value. If a test method name itself exceeds the limit, shorten the name while retaining the `test_` prefix and keep the behavior clear in its docstring. Verify with `pylint --disable=all --enable=C0301 path/to/test_file.py`, project Pyright, and `git diff --check`.

## Commit and push CuratorMD development changes

Run `npm run update-git` from the repository root. The script stages all non-ignored changes with `git add .`, then pre-fills an editable commit-message prompt with the next `curatorMD-dev_` sequence. Press Enter to accept and commit; an optional description may follow the generated version. The script pushes the current branch to its configured upstream.

The four numeric fields use base 100: increment the last field through `99`, then carry to the previous field and reset the last to `00` (`curatorMD-dev_0.0.0.99` becomes `curatorMD-dev_0.0.01.00`; `curatorMD-dev_0.0.99.99` becomes `curatorMD-dev_0.1.00.00`). Ctrl+C cancels the commit prompt but leaves changes staged. If the push fails after a successful commit, push that commit with `git push` before starting another numbered update.

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
