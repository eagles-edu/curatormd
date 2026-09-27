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
