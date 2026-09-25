# CuratorMD system repository contract

CuratorMD is a standalone Markdown curation system. This repository owns the shared CuratorMD plugin, capture hooks, status extension, documentation, and release source.

Consumer repositories remain independent projects. GPTMD is the medical-doctor application repository and is only a CuratorMD consumer. Never move, merge, or reinterpret a consumer repository's project root, profile, native inbox, state, or persistence as CuratorMD system data.

Read `persistence/AGENTS.md` and `persistence/SOP.md` before changing this repository. Durable CuratorMD system knowledge belongs in the four Markdown files under `persistence/`; `.curatormd/` is private ignored runtime state. Keep consumer project data inside that consumer's own root.

Always use the OpenAI developer documentation MCP server for OpenAI product, API, plugin, or Codex questions.
