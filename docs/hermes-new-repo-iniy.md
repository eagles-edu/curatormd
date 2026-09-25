# Hermes new-repository initialization

## MCP placement

Use one installation per runtime boundary:

| Layer | Configuration | Current state |
|---|---|---|
| Codex CLI and Codex IDE extension | Global Codex MCP configuration | `openaiDeveloperDocs` and `curatormd` enabled |
| Hermes | Per-profile Hermes configuration | the dedicated project profile has `openaiDeveloperDocs` and `curatormd` enabled |
| Repository | `AGENTS.md` and `persistence/` instructions | The Docs MCP usage rule is recorded here |

OpenAI Developer Docs MCP is a public, read-only server:
`https://developers.openai.com/mcp`. Codex CLI and its IDE extension share the
Codex MCP configuration, so it only needs to be added once to Codex. Hermes
profiles are separate, so each new profile must register it independently.

For a new repository, run:

```bash
python3 /home/eaglesvn/dockerz/curatormd/plugins/gptmd-memory/scripts/enable_repo.py \
  --project-root /absolute/path/to/new-repo \
  --profile newrepo-coding \
  --time 06:15
```

That command registers both `curatormd` and `openaiDeveloperDocs` in the new
Hermes profile. Complete the separate profile sign-in afterward:

```bash
hermes -p newrepo-coding model
hermes -p newrepo-coding status
hermes -p newrepo-coding mcp list
```

Use `--dry-run` first when reviewing a new repository. Do not put API keys in
this repository; the Docs MCP does not require authentication.

## Capability recommendations

The current application dependencies are Nuxt 4, Vue 3, Vue Router, and
Vuetify. The following items are not currently installed as project packages
or specialized local skills; treat them as a staged backlog rather than a
claim that they are already enabled.

| Area | Recommendation | Preferred boundary |
|---|---|---|
| TypeScript, Vue, Nuxt, Vuetify | Use the Nuxt/Vue toolchain already present; add strict TypeScript checks and project conventions next | Repository config and Codex/Hermes instructions |
| Unit/component testing | Vitest plus Vue Test Utils; add Playwright for browser/SSR flows | Repository dev dependencies and CI |
| ESLint | Nuxt ESLint integration with typed rules | Repository dev dependency and CI |
| SCSS/CSS | Stylelint with SCSS and property-order rules | Repository dev dependency and CI |
| HTML5 validation | `html-validate` for templates and generated markup where practical | Test script and CI |
| WebSockets | Add only if the app needs realtime behavior; test reconnect, auth, and backpressure | Application code plus integration tests |
| Express.js | Required as a separate service; keep its package, TypeScript build, port, and deployment boundary independent from Nuxt | `services/api/` |
| Redis Stack 7.x | Keep the verified local Compose stack; use `redis-cli` health checks and a narrow, read-only inspection tool if needed | Local infrastructure, never broad agent access |
| Python | Ruff, pytest, and pyright/mypy for Python utilities and services | Separate Python package/CI job |
| Kubernetes | Add manifests only when deployment requires it; validate with `kubectl`, Helm, and schema checks | Deployment repository/CI, not general MCP write access |
| CI/CD | GitHub Actions, build/test gates, actionlint, and secret scanning | CI; agents may inspect but should not deploy unattended |
| OLSWS, Nginx, Gunicorn | Keep host operations explicit and administrator-reviewed; use official docs, config tests, listener checks, and ACME verification | Host operations, not automatic MCP mutations |
| Git and Copilot | Git remains the source-control boundary; Copilot stays attended inline/terminal support | Human-reviewed workflow |
| SSR/SPA and test creation | Treat Nuxt SSR, client hydration, routing, accessibility, and browser tests as one acceptance surface | Vitest + Playwright + CI |

## Available skills

Currently available relevant skills include OpenAI Docs, frontend app
building, frontend testing/debugging, React/Next.js guidance, and general
plugin/skill management. There is not currently a dedicated installed skill
for every item in the table above. Prefer small repository-specific rules and
verified tooling over installing one broad “everything” skill.

Reference: [OpenAI Docs MCP](https://developers.openai.com/learn/docs-mcp).
