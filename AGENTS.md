# CuratorMD system repository contract

CuratorMD is a standalone Markdown curation system. This repository owns the shared CuratorMD plugin, capture hooks, status extension, documentation, and release source.

Consumer repositories remain independent projects. Never move, merge, or reinterpret a consumer repository's project root, profile, native inbox, state, or persistence as CuratorMD system data.

Read `persistence/AGENTS.md` and `persistence/SOP.md` before changing this repository. Durable CuratorMD system knowledge belongs in the four Markdown files under `persistence/`; `.curatormd/` is private ignored runtime state. Keep consumer project data inside that consumer's own root.

Always use the OpenAI developer documentation MCP server for OpenAI product, API, plugin, or Codex questions.

Start each development task with a concise problem summary and success
criteria, then complete troubleshooting, remediation plan, implementation,
testing, and completion in that order. Do not stop at an error: diagnose it,
continue safe repair, and report manual and automatic recovery paths if blocked.

For each durable SDE, review the full relevant thread and submit one complete
proposal with a beginning (trigger and context), middle (decisions and work),
and end (outcome and verification). Preserve substantive project details;
scrub secrets only. Never promote hook cue words into proposal prose.

When changing Python modules, keep the maintained source files in
`pyrightconfig.json` and run the project-level Pyright check. For dynamic JSON
boundaries, narrow values before nested access and set an explicit per-file
checking mode when strict inference is not appropriate.
