---
name: enable-hermes-repo
description: Enable a Git repository as an isolated Hermes, Codex, and CuratorMD project with MCP, skills, hooks, scheduling, and verification.
---

# Enable a Hermes repository

Use this skill when a repository needs its own Hermes profile and project-scoped
CuratorMD integration. The target outcome is one isolated `codex_app_server`
profile, the CuratorMD and OpenAI Developer Docs MCP servers, the CuratorMD
skill, a redacted observer hook, and one serialized daily curation job.

Keep the workflow local and reviewable. Never read or record secrets, commit,
push, deploy, migrate, delete project data, or modify application source as
part of enablement.

## 1. Establish the repository boundary

Resolve the absolute Git worktree root before running CuratorMD or changing
configuration:

```bash
project_root="$(git rev-parse --show-toplevel)"
```

Read, in order:

- `$project_root/AGENTS.md`, if present
- `$project_root/persistence/AGENTS.md`, if present
- all four files under `$project_root/persistence/`, if present

Inspect `git status --short --branch` and preserve existing user changes.
CuratorMD requires a Git worktree containing `persistence/`; the enablement
script scaffolds missing contract and persistence files without overwriting
existing ones.

When `persistence/` already exists and the CuratorMD MCP is available, call
`persistence_status` and `memory_recall` with this absolute `project_root`
before non-trivial setup. If the MCP is not yet registered for the new
profile, perform the bootstrap first and make these calls during verification.

## 2. Inspect shared prerequisites

Check the current profile, MCP, and plugin state before installing anything:

```bash
hermes profile list
codex plugin list
```

The CuratorMD package is a Codex portable plugin identified by
`.codex-plugin/plugin.json`. Verify `gptmd-memory@personal` is installed and
enabled with `codex plugin list`. If the personal marketplace is absent, add
the trusted local or Git marketplace that contains the package, then install
and enable the plugin. Do not treat an unrecognized copy under
`~/.hermes/plugins/` as a valid Hermes-native plugin.

Use one profile per repository. Derive a lowercase profile such as
`<repository-name>-coding`; if that name already exists, verify its observer
hook, curation script, and cron workdir point to this same repository before
reusing it.

Choose a free daily local-time slot. Inspect every existing profile's jobs and
stagger repositories, for example `06:00`, `06:15`, and `06:30` in
`Asia/Ho_Chi_Minh`. Never silently move another repository's job.

## 3. Run the idempotent bootstrap

Use the tracked `enable_repo.py` from the CuratorMD plugin. When the current
repository does not contain the plugin source, resolve the installed plugin
cache and pass its `scripts/` directory explicitly as `--source-dir`.

Review the planned changes first:

```bash
python3 "$enable_script" \
  --project-root "$project_root" \
  --profile "$profile" \
  --time "$time" \
  --source-dir "$source_dir" \
  --dry-run
```

After checking the target and schedule, run the same command without
`--dry-run`. The bootstrap creates or reconciles:

- the repository contract and four persistence documents;
- the ignored `.curatormd/` boundary;
- the isolated Hermes profile using the OpenAI Codex provider;
- `model.openai_runtime = codex_app_server` and serialized cron execution;
- the `curatormd` stdio MCP server;
- the public, read-only `openaiDeveloperDocs` MCP server;
- a profile-bound redacted observer hook;
- a no-agent `gptmd-curatormd` job with the absolute repository workdir.

The script is idempotent. It must not create duplicate profiles, MCP entries,
hooks, or curation jobs.

## 4. Install the profile skill

Every enabled profile needs the CuratorMD skill in addition to the Codex
plugin. Install it from the reviewed repository source, or reuse the existing
installation when the profile already has it:

```bash
hermes -p "$profile" skills install \
  'https://raw.githubusercontent.com/eagles-edu/gptmd/main/plugins/gptmd-memory/skills/gptmd-memory/SKILL.md' \
  --category productivity --name gptmd-memory --yes
```

Use a reviewed raw URL or commit-specific source when reproducibility matters.
Do not install credentials or copy `.env` values into the repository.

## 5. Verify the live boundary

Run all of these checks against the new profile and absolute project root:

```bash
hermes profile show "$profile"
hermes -p "$profile" mcp list
hermes -p "$profile" mcp test curatormd
hermes -p "$profile" skills list --enabled-only
hermes -p "$profile" cron list --all
python3 "$source_dir/gptmd_memory.py" \
  --project-root "$project_root" --profile "$profile" status
python3 "$source_dir/gptmd_memory.py" \
  --project-root "$project_root" snapshot
```

Also call CuratorMD `persistence_status` and `memory_recall` with the absolute
root. Finish with `persistence_status`; report the four persistence files,
capture state, inbox count, and any uncommitted reviewable changes.

Confirm that the profile shows the Codex app-server runtime, both MCP servers
are enabled, CuratorMD discovers its seven tools, the skill is enabled, and
the cron job has the expected schedule and absolute workdir. Inspect the
generated hook and cron script to confirm the profile and project are bound
correctly.

If the repository uses the CuratorMD VS Code status extension, add the
profile-specific workspace setting while preserving existing JSON:

```json
"curatormdStatus.profile": "<profile>"
```

Reload VS Code after installing or updating the extension. A fresh profile may
show capture as degraded until a Hermes lifecycle event is observed; this is
separate from persistence-store health and must be reported clearly.

Run the repository's normal validation, such as `npm run build`, after the
enablement checks. Record existing warnings separately from enablement
failures. Finish by reporting changed files, live profile state, validation
results, and any degraded observer state. Leave all curation and repository
contract changes uncommitted for review.
