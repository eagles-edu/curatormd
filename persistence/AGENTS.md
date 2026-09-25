# Active project rules

- Keep CuratorMD system knowledge in this repository; keep consumer knowledge in each consumer repository.
- Never mix project roots, Hermes profiles, native inboxes, runtime state, or persistence records across repositories.
- Never store credentials, tokens, private keys, connection strings, personal data, or raw prompts/responses in durable knowledge.
- Use an absolute Git worktree root with CuratorMD. Keep `.curatormd/` ignored and private.
- CuratorMD may produce review candidates but must not commit, push, deploy, migrate, delete project data, or modify consumer application source.
- Use the OpenAI developer documentation MCP server for OpenAI product, API, plugin, or Codex questions.
