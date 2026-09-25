# Enable a new repository

Each repository gets its own Hermes profile, CuratorMD state boundary, observer,
and daily curator slot. Do not reuse `default` or another repository's profile.

Choose an unused local schedule time for each repository, such as `06:15` or `06:30`.

From this repository, run:

```bash
python3 plugins/gptmd-memory/scripts/enable_repo.py \
  --project-root /absolute/path/to/new-repo \
  --profile newrepo-coding \
  --time 06:15
```

The command:

- validates that the target is the Git worktree root;
- creates only missing `AGENTS.md` and `persistence/*.md` files;
- adds the ignored `.curatormd/` boundary;
- writes an ignored CuratorMD root/profile marker so bundled SDE hooks stay
  confined to this repository;
- binds the VS Code status extension to this repository's workspace profile
  and initializes its polling interval in workspace settings;
- creates the isolated Hermes profile;
- sets the Codex app-server runtime and `cron.max_parallel_jobs=1`;
- registers the local CuratorMD MCP server in that profile;
- installs the matching `gptmd-memory` and `curation-learning` Hermes skills in that profile;
- registers the public, read-only OpenAI Developer Docs MCP server;
- installs a project-bound, redacting Hermes observer;
- creates one no-agent daily CuratorMD job with an absolute workdir;
- never commits, pushes, deploys, migrates, deletes, or edits application source.

The `gptmd-memory` Codex plugin also captures bounded SDE vocabulary cues at
prompt submission and turn completion. It stores no prompt/response text. On
the first plugin update, inspect and trust the bundled hooks in Codex's `/hooks`
screen before relying on automatic capture.

Authentication is intentionally interactive and profile-specific:

```bash
hermes -p newrepo-coding model
hermes -p newrepo-coding status
hermes -p newrepo-coding mcp list
```

Select OpenAI Codex and complete its sign-in when prompted. Then inspect the
profile in the local dashboard:

```text
http://127.0.0.1:9119/cron?profile=newrepo-coding
```

Review the generated files and `git diff` in the new repository. Do not run the
daily job until the profile authentication and project root are correct.

For a preview without writes:

```bash
python3 plugins/gptmd-memory/scripts/enable_repo.py \
  --project-root /absolute/path/to/new-repo \
  --profile newrepo-coding \
  --time 06:15 \
  --dry-run
```
