# Lessons learned

- A shared tool can live beside consumer repositories without making any consumer repository its system repository. Keep shared implementation ownership explicit and keep per-project state rooted in each consumer.
- Shared CuratorMD integrations must not default to a consumer profile or repository root. Require a project root/profile marker, write the matching profile into workspace settings, and keep native events and review state under that repository's ignored `.curatormd/` directory.
- Pyright's project `include` list can omit an open runtime module while Pylance still analyzes it under workspace strictness. Keep runtime modules explicitly included, choose checking mode for the module's data boundary, and narrow JSON objects once before accessing nested fields.

## Trust CuratorMD hooks to enable capture

**Date:** 2026-09-28

**Lesson:** ## Trust CuratorMD hooks to enable capture

**Beginning — trigger and context:** On September 28, the user reported that no CuratorMD reviews appeared despite substantial work in the CuratorMD repository the previous day. The repository inbox had no new event, and the scheduled 07:00 local curation run had completed with no writes because its only inbox item was an older duplicate.

**Middle — decisions and work:** The cause was checked in Codex's /hooks interface: the CuratorMD UserPromptSubmit and Stop hooks were installed but inactive because both new definitions awaited review and trust. The workspace being marked trusted did not approve plugin hooks. After reviewing the commands and bounded-capture implementation, both hooks were trusted through the local Codex hook review flow. A temporary-project check sent synthetic prompt and Stop events through the installed hook script; it produced one native inbox projection containing cue metadata and hashed references, with neither synthetic prompt nor response text stored.

**End — outcome and verification:** A fresh Codex /hooks view showed both events active. The temporary capture check passed and its workspace was removed; the real CuratorMD inbox was not used for that test. This root cause explains the missing September 27 capture; future hooks can capture only new qualifying turns and do not backfill old sessions. The original work was recovered as two pending review proposals.

**Future utility:** When a Codex plugin is installed but capture is stale, inspect /hooks and separately review/trust each plugin hook definition; repository trust alone is insufficient. Then verify both UserPromptSubmit and Stop are active.

**Project impact:** Observed: both previously inactive hooks now show active, and the installed script created a bounded test projection without storing prompt or response text. Expected: future qualifying Codex turns can reach the CuratorMD inbox. Existing sessions may need reload or a fresh Codex session before they use the updated hook trust state.

**Trigger / root cause:** When a Codex plugin is installed but capture is stale, inspect /hooks and separately review/trust each plugin hook definition; repository trust alone is insufficient. Then verify both UserPromptSubmit and Stop are active.

**Preventative rule:** Observed: both previously inactive hooks now show active, and the installed script created a bounded test projection without storing prompt or response text. Expected: future qualifying Codex turns can reach the CuratorMD inbox. Existing sessions may need reload or a fresh Codex session before they use the updated hook trust state.

<!-- curatormd:record_id=dc4f26fb04144a92db0cec7b4ddf576b;content_sha256=203324c5aa9b1e180ef208c4f07234520a613197a38caabc1b19a06ee7bf1462 -->
<!-- curatormd:fingerprint=dde871fba8c0468e2919c3d84600340a6f58606dca7304692f55e277b19482f7 -->
