# Significant Development Event capture

CuratorMD's bundled Codex hooks inspect each submitted user prompt and the
assistant's completed turn. They retain only bounded vocabulary cues and
hashed references. Cue matches are alerts, not project facts, and never form a
candidate by themselves.

For a durable SDE, Hermes reads the full relevant thread and synthesizes one
complete proposal with `title`, `beginning`, `middle`, and `end`. The beginning
captures the trigger and context; the middle captures decisions and work; the
end captures the outcome and verification. Include `utility` to explain what
future work can reuse from the event, and `impact` to state the evidenced or
explicitly expected effect on project quality. Select an archive suggestion
using the routing rule below; rationale and follow-up are optional. Submit
that one object to `sde_parse` and review the resulting single proposal
normally. The MCP stores the bounded synthesis, scrubs secrets, and does not
store raw prompts, responses, tool arguments, or full transcripts.

## When an event is an SDE

Record an SDE when the full event contains a consequential, durable project
change or decision that future work will need to understand. Typical reasons
include:

- a feature, subsystem, interface, architecture, dependency, data, security,
  runtime, or configuration change;
- a design choice or trade-off that affects how the software works or how it
  should be changed later;
- a verified failure cause, regression, recovery, or prevention that changes
  future troubleshooting or project quality;
- a significant implementation, removal, modernization, or improvement with
  an explainable outcome, evidence, or remaining limit.

Do not create an SDE from a vocabulary match alone, routine agent lifecycle
events, ordinary searches or questions, formatting-only edits, or a transient
action with no lasting decision, behavior, risk, or project outcome. A small
change can qualify if its decision or effect matters later; a large diff does
not qualify by size alone. Incomplete or blocked work may qualify when the
cause, recovery, or unresolved decision is worth retaining; state what remains
unverified. Avoid repeating an existing durable entry unless this event adds a
material decision, evidence, or change.

Before submitting, state why the event is durable in its `utility` and what
quality or outcome effect is evidenced or expected in its `impact`. A keyword
or claim of significance is not sufficient evidence.

Choose the file by the question a future reader will bring:

- `persistence/AGENTS.md` (`agents`) is the active software, subsystem, and
  agent reference. It answers what the software is for, what features it has,
  how it operates, how it is used, and which settings and rules apply. Route
  SDEs about additions, removals, improvements, and other whole-software or
  subsystem changes here because they update that current reference.
- `persistence/SOP.md` (`sop`) contains repeatable procedures. Put an SDE here
  when its durable value is a sequence of steps someone should repeat.
- `persistence/HISTORY.md` (`history`) records dated decisions and outcomes.
  Put an SDE here when a future reader needs the chronology, but it does not
  primarily update the current software reference.
- `persistence/LESSONS-LEARNED.md` (`lessons`) records verified failure causes
  and prevention rules. Put an SDE here when its main future value is avoiding
  a known failure.

The human reviewer makes the final archive choice. Choose one canonical home
for each fact; a history entry may point readers to an updated software
reference when both chronology and current-state knowledge matter.

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

These cues prompt semantic review; they do not assert that an SDE occurred. A
single SDE reference groups before and after cues. Without a structured SDE
synthesis, the event remains cue-only and is not proposed for persistence.

## Privacy and repository boundaries

The hook payload stores matched vocabulary and categories plus hashed
SDE/session/turn references. It does not store prompt or response text or tool
arguments. The structured MCP candidate shows the parsed SDE fields and a
separate editable decision block. Each hook requires
a valid local `.curatormd/project.json` marker
whose root is the current Git worktree and whose profile identifies that
repository. State remains under that repository's ignored `.curatormd/`
directory. Hook errors are swallowed so capture cannot block a coding turn.
Repository onboarding writes the marker even when `--no-scaffold` is selected,
and records the profile in workspace-level `.vscode/settings.json` so status
checks cannot silently use another repository's Hermes profile.

Codex asks the user to review and trust bundled plugin hooks in `/hooks` after
installation or update.
