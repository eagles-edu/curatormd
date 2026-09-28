# Decision history

## 2026-09-26 — Create a dedicated CuratorMD repository

**Decision:** Establish `/home/eaglesvn/dockerz/curatormd` as the standalone owner of shared CuratorMD source, capture hooks, status extension, and documentation.

**Rationale:** Keeping CuratorMD source in its own repository prevents consumer application code, project memory, and shared system code from being conflated. Consumer repositories retain their own profiles and private state.

## 2026-09-26 — Add project-scoped SDE capture and clarify review/poll state

**Decision:** Bundle before/after SDE vocabulary capture with the CuratorMD Codex plugin and expose bounded cue JSON with hashed references. Cue-only captures do not become proposals. Hermes reviews the full relevant thread, synthesizes a defined SDE, and submits it through the `sde_parse` MCP for human review. Bind every consumer through an ignored root/profile marker and workspace-scoped VS Code profile/poll settings.

**Rationale:** Trigger-only records had no usable proposal text and produced generic cue-word filler. Implicit consumer-profile defaults also risked cross-repository confusion, while the status bar gave no indication that its timer was refreshing. The new skill and parser preserve a factual SDE synthesis without retaining raw transcripts.

## 2026-09-26 — Structured SDE parsing and review recovery

**Decision:** Add the Hermes `sde-curation` skill and `sde_parse` MCP so an agent can inspect the full relevant thread and submit a structured SDE with its problem, decision, implementation, verification, rationale, impact, and follow-up. Capture only cues automatically; scrub secrets in the synthesis and never store raw prompts, responses, tool arguments, or transcripts. Capture the target archive hash when preparing human approvals, retry unchanged transactions automatically, expose explicit manual recovery for legacy journals, and supersede a failed prepared revision when a reviewer corrects its decision.

**Rationale:** The prior SDE hook promoted vocabulary fragments as if they were event summaries, and approved writes could not resume safely when a target file was already dirty. A full-thread semantic synthesis and transaction-time baseline preserve meaning and existing edits while still detecting later changes.

**Impact:** Cue-only events no longer enter the review queue as gibberish. New human approvals can append alongside pre-existing edits when the target remains unchanged; later edits still stop recovery. `curation_recover` and CLI `recover` provide the manual path. The CuratorMD Python suite passed 18 tests, MCP discovery reported 16 tools, and Python compilation plus `git diff --check` passed.

## 2026-09-26 — Require chronological SDE summaries

**Decision:** Require every `sde_parse` proposal to contain a title and three sections: beginning (trigger and context), middle (decisions and work), and end (outcome and verification). Render the sections together as one complete review entry, and teach Hermes to synthesize this shape from the full relevant discussion.

**Rationale:** A list of separate problem, decision, implementation, and verification fields did not force the proposal to tell the event as one coherent progression. Explicit chronology makes the start, development, and verified result reviewable together.

**Impact:** The `sde_parse` MCP schema, CLI, Hermes skill, agent contract, SOP, and user guide now require and explain this format. The active consumer Hermes skill was refreshed. All 19 CuratorMD tests passed; Python compilation, MCP discovery of 16 tools, and `git diff --check` passed.

## 2026-09-26 — Align Pylance and Pyright scope for CuratorMD scripts

**Decision:** Add `curatormd.py` to the Pyright project scope, keep its JSON-heavy boundary at explicit basic checking while retaining strict checks for `curation_learning.py`, and narrow optional JSON objects before access. Validate archive names before set lookup and require generated proposal data before storing it. Add the script's technical identifiers to workspace spellcheck vocabulary.

**Rationale:** The editor reported 359 Pylance errors because the runtime module was omitted from the project include and inherited strict checking, along with 12 spellcheck notices. The file also had optional-value access paths that the project-level check had not covered.

**Impact:** Project-level Pyright now analyzes both maintained modules with zero errors, warnings, or information diagnostics. All 19 CuratorMD tests and Python compilation passed; `git diff --check` passed.

## 2026-09-28 — Remove GPTMD coupling from CuratorMD

**Decision:** ## Remove GPTMD coupling from CuratorMD

**Beginning — trigger and context:** A review found the CuratorMD plugin still used GPTMD-specific names and an implicit GPTMD_PROJECT_ROOT fallback. The user required CuratorMD-owned files and runtime names to be consumer-neutral, with each consumer's root and profile kept in its own configuration.

**Middle — decisions and work:** The CLI and shared resolver were changed to require an explicit project root, removing GPTMD_PROJECT_ROOT and current-directory fallback behavior. CuratorMD-owned plugin, script, skill, test, cron, and documentation names were renamed; remaining consumer references were removed from this repository while consumer profile names stayed in consumer configuration. Six Hermes profiles and the local Codex plugin and VS Code status extension bindings were updated to the shared CuratorMD source.

**End — outcome and verification:** Strict Pyright reported zero diagnostics; Python compilation, Node syntax, and git diff checks passed. All six Hermes MCP checks discovered 16 tools, and the local Codex plugin and status extension were refreshed. The full Python suite still showed two curation assertion failures during the migration; they were reported as pre-existing and unrelated to the rename, so the migration did not establish a fully green suite.

**Future utility:** Future plugin changes can follow the explicit-root and consumer-owned-profile boundary to avoid routing CuratorMD state into a consumer repository or coupling shared source names to one consumer.

**Project impact:** Observed: the shared source and six profile bindings used the renamed CuratorMD paths, and MCP discovery succeeded for each profile. Expected: explicit project selection and neutral plugin identity reduce cross-repository routing and maintenance errors.

**Rationale:** Future plugin changes can follow the explicit-root and consumer-owned-profile boundary to avoid routing CuratorMD state into a consumer repository or coupling shared source names to one consumer.

**Impact:** Observed: the shared source and six profile bindings used the renamed CuratorMD paths, and MCP discovery succeeded for each profile. Expected: explicit project selection and neutral plugin identity reduce cross-repository routing and maintenance errors.

<!-- curatormd:record_id=46a2b50d8d21b29b0b2f0d187ebfc9a9;content_sha256=1175967c3cd4c3f3327ffcf2dad2123594d0050a28bf50d4c79a5eb75ef82c90 -->
<!-- curatormd:fingerprint=d43ec4aeb57f0496dc568ab70b47d473e3a90644613340b8a09a432eeda97c44 -->

## 2026-09-28 — Standardize CuratorMD Python tooling

**Decision:** ## Standardize CuratorMD Python tooling

**Beginning — trigger and context:** On September 27, Pylance and Pyright findings exposed that the repository's Python checking scope, formatter settings, and selected interpreter were not aligned. The user requested all maintained Python files remain in strict mode, Black become the default formatter, and the project interpreter be selected.

**Middle — decisions and work:** The project Pyright scope was expanded to all nine repository Python files and dynamic JSON boundaries were narrowed until strict analysis passed. Pylint was installed persistently through uv, the repository gained Black configuration targeting Python 3.10 with an 88-character line length, Pylint was aligned to 88, and VS Code was configured for Black with format-on-save. A repository-local .venv was created with Python 3.12.3; VS Code's default interpreter points to it and new terminals activate it. The user selected .venv/bin/python in the Command Palette.

**End — outcome and verification:** Strict Pyright reported zero diagnostics across all nine Python files. Black's check passed for enable_repo.py, Pylint errors-only passed across the repository, and full Pylint reported zero findings for the files represented by the Problems export after the follow-up fixes. The existing two complexity warnings in enable_repo.py remained; the Python test suite was not run as part of this toolchain setup.

**Future utility:** Future contributors can use one repository-local environment and matching strict analysis, formatting, and line-length settings instead of diagnosing different editor and CLI scopes.

**Project impact:** Observed: strict Pyright and the reported-file Pylint checks passed, and the selected Python interpreter and automatic formatter now match repository configuration. Expected: consistent formatting and analysis should reduce editor-versus-CLI drift.

**Rationale:** Future contributors can use one repository-local environment and matching strict analysis, formatting, and line-length settings instead of diagnosing different editor and CLI scopes.

**Impact:** Observed: strict Pyright and the reported-file Pylint checks passed, and the selected Python interpreter and automatic formatter now match repository configuration. Expected: consistent formatting and analysis should reduce editor-versus-CLI drift.

<!-- curatormd:record_id=742f9d864a1ccb614f4dd5d419942fa9;content_sha256=5139e2c1908629939ff830eb8f3f6fb0cfa34197717d89ab39e616ddec539834 -->
<!-- curatormd:fingerprint=b7bd06c6199e2e375f39704b4a99724a70941764feac42277bd34d54dd6a8ccd -->
