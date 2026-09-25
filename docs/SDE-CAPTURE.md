# Significant Development Event capture

CuratorMD's bundled Codex hooks inspect each submitted user prompt and the
assistant's completed turn. Vocabulary matches are combined into one
`before`/`after` candidate in the active repository's ignored native inbox.
Review it with the normal CuratorMD pending-review flow; capture never approves
a candidate automatically.

## Trigger vocabulary

- **Decision:** decided, decision, tradeoff, chose, selected, rejected,
  deferred, accepted, design decision, chosen, will use.
- **Change:** add/added/addition, remove/removed/subtraction, implement,
  implementation, modernize, align, upgrade, improve, refactor, rewrite,
  migrate, deprecate, feature, dependency/dependencies.
- **Repair:** fix/fixed, repair/repaired, resolve/resolved, restore/restored,
  corrected, misconfiguration, regression, drift, rollback, hotfix,
  workaround.
- **Outcome:** failure/failed, incident, root cause, lesson learned, verified,
  breaking change, performance, security, data loss.
- **Risk:** destructive, deleted, overwritten, data loss, security issue,
  credential exposure, unsafe, breaking change.

These cues prompt human review; they do not assert that an SDE occurred. A
single SDE reference groups the before and after cues into one review candidate.

## Privacy and repository boundaries

The payload stores matched vocabulary and categories, a hashed SDE/session/turn
reference, and before/after cue summaries. It does not store prompt or response text, tool arguments,
or file paths. The review document shows the safe before/after cue JSON, the
CuratorMD proposal, and a separate editable decision block. Each hook requires
a valid local `.curatormd/project.json` marker
whose root is the current Git worktree and whose profile identifies that
repository. State remains under that repository's ignored `.curatormd/`
directory. Hook errors are swallowed so capture cannot block a coding turn.
Repository onboarding writes the marker even when `--no-scaffold` is selected,
and records the profile in workspace-level `.vscode/settings.json` so status
checks cannot silently use another repository's Hermes profile.

Codex asks the user to review and trust bundled plugin hooks in `/hooks` after
installation or update.
