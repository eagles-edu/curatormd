# CuratorMD Human-Guided Curation, Statistical Learning, and QA Validation Plan

## 1. Purpose

Extend CuratorMD from a lifecycle-event curator into a longitudinal, human-supervised decision system that learns which software-development events deserve durable project chronicle entries, how important those entries are, where they belong, and—over time—whether the human and AI assumptions behind those decisions are associated with measurable project quality outcomes.

The system must not merely learn:

> “What did the human approve?”

It must progressively distinguish three separate questions:

1. **Curation prediction**

   * Given the evidence available at review time, what is the human likely to approve, reject, prioritize, and archive?

2. **Proposal quality**

   * How accurately does CuratorMD anticipate the human's eventual decision, and is that accuracy improving over time?

3. **Project-quality validity**

   * Do the human's decisions, the AI's proposals, and disagreements between them correspond to later evidence that an event actually mattered to project quality, continuity, reliability, procedures, historical understanding, or prevention of repeated mistakes?

The initial system remains human-supervised.

Automation is introduced only after sufficient prospective evidence demonstrates that a category is stable and predictable.

The learning system must never silently redefine human preference as objective project quality.

---

# 2. Governing design principles

## 2.1 Evidence, proposal, decision, and outcome are different things

Maintain four independent layers:

```text
EVENT EVIDENCE
What actually happened.

        ↓

AI PROPOSAL
What CuratorMD recommends recording.

        ↓

HUMAN DECISION
What the reviewer actually decides.

        ↓

LATER QA / UTILITY OUTCOME
What subsequent project evidence says about whether the information mattered.
```

These layers must never be collapsed.

In particular:

```text
AI proposal != human label

human approval != objective QA benefit

AI confidence != statistical evidence

automatic decision != human label
```

---

## 2.2 The producer reports facts; CuratorMD evaluates importance

Codex/Hermes should provide structured evidence describing the event.

They should not authoritatively decide whether the event belongs in project history.

Good producer facts include:

```text
test failed
architecture changed
dependency changed
three tests failed
rollback occurred
decision was made
configuration changed
new procedure introduced
```

Producer fields such as:

```text
important=true
should_archive=true
priority=5
```

may be retained as audit metadata, but they must not automatically become Curator labels or regression outcomes.

---

## 2.3 Human review is the initial supervisory source

During human-learning phases, the human's finalized review becomes the supervised curation label.

Pending records are unlabeled.

Automatic decisions are not human labels.

---

## 2.4 Downstream project quality is a separate evidentiary layer

The system must later evaluate whether curation judgments remain useful when tested against observable future project behavior.

Examples include:

```text
repeat regressions
repeat incidents
rollback/revert
time to resolution
test failure recurrence
entry reuse
entry survival through compaction
procedure reuse
lesson reuse
supersession
manual retrospective usefulness
```

These outcomes must remain separate from original review labels.

---

## 2.5 Human review must be almost frictionless

CuratorMD performs the writing.

The human supplies judgment.

The normal workflow should therefore be:

```text
proposal correct
    -> select approved

proposal irrelevant
    -> select do-not-record

proposal mostly correct
    -> change one or two selections
    -> approve
```

The reviewer must not manually reconstruct metadata already known to the system.

---

## 2.6 Mathematical notation

Use inline LaTeX for short expressions, such as `$p_i=P(Y_i=1\mid X_i)$`. Use display equations for model definitions, derivations, and formulas that are easier to read on separate lines. Keep prose and short expressions inline so equations do not fragment the surrounding explanation.

# 3. Preserve the existing Hermes–Codex liaison architecture

The existing Hermes/Codex topology shown in the liaison diagram remains authoritative for transport and execution relationships.

This plan does not require redesigning that topology.

Instead, responsibilities are assigned at logical boundaries:

```text
CODEX
execution semantics and result evidence

        ↓

HERMES
capture, liaison, normalization, security boundary,
identity, fingerprinting, transport

        ↓

CURATORMD PLUGIN
curation, proposal generation, human review,
canonical persistence, learning, statistics,
QA linkage, reports, automation gates

        ↓

HUMAN
final curation judgment, corrections,
phase authorization, retrospective usefulness review
```

Where the existing liaison implementation already performs one of the responsibilities described below, extend the existing component rather than duplicating it.

CuratorMD should not become directly coupled to private Codex execution state if Hermes is already the liaison boundary.

---

# 4. Codex responsibilities

Codex is closest to the semantic meaning of the completed development operation.

Codex should therefore produce bounded structured evidence while it still possesses the complete execution context.

Codex responsibilities:

```text
execute development work
know the task intent
know the actual result
know whether tests passed or failed
know whether files/configuration/dependencies changed
know whether a fix was made
know whether a project decision occurred
know the unredacted final response before persistence redaction
produce a safe semantic summary before that information is lost
```

Codex must not:

```text
append canonical CuratorMD archives
create human labels
train CuratorMD statistical models
silently auto-approve chronicle entries
treat its own proposed importance as ground truth
```

---

# 5. Safe semantic summary requirement

The current payload contains:

```json
"response": "[REDACTED]"
```

Once the response has reached that state, CuratorMD cannot recover its semantic content.

Therefore a **safe semantic summary derived from the unredacted response must be produced before redaction**.

Required sequence:

```text
unredacted Codex execution/result
        |
        +----> structured result extraction
        |
        +----> bounded semantic summarization
        |
        +----> secret/privacy sanitization
        |
        +----> review_safe_summary
        |
        +----> raw response redaction
```

CuratorMD does not need the original unredacted response.

It needs the meaningful development result preserved safely.

---

# 6. Safe-summary requirements

The summary must preserve, where applicable:

```text
what was attempted
what was actually accomplished
important test result
important failure
important regression
important discovery
root cause
fix
persistent project change
architectural consequence
dependency consequence
configuration consequence
interface consequence
project decision
new procedure
unresolved issue
```

It should suppress routine narration such as:

```text
agent started
agent stopped
agent:end occurred
tool finished
session closed
```

unless that lifecycle behavior itself was the object of the test.

Recommended defaults:

```json
{
  "max_summary_chars": 1200,
  "max_summary_sentences": 6,
  "max_direct_quote_chars": 240
}
```

The summary may be shorter.

---

# 7. Summary sanitization

The safe-summary boundary must remove or replace:

```text
passwords
API keys
access tokens
refresh tokens
private keys
authorization headers
cookies
credential-bearing URLs
credential-bearing connection strings
secret environment variables
private secrets
unnecessary personal identifiers
unbounded logs
unbounded file contents
```

Replacement placeholders may include:

```text
[SECRET]
[TOKEN]
[CREDENTIAL]
[PRIVATE_VALUE]
[PRIVATE_PATH]
```

The safe summary itself may remain semantically unredacted with respect to ordinary project information.

For example, preserve:

> “The OAuth refresh path failed because token expiry was incorrectly calculated.”

rather than reducing it to:

> “[REDACTED] failed because [REDACTED].”

Only sensitive values should be removed.

---

# 8. Hermes responsibilities

Hermes owns the durable event-envelope and liaison/security boundary.

Hermes responsibilities include:

```text
capture lifecycle event
receive structured Codex result
receive safe semantic summary
validate event schema
validate enum values
sanitize again if necessary
redact raw response before persistence
assign or retain record_id
assign source_id
assign timestamp
assign cursor
assign fingerprint
identify provider/profile/model/platform/scope/session
deduplicate transport events
persist temporary inbox record
deliver event to CuratorMD
preserve schema version
```

Hermes should not decide:

```text
whether an event deserves recording
canonical archive
human priority
human disposition
future automation phase
```

---

# 9. Requested Hermes/Codex schema v3

Existing schema-v2 payloads remain readable.

New producers should emit schema v3.

```json
{
  "captured_at": "2026-09-23T11:04:12.204464Z",
  "cursor": "05d80ba2eb5de9200b7bb9ef205d1a7e",
  "event_type": "agent:end",

  "fingerprint": "a3c7b8f33c1c58f520a29d2a20920d79d4b4bb827b8d9f0eebe01d98b485a7d4",

  "payload": {
    "event": "agent:end",
    "iteration": null,
    "message": null,

    "model": "gpt-5.6-luna",
    "platform": "local",
    "profile": "consumer-coding",
    "provider": "openai-codex",
    "scope": "profile-bound",
    "session_id": "live-hook-test",

    "tool_names": [],

    "response": "[REDACTED]",

    "result": {
      "activity_class": "test",
      "status": "success",
      "result_class": "validation",

      "changed_project": false,
      "decision_made": false,

      "files_changed_count": 0,

      "configuration_changed": false,
      "dependency_changed": false,
      "interface_changed": false,
      "architecture_changed": false,
      "documentation_changed": false,
      "security_changed": false,
      "data_changed": false,

      "tests": {
        "executed": true,
        "passed": 1,
        "failed": 0,
        "skipped": 0
      },

      "error_count": 0,
      "failure_class": "none",

      "producer_tags": [
        "live-hook",
        "validation"
      ]
    },

    "review_safe_summary": {
      "text": "Completed the local live-hook validation successfully; no persistent project change was produced.",
      "status": "generated",
      "bounded": true,
      "sanitized": true,
      "generator": "openai-codex",
      "generator_version": "..."
    }
  },

  "project_root": "/path/to/consumer-repository",

  "record_id": "68b3db3f6a430b8f09e7917a6626ec81",

  "reviewed": false,

  "schema_version": 3,

  "source_id": "hermes:consumer-coding:live-hook-test:agent:end"
}
```

---

# 10. Producer activity taxonomy

## `activity_class`

```text
test
build
deploy
implementation
refactor
debug
configuration
dependency
migration
documentation
research
design
review
release
security
data
other
unknown
```

## `status`

```text
success
failure
partial
blocked
cancelled
unknown
```

## `result_class`

```text
routine
validation
change
fix
failure
discovery
decision
milestone
regression
artifact
unknown
```

## `failure_class`

```text
none
test
runtime
integration
configuration
dependency
data
security
regression
environment
unknown
```

Unknown producer values map to `unknown`, and statistical encoding may map unseen categories to `__OTHER__`.

Never dynamically create new statistical categories during inference.

---

# 11. Legacy payload behavior

For schema v2:

### Case A — response still available

Generate the safe summary before redaction.

### Case B — response already equals `[REDACTED]`

Do not hallucinate or reconstruct the response.

Use:

```json
{
  "review_safe_summary": {
    "text": null,
    "status": "unavailable",
    "bounded": true,
    "sanitized": true
  }
}
```

CuratorMD may still evaluate the available metadata.

Its statistical feature set must record:

```text
safe_summary_available = false
```

---

# 12. CuratorMD responsibilities

CuratorMD owns everything related to curation policy and learning.

Responsibilities:

```text
ingest Hermes records
normalize v2/v3 events
validate evidence
generate deterministic candidate
derive bounded features
run current statistical model in inference mode
show AI proposal separately from human decision
generate painless review block
persist pending edits
finalize human review
append approved Markdown idempotently
avoid persistence on rejection
write immutable learning observation
maintain rolling six-month learning dataset
recompute models every 21 days
evaluate model calibration and accuracy
evaluate user corrections versus AI proposals
link later QA outcomes
perform retrospective utility analysis
detect drift
manage automation phases
generate reports
```

---

# 13. Canonical archives

Allowed archive values:

```text
agents
sop
history
lessons
```

### `agents`

Stable knowledge concerning:

```text
agent/provider/profile capabilities
agent constraints
agent behavioral expectations
durable model/profile integration behavior
```

### `sop`

Repeatable practices:

```text
testing procedures
deployment procedures
validation procedures
recovery procedures
security procedures
review procedures
operating practices
```

### `history`

Chronological project knowledge:

```text
major decisions
architecture changes
migrations
releases
milestones
important implementation changes
important results
```

### `lessons`

Knowledge intended to prevent recurrence:

```text
failures
root causes
regressions
constraints
pitfalls
corrective practices
important fixes
```

Archive is nominal.

Do not encode:

```text
agents=1
sop=2
history=3
lessons=4
```

as an ordered regression variable.

---

# 14. Priority scale

Priority remains independent from disposition.

```text
0 = none
1 = low
2 = moderate
3 = high
4 = maximum
5 = highest importance
```

### 0 — none

No durable archival value.

### 1 — low

Minor contextual value. Safe future compaction candidate.

### 2 — moderate

Useful durable supporting information.

### 3 — high

Important result, decision, lesson, behavior, milestone, or project change.

### 4 — maximum

Major project-shaping information whose loss would materially impair future understanding or operation.

### 5 — highest importance

Foundational information whose loss could materially damage:

```text
project intent
architectural understanding
safety
critical operating procedure
critical historical interpretation
```

Priority `5` is the highest importance level and requires explicit human confirmation.

---

# 15. Disposition

Allowed:

```text
pending
approved
do-not-record
```

Meanings:

```text
pending
    review incomplete

approved
    append canonical entry and record human decision

do-not-record
    record human decision but do not change canonical archive
```

`pending` is missing outcome data.

It must never be encoded as `approved = 0`.

---

# 16. Curator-generated candidate

CuratorMD should construct:

```json
{
  "candidate": {
    "title": "Live-hook validation completed",

    "content": "2026-09-23 -- Provider openai-codex using profile-bound consumer-coding, deployed gpt-5.6-luna and performed local \"hermes:consumer-coding:live-hook-test:agent:end\": completed the live-hook validation successfully without a persistent project change (fingerprint: a3c7b8f33c1c58f520a29d2a209; record_id: 68b3db3f6a430b8f09e7917a6626ec81).",

    "utility": "Confirms that the profile-bound local live-hook path completed successfully.",

    "impact": "No persistent project behavior or architecture changed."
  }
}
```

The candidate must describe the meaningful result rather than merely repeating `agent:end`.

---

# 17. Canonical prose format

Use deterministic outer structure:

```text
YYYY-MM-DD -- Provider <provider> using <scope> <profile>,
deployed <model> and performed <platform> "<source_id>":
<safe meaningful event description>
(fingerprint: <short fingerprint>; record_id: <record_id>).
```

Additional details may appear inside the bounded event description.

---

# 18. Painless human review block

The review JSON must act like a multiple-choice form.

The generated `options` appear horizontally.

The human normally edits only `selected`.

```json
{
  "review": {
    "reviewed": false,

    "candidate": {
      "title": "Live-hook validation completed",
      "content": "2026-09-23 -- Provider openai-codex using profile-bound consumer-coding, deployed gpt-5.6-luna and performed local \"hermes:consumer-coding:live-hook-test:agent:end\": completed the live-hook validation successfully without a persistent project change.",
      "utility": "Confirms that the profile-bound local live-hook path completed successfully.",
      "impact": "No persistent project behavior or architecture changed."
    },

    "selection": {
      "disposition": {"selected":"pending","options":["pending","approved","do-not-record"]},

      "priority": {"selected":1,"options":["0:none","1:low","2:moderate","3:high","4:max","5:highest-importance"]},

      "archive": {"selected":"history","options":["agents","sop","history","lessons"]},

      "significance": {"selected":"minor","options":["none","minor","material","critical","unknown"]},

      "change_class": {"selected":"none","options":["none","implementation","configuration","architecture","dependency","interface","workflow","security","data","documentation","unknown"]},

      "review_reason": {"selected":"routine","options":["none","routine","duplicate","not-significant","important-result","decision","failure","lesson","milestone","other"]}
    },

    "human_edits": {
      "title": null,
      "content": null,
      "utility": null,
      "impact": null
    },

    "finalized_at": null
  }
}
```

---

# 19. Meaning of review options

Only `selection.*.selected` represents a human selection.

The `selection.*.options` arrays are interface metadata.

They are never treated as observed statistical values.

---

# 20. Mandatory versus optional review selections

Core human labels:

```text
disposition
priority
archive (for approved records only)
```

`archive` is required only for approved records.

CuratorMD preselects:

```text
priority
archive
significance
change_class
review_reason
```

The human changes only incorrect selections.

A correct proposal should normally require only:

```text
pending -> approved
```

A rejection should normally require only:

```text
pending -> do-not-record
```

Free-text rationale is never mandatory.

---

# 21. Human correction semantics

Suppose Curator proposes:

```text
priority = 1
archive = history
```

and the human selects:

```text
priority = 3
archive = lessons
disposition = approved
```

Store:

```json
{
  "ai_proposal": {
    "priority": 1,
    "archive": "history"
  },

  "human_final": {
    "disposition": "approved",
    "priority": 3,
    "archive": "lessons"
  },

  "corrections": {
    "priority_changed": true,
    "archive_changed": true
  }
}
```

The correction itself is sufficient learning evidence.

The human should not need to explain it.

---

# 22. Human text edits

If the user edits:

```text
title
content
utility
impact
```

retain both versions:

```json
{
  "ai_text": {
    "title": "...",
    "content": "...",
    "utility": "...",
    "impact": "..."
  },

  "human_text": {
    "title": "...",
    "content": "...",
    "utility": "...",
    "impact": "..."
  }
}
```

These differences are audit/proposal-quality evidence.

They are excluded from the initial regression feature matrix.

---

# 23. Review convenience metrics

Track:

```text
number of selections changed
number of text fields edited
review actions
proposal accepted unchanged
```

Define the unchanged approval rate inline as `$UAR = N_{\text{approved without corrections}} / N_{\text{approved}}$`.

Define mean corrections per review as `$MCR = N_{\text{corrected fields}} / N_{\text{finalized reviews}}$`.

Define the one-action rate as `$OAR = N_{\text{reviews requiring only a disposition change}} / N_{\text{finalized reviews}}$`.

Do not rely on elapsed review time by default because interruptions make it noisy.

---

# 24. Review state machine

Use explicit state:

```text
received
candidate-generated
pending-review
finalizing
approved
do-not-record
learning-recorded
```

A record is never considered permanently processed merely because a candidate was generated.

Pending records remain editable and reprocessable.

Malformed review data remains recoverable.

---

# 25. Review revision behavior

If a finalized human decision is corrected later, do not silently destroy the old label.

Create a revision:

```json
{
  "review_revision": 2,
  "supersedes_observation_id": "...",
  "active": true
}
```

Mark the prior observation:

```text
active = false
```

The training dataset uses the latest active human label.

The audit history retains both.

---

# 26. Markdown persistence

Approved entries append to the project’s canonical files:

```text
agents -> persistence/AGENTS.md
sop -> persistence/SOP.md
history -> persistence/HISTORY.md
lessons -> persistence/LESSONS-LEARNED.md
```

Do not commit automatically.

Use `record_id` for idempotency.

Recommended marker:

```html
<!-- curatormd:record_id=68b3db3f6a430b8f09e7917a6626ec81 -->
```

Before append:

```text
if record_id already present:
    do not append duplicate
```

---

# 27. Crash-safe review finalization

The review record, external learning store, and canonical Markdown files do not share a transaction manager. Do not describe writes across these files as one atomic transaction. Use a durable journal to make finalization recoverable and idempotent.

For each finalization, write a journal entry keyed by `record_id` and review revision. The entry contains the validated human decision, learning observation, target archive path, and expected Markdown entry. Persist it by writing a temporary file, flushing it, and atomically renaming it into the journal directory before applying either side effect.

Apply the journaled operations idempotently:

```text
validate human selection and candidate
persist final review and learning observation by stable observation_id
append approved Markdown only if record_id is absent
verify the learning observation; for approvals, verify the Markdown marker
mark the journal entry committed
```

On startup or retry, inspect uncommitted journal entries. If the archive marker is already present, treat the append as complete; if the observation already exists, verify it rather than duplicating it. Complete any missing operation; for a rejection, verify that no canonical archive changed. Then mark the journal committed. If recovery finds conflicting content for the same `record_id`, stop that record for human review and preserve the journal for diagnosis.

---

# 28. Learning-store separation

Learning state remains outside the repository.

Logical structure:

```text
CuratorMD external plugin state
    observations/
    models/
    reports/
    qa-outcomes/
    retrospective-audits/
```

Physical implementation should use the plugin's existing external state mechanism.

Do not introduce repository-tracked training files.

---

# 29. Active decision-data retention

At analysis time `$t$`, define the active learning dataset as:

$$
D_t =
\left\{
i :
t - 6\text{ months}
\leq t_i
\leq t
\right\}.
$$

Here `$t_i$` is the review timestamp for observation `$i$`.

The complete retained dataset must be recomputed every 21 days.

Do not rely on irreversible online-only coefficient updates.

---

# 30. Long-term aggregate metrics

Retain event-level decision records and their bounded QA linkage for at least nine months from the review timestamp. This leaves time for the 180-day outcome window and delayed retrospective review to mature.

The active model-training window remains six months. At nine months, an event-level record may be removed only after all configured QA windows and retrospective reviews have been finalized or marked unavailable. Non-sensitive aggregate longitudinal summaries may be retained longer, including:

```text
monthly Brier score
monthly log loss
monthly correction rate
monthly priority MAE
monthly archive accuracy
monthly QA rates
phase-transition metrics
```

This permits long-term improvement analysis without indefinitely retaining event-level learning content.

---

# 31. Statistical observation schema

Every finalized human review creates one active observation:

```json
{
  "schema_version": 1,

  "observation_id": "...",
  "record_id": "...",
  "review_revision": 1,

  "event_timestamp": "...",
  "proposal_timestamp": "...",
  "review_timestamp": "...",

  "features": {
    "event_type": "agent:end",
    "provider": "openai-codex",
    "profile": "consumer-coding",
    "model": "gpt-5.6-luna",
    "platform": "local",
    "scope": "profile-bound",

    "activity_class": "test",
    "status": "success",
    "result_class": "validation",
    "failure_class": "none",

    "changed_project": false,
    "decision_made": false,

    "tests_executed": true,
    "tests_failed": 0,

    "files_changed_count": 0,

    "configuration_changed": false,
    "dependency_changed": false,
    "interface_changed": false,
    "architecture_changed": false,

    "safe_summary_available": true,

    "same_class_30d": 4,
    "days_since_same_class": 5.2
  },

  "ai_proposal": {
    "disposition_probability": 0.12,
    "priority": 1,
    "archive": "history",
    "significance": "minor",
    "change_class": "none",
    "model_version": "..."
  },

  "human_final": {
    "disposition": "do-not-record",
    "priority": 0,
    "archive": null,
    "significance": "none",
    "change_class": "none",
    "review_reason": "routine"
  },

  "corrections": {
    "disposition_changed": true,
    "priority_changed": true,
    "archive_changed": null,
    "text_changed": false
  },

  "audit": {
    "review_source": "human",
    "producer_schema_version": 3,
    "feature_extractor_version": "1",
    "proposal_generator_version": "1"
  },

  "analysis_eligible": true,
  "archive_analysis_eligible": false,
  "active": true
}
```

---

# 32. Training eligibility

A human-reviewed record is eligible for disposition and priority learning only when `review_source = human`, `disposition ∈ {approved, do-not-record}`, and `active = true`. Archive learning is conditional on approval: train and evaluate the archive model only on approved records with a finalized archive label. For rejected records, archive and archive correction are not applicable; store them as `null` or exclude them from archive metrics, never as a category or a negative label.

Exclude:

```text
pending records
malformed records
machine-only decisions
superseded review revisions
```

---

# 33. Predictor/label separation

For observation `$i$`, let `$X_i$` contain only information legitimately available before human review.

Let `$Y_i$` contain the human decision observed after review.

The leakage-prevention rule is:

$$
X_i \not\supset Y_i.
$$

Examples of prohibited leakage:

```text
review_reason -> approval predictor for the same review
human-edited significance -> approval predictor for the same review
human archive correction -> archive predictor for the same review
retrospective usefulness -> original approval predictor
```

Those values may serve as outcomes or features for later, separately defined models.

---

# 34. Initial regression feature policy

Eligible predictors include bounded structured metadata:

```text
event_type
provider
profile
model family
platform
scope
activity_class
status
result_class
failure_class
changed_project
decision_made
configuration_changed
dependency_changed
interface_changed
architecture_changed
documentation_changed
security_changed
data_changed
tests_executed
tests_failed
files_changed_count
tool_count
safe_summary_available
```

---

# 35. Historical frequency features

CuratorMD may derive features using only information existing before the current event:

```text
same event-class count in previous 7 days
same event-class count in previous 30 days
same result-class count in previous 30 days
days since last same class
first occurrence indicator
known category indicator
recent failure frequency
recent regression frequency
```

For event `$i$`, never calculate these using events after `$i$`.

---

# 36. Count transformations

For non-negative count `$x$`, a deterministic transform may be:

$$
x' = \log(1+x).
$$

Alternatively use predefined buckets:

```text
0
1
2-5
6-20
21+
```

The transformation must be serialized in the model bundle and applied identically during training and inference.

---

# 37. Categorical feature encoding

Use deterministic one-hot encoding:

```text
activity_class.test
activity_class.debug
activity_class.deploy

result_class.routine
result_class.validation
result_class.failure

architecture_changed.true
```

Requirements:

```text
stable lexical column ordering
persisted vocabulary
fixed reference convention
unseen values -> __OTHER__
no inference-time vocabulary expansion
```

An unseen high-impact category causes automation abstention.

---

# 38. Free-text feature policy

Initial predictive models must not use:

```text
raw response
safe-summary text
candidate title
candidate content
candidate utility
candidate impact
human text
LLM embeddings
sentiment
arbitrary language-model importance scores
```

The prose remains evidence for human review.

A future text-model experiment must be separate, versioned, shadow-mode first, and prospectively evaluated before affecting automation.

---

# 39. Model family overview

The initial statistical system uses three distinct response models:

```text
Approval model
Priority model
Archive model
```

They must not be collapsed into one arbitrary score.

---

# 40. Approval model

Define the human approval outcome:

$$
Y_i^{(A)}
=
\begin{cases}
1, & \text{approved},\\
0, & \text{do-not-record}.
\end{cases}
$$

Pending reviews have no value of `$Y_i^{(A)}$`.

The approval model estimates `$p_i=P(Y_i^{(A)}=1\mid X_i)$`.

Use L2-regularized logistic regression:

$$
p_i =
\frac{1}{
1+\exp\left[-\left(\beta_0+\beta^\top X_i\right)\right]
}.
$$

Equivalently:

$$
\operatorname{logit}(p_i)
=
\log\left(\frac{p_i}{1-p_i}\right)
=
\beta_0+\beta^\top X_i.
$$

---

# 41. Logistic regularization

Estimate:

$$
\hat{\beta}
=
\arg\min_{\beta}
\left[
-\ell(\beta)
+
\lambda\sum_{j=1}^{p}\beta_j^2
\right].
$$

The logistic log-likelihood is:

$$
\ell(\beta)
=
\sum_{i=1}^{n}
\left[
y_i\log(p_i)
+
(1-y_i)\log(1-p_i)
\right].
$$

The intercept should normally remain unpenalized.

Initial configuration:

```json
{
  "regularization": "l2",
  "lambda": 1.0
}
```

Regularization is preferred because the six-month dataset may remain relatively small compared with the number of categorical predictors.

---

# 42. Logistic implementation

Define the sigmoid:

$$
\sigma(z)=\frac{1}{1+e^{-z}}.
$$

For design matrix `$X$`, let `$p=\sigma(X\beta)$` and:

$$
W=\operatorname{diag}\left(p_i(1-p_i)\right).
$$

A regularized Newton/IRLS update may use:

$$
\beta_{\text{new}}
=
\beta_{\text{old}}
+
\left(X^\top W X+\lambda I\right)^{-1}
\left[
X^\top(y-p)-\lambda\beta_{\text{old}}
\right].
$$

The penalty matrix must exclude the intercept when the intercept is unregularized.

Implementation requirements:

```text
fixed convergence tolerance
fixed maximum iterations
stable feature ordering
stable solver
no random initialization
deterministic serialization
```

---

# 43. Sparse-category partial pooling

When sufficient implementation maturity exists, category-specific effects may use a deterministic hierarchical/MAP extension such as:

$$
\beta_g \sim \mathcal{N}(\mu,\tau^2).
$$

This yields partial pooling:

```text
large well-supported category
    -> estimate primarily driven by own data

small sparse category
    -> estimate shrunk toward population behavior
```

Until implemented and validated, use regularized fixed effects plus explicit sparse-category abstention.

---

# 44. Approval output

Return:

```json
{
  "approval_probability": 0.14,

  "approval_interval": {
    "lower": 0.06,
    "upper": 0.29
  }
}
```

Interpret this as the estimated probability that the human reviewer would approve an event with these structured features.

Do not describe it as “14% importance.”

---

# 45. Priority model

Priority is ordered as `$0<1<2<3<4<5$`, but the distances between levels are not assumed equal.

Use a regularized proportional-odds ordinal logistic model:

$$
P\left(Y_i^{(P)}\leq k\mid X_i\right)
=
\sigma\left(\theta_k-\beta^\top X_i\right),
\qquad k=0,\ldots,4.
$$

Require:

$$
\theta_0<\theta_1<\theta_2<\theta_3<\theta_4.
$$

---

# 46. Ordered-threshold implementation

Guarantee ordered thresholds with:

$$
\theta_0=a_0
$$

and, for `$k\geq1$`:

$$
\theta_k
=
\theta_{k-1}
+
\exp(\delta_k).
$$

Since `$\exp(\delta_k)>0$`, thresholds remain strictly increasing.

---

# 47. Priority-category probabilities

Let:

$$
F_k(X)
=
P\left(Y^{(P)}\leq k\mid X\right).
$$

Then:

$$
P(Y^{(P)}=0\mid X)=F_0(X),
$$

for `$k=1,\ldots,4$`:

$$
P(Y^{(P)}=k\mid X)
=
F_k(X)-F_{k-1}(X),
$$

and:

$$
P(Y^{(P)}=5\mid X)
=
1-F_4(X).
$$

The probabilities must satisfy:

$$
\sum_{k=0}^{5}
P(Y^{(P)}=k\mid X)
=
1.
$$

---

# 48. Expected priority

Compute the advisory expected priority as:

$$
E[Y^{(P)}\mid X]
=
\sum_{k=0}^{5}
k\,P(Y^{(P)}=k\mid X).
$$

Return the full probability distribution as the primary result:

```json
{
  "priority_probabilities": {
    "0": 0.08,
    "1": 0.39,
    "2": 0.32,
    "3": 0.15,
    "4": 0.05,
    "5": 0.01
  },

  "expected_priority": 1.52
}
```

---

# 49. Proportional-odds diagnostic

The proportional-odds assumption must not be treated as permanently true.

Periodically compare threshold-specific cumulative binary behavior.

If feature effects vary materially across thresholds:

```text
flag ordinal-model-assumption warning
reduce automation confidence
```

Do not silently replace the model with a more complex one without separate implementation, testing, versioning, and prospective validation.

---

# 50. Archive model

For approved events:

$$
Y_i^{(R)}
\in
\{
\text{agents},
\text{sop},
\text{history},
\text{lessons}
\}.
$$

Use L2-regularized multinomial logistic regression:

$$
P(Y^{(R)}=j\mid X)
=
\frac{
\exp(\beta_j^\top X)
}{
\sum_{m=1}^{K}\exp(\beta_m^\top X)
},
\qquad K=4.
$$

---

# 51. Numerically stable softmax

Let `$z_j=\beta_j^\top X$` and define:

$$
z'_j=z_j-\max_m z_m.
$$

Then:

$$
P(Y^{(R)}=j\mid X)
=
\frac{e^{z'_j}}{\sum_m e^{z'_m}}.
$$

This preserves probabilities while reducing overflow risk.

---

# 52. Archive output

Example:

```json
{
  "archive_probabilities": {
    "agents": 0.05,
    "sop": 0.11,
    "history": 0.71,
    "lessons": 0.13
  }
}
```

Store:

```text
top archive
top probability
runner-up probability
probability margin
```

These probabilities estimate the archive conditional on an approved disposition. Do not assign or score a human archive label for a rejected record.

Do not automate archive selection merely because one class has the highest probability.

---

# 53. Pre-review prediction snapshot

Immediately before the human sees the proposal, persist an immutable `prediction_snapshot` containing:

```text
model version
feature extractor version
feature vector hash
approval probability
priority probabilities
archive probabilities
candidate priority
candidate archive
candidate text hash
timestamp
```

The snapshot must never be overwritten after human review.

This is the only legitimate basis for historical claims about how well the AI predicted the decision.

---

# 54. No retrospective prediction inflation

After retraining, do not rerun the improved model over old observations and call those fitted values historical prediction accuracy.

Distinguish:

```text
in-sample fitted value
```

from:

```text
prospective pre-review prediction
```

Only prospective predictions measure operational predictive performance.

---

# 55. Temporal/prequential evaluation

For review event `$t$`, define the available training data as:

$$
\mathcal{D}^{\text{train}}_t
=
\{i:t_i<t\}.
$$

Fit:

$$
M_t
=
Train\left(\mathcal{D}^{\text{train}}_t\right).
$$

Then predict:

$$
\hat{Y}_t=M_t(X_t)
$$

before observing `$Y_t$`.

The valid direction is always:

```text
past -> future
```

never:

```text
future -> past
```

Use rolling-origin/prequential evaluation rather than random-only train/test splitting.

---

# 56. Recompute cycle

Every 21 days:

1. Load active observations.
2. Expire observations outside the six-month window.
3. Resolve review revisions.
4. Validate schemas.
5. Exclude ineligible observations.
6. Construct deterministic vocabulary.
7. Construct features using past-only transformations.
8. Fit approval model.
9. Fit priority model.
10. Fit archive model.
11. Run temporal validation.
12. Calculate performance metrics.
13. Calculate calibration metrics.
14. Calculate category support.
15. Calculate uncertainty.
16. Calculate human-correction metrics.
17. Calculate drift metrics.
18. Link available QA outcomes.
19. Evaluate automation eligibility.
20. Persist model bundle.
21. Generate report.

Support manual recomputation.

---

# 57. Approval-model log loss

For `$n$` prospective predictions:

$$
LogLoss
=
-\frac{1}{n}
\sum_{i=1}^{n}
\left[
y_i\log(p_i)
+
(1-y_i)\log(1-p_i)
\right].
$$

Lower is better.

---

# 58. Brier score

$$
Brier
=
\frac{1}{n}
\sum_{i=1}^{n}
(p_i-y_i)^2.
$$

Lower is better.

---

# 59. Classification metrics

Use:

$$
Accuracy
=
\frac{TP+TN}{TP+TN+FP+FN}.
$$

$$
Precision
=
\frac{TP}{TP+FP}.
$$

$$
Recall
=
\frac{TP}{TP+FN}.
$$

$$
Specificity
=
\frac{TN}{TN+FP}.
$$

$$
NPV
=
\frac{TN}{TN+FN}.
$$

Accuracy must remain secondary when class imbalance is substantial.

Also report PR-AUC when useful and ROC-AUC as a secondary discrimination measure.

---

# 60. Calibration

Probability calibration matters because automation depends on probabilities rather than ranking alone.

For prospective probability `$\hat p_i$`, define:

$$
\hat{\eta}_i
=
\log\left(
\frac{\hat p_i}{1-\hat p_i}
\right).
$$

Fit:

$$
\operatorname{logit}\left[P(Y_i=1)\right]
=
\alpha+\beta_{\text{cal}}\hat{\eta}_i.
$$

Ideal calibration is approximately `$\alpha=0$` and `$\beta_{\text{cal}}=1$`.

Report:

```text
calibration intercept
calibration slope
reliability table
Brier score
log loss
```

With enough observations, provide a reliability diagram.

---

# 61. Priority performance

For predicted priority `$\hat P_i$` and human priority `$P_i$`, define:

$$
MAE_P
=
\frac{1}{n}
\sum_{i=1}^{n}
|\hat P_i-P_i|.
$$

Define signed error:

$$
e_i=\hat P_i-P_i.
$$

Then:

$$
Bias_P
=
\frac{1}{n}
\sum_{i=1}^{n}e_i.
$$

`$Bias_P>0$` indicates systematic over-prioritization.

`$Bias_P<0$` indicates systematic under-prioritization.

Also report exact-match rate, median absolute error, weighted agreement, confusion matrix, and:

$$
Within1
=
\frac{1}{n}
\sum_{i=1}^{n}
I(|\hat P_i-P_i|\leq1).
$$

---

# 62. Archive performance

Report:

```text
exact accuracy
multiclass log loss
macro F1
per-archive precision
per-archive recall
confusion matrix
top-two probability margin
```

Interpret sparse-category metrics cautiously.

---

# 63. Measuring human changes versus AI proposals

For event `$i$`, define the disposition correction indicator:

$$
C_{D,i}
=
I(H_{D,i}\neq A_{D,i}).
$$

Define signed priority correction:

$$
\Delta_{P,i}
=
H_{P,i}-A_{P,i}.
$$

If `$\Delta_{P,i}>0$`, the human increased importance.

If `$\Delta_{P,i}<0$`, the human decreased importance.

Define absolute priority correction:

$$
|\Delta_{P,i}|
=
|H_{P,i}-A_{P,i}|.
$$

Define archive correction only for approved records with a finalized human archive label:

$$
C_{R,i}
=
I(H_{R,i}\neq A_{R,i}).
$$

This definition applies only to approved records with a finalized human archive label. Rejected records have no archive label; exclude them from archive-model training, evaluation, and correction-rate denominators.

Define significance correction:

$$
C_{S,i}
=
I(H_{S,i}\neq A_{S,i}).
$$

Define change-class correction:

$$
C_{C,i}
=
I(H_{C,i}\neq A_{C,i}).
$$

---

# 64. Proposal-correction rates

Disposition correction rate:

$$
CorrectionRate_D
=
\frac{
\sum_{i=1}^{n}C_{D,i}
}{
n
}.
$$

Priority correction rate:

$$
CorrectionRate_P
=
\frac{
\sum_{i=1}^{n}
I(H_{P,i}\neq A_{P,i})
}{
n
}.
$$

For approved reviews with a finalized human archive label, where `$n_R$` is the number of such reviews:

$$
CorrectionRate_R
=
\frac{
\sum_i I(H_{R,i}\neq A_{R,i})
}{
n_R
}.
$$

Report these over rolling windows and by supported event categories.

---

# 65. AI proposal accuracy improvement over time

Historical performance must use predictions actually issued at the time.

Track rolling 21-day, 63-day, and 180-day metrics when sample size allows.

Primary trend metrics:

```text
approval log loss
approval Brier score
approval calibration
false-rejection rate
priority MAE
archive log loss
archive accuracy
human correction rate
one-action review rate
```

Improvement means:

```text
lower log loss
lower Brier score
better calibration
lower false-rejection rate
lower priority MAE
lower correction rate
higher one-action review rate
```

It does not mean merely producing more extreme probabilities.

---

# 66. Champion/challenger model comparison

When a new model is produced:

```text
current active model = champion
new candidate model = challenger
```

For subsequent human-reviewed events, produce frozen predictions from both.

Only the champion controls the visible proposal unless configured otherwise.

Compare both models on the same prospective observations.

For observation `$i$`, define the paired log-loss difference:

$$
\Delta L_i
=
L_i^{(C)}-L_i^{(M)}.
$$

Here:

$$
L_i
=
-\left[
y_i\log(p_i)
+
(1-y_i)\log(1-p_i)
\right].
$$

If `$\Delta L_i<0$`, the challenger predicted that observation better.

Average paired difference:

$$
\overline{\Delta L}
=
\frac{1}{n}
\sum_{i=1}^{n}\Delta L_i.
$$

If `$\overline{\Delta L}<0$`, the challenger has lower average prospective log loss.

---

# 67. Paired priority comparison

For challenger `$C$` and champion `$M$`:

$$
\Delta E_i
=
|\hat P_i^{(C)}-P_i|
-
|\hat P_i^{(M)}-P_i|.
$$

If `$\Delta E_i<0$`, the challenger had the smaller priority error.

Hard binary decisions may additionally use a paired McNemar-style comparison.

---

# 68. Category-level empirical evidence

For a category with `$x$` approvals among `$n$` reviewed observations:

$$
\hat p=\frac{x}{n}.
$$

Use a Wilson interval rather than a simple normal approximation for sparse categories.

Define:

$$
C
=
\frac{
\hat p+\frac{z^2}{2n}
}{
1+\frac{z^2}{n}
}
$$

and:

$$
H
=
\frac{
z
}{
1+\frac{z^2}{n}
}
\sqrt{
\frac{\hat p(1-\hat p)}{n}
+
\frac{z^2}{4n^2}
}.
$$

Then:

$$
CI_{\text{Wilson}}
=
[C-H,\;C+H].
$$

For a nominal 95% interval, use `$z\approx1.96$`.

---

# 69. Model prediction uncertainty

For a new feature vector `$x$`, define the logistic linear predictor:

$$
\eta=x^\top\hat\beta.
$$

Approximate coefficient covariance with:

$$
\Sigma_{\hat\beta}
\approx
(X^\top W X+\lambda I)^{-1},
$$

subject to correct handling of the unpenalized intercept.

Prediction variance is:

$$
\operatorname{Var}(\eta)
=
x^\top\Sigma_{\hat\beta}x.
$$

Thus:

$$
SE_\eta
=
\sqrt{x^\top\Sigma_{\hat\beta}x}.
$$

For confidence multiplier `$z_\alpha$`:

$$
\eta_L
=
\eta-z_\alpha SE_\eta,
\qquad
\eta_U
=
\eta+z_\alpha SE_\eta.
$$

Convert back to probabilities:

$$
p_L=\sigma(\eta_L),
\qquad
p_U=\sigma(\eta_U).
$$

For approximate 95% bounds, use `$z_\alpha\approx1.96$`.

---

# 70. Abstention

The statistical system must be allowed to say:

```text
insufficient evidence
```

Automation is prohibited when:

```text
new feature category
sparse category
model not calibrated
large prediction interval
drift warning
producer evidence incomplete
safe summary unavailable
model version not prospectively validated
```

Abstention is preferable to false certainty.

---

# 71. Concept drift

Monitor:

```text
recent approval rate vs older approval rate
recent correction rate vs older correction rate
recent log loss vs older log loss
recent Brier score vs older Brier score
recent priority MAE
feature/category distribution shifts
```

For recent rate `$\hat p_R$` and historical rate `$\hat p_H$`, define:

$$
\Delta p
=
\hat p_R-\hat p_H.
$$

For a loss measure `$L$`:

$$
\Delta L
=
L_{\text{recent}}
-
L_{\text{historical}}.
$$

For metrics where lower is better, `$\Delta L>0$` indicates deterioration.

A meaningful deterioration generates:

```text
drift_warning = true
```

Affected categories return to human-only review.

---

# 72. Automation phases

## Phase 0 — instrumentation

Behavior:

```text
capture schema-v3 events
capture safe summaries
generate proposals
collect human labels
record prediction snapshots
record corrections
no automation
```

---

# 73. Phase 1 — human-only learning

Behavior:

```text
fit models
show predictions
show suggested priority
show suggested archive
show uncertainty
require human final disposition
```

No automatic approval.

No automatic rejection.

The first six months remain human-review-only for automation purposes.

---

# 74. Phase 2 — conservative auto-rejection

Disabled by default.

A record may be automatically rejected only when all evidence gates pass.

The model-level condition is:

$$
p_U<T_{\text{reject}}.
$$

The empirical category condition is:

$$
WilsonUpper<T_{\text{reject}}.
$$

Example starting threshold:

```json
{
  "auto_reject": {
    "enabled": false,
    "approval_upper_bound_threshold": 0.05
  }
}
```

A low point estimate alone is insufficient if uncertainty is broad.

---

# 75. Phase-2 false-rejection metric

The critical safety quantity is:

$$
FalseRejectRate
=
P(HumanApprove\mid AutoReject).
$$

Under human audit:

$$
FalseRejectRate
=
\frac{
N(AutoReject\cap HumanApprove)
}{
N(AutoReject\ \text{audited by human})
}.
$$

This matters more than ordinary overall accuracy.

---

# 76. Phase 3 — optional auto-approval

Implemented but disabled by default.

Require explicit operator configuration.

Model-level condition:

$$
p_L>T_{\text{approve}}.
$$

Empirical category condition:

$$
WilsonLower>T_{\text{approve}}.
$$

Example:

```json
{
  "auto_approve": {
    "enabled": false,
    "approval_lower_bound_threshold": 0.95
  }
}
```

Also require:

```text
archive confidence sufficient
priority confidence sufficient
no drift warning
adequate category support
recent human audit evidence
```

Priority 5 remains human-confirmed unless explicitly changed by later configuration.

---

# 77. Evidence gate

Initial configurable gate:

```json
{
  "evidence_gate": {
    "minimum_history_days": 180,
    "minimum_reviewed_examples": 30,
    "minimum_recent_examples": 10,
    "confidence_level": 0.95,
    "require_temporal_validation": true,
    "require_calibration": true,
    "require_no_drift_warning": true,
    "require_human_audit_stream": true
  }
}
```

These are policy defaults rather than universal statistical laws.

The report must state exactly which condition prevents automation.

---

# 78. Automatic decisions must not become human labels

Store automatic decisions distinctly:

```json
{
  "review_source": "automatic",
  "analysis_eligible_as_human_label": false
}
```

Otherwise the model can create a self-confirming feedback loop:

```text
model predicts rejection
    ->
machine writes rejection
    ->
next model treats machine rejection as truth
    ->
confidence increases
    ->
model appears to prove itself
```

This is prohibited.

---

# 79. Mandatory human audit stream

After automation begins, deterministic human auditing must continue.

Example:

```text
hash(record_id) mod 10 == 0
```

selects approximately 10% of otherwise automatable records.

Configuration:

```json
{
  "automation_audit": {
    "enabled": true,
    "bucket_modulus": 10,
    "human_review_bucket": 0
  }
}
```

Only human-confirmed audit outcomes become new supervised labels.

---

# 80. Routine lifecycle suppression

Lifecycle events such as:

```text
agent:end
tool:end
test:end
```

should not automatically become durable history.

Examples:

```text
routine successful validation
+ no change
+ no decision
    -> likely priority 0-1

test completion
+ material regression discovered
    -> potentially lessons/history

agent:end
+ architecture changed
    -> potentially priority 3-4 history

debug completion
+ root cause + prevention procedure
    -> potentially lessons/sop
```

The event type itself is weak evidence.

---

# 81. Deterministic pre-model heuristics

Before sufficient learning data exists:

```text
routine success + no persistent change + no decision
    -> priority 0-1

important failure without durable lesson
    -> priority 1-2

root cause identified
    -> priority 2-3 lessons

persistent implementation change
    -> priority 2-3 history

new repeatable procedure
    -> sop

architectural decision
    -> priority 3-4 history

foundational project constraint
    -> priority 4 suggestion
    -> priority 5 only after human confirmation
```

These are proposals, not human labels.

---

# 82. Statistical proposal integration

Do not simply replace deterministic recommendations with the maximum-probability statistical output.

Expose the evidence:

```json
{
  "analysis": {
    "approval_probability": 0.12,
    "approval_interval": [0.04, 0.27],

    "priority_probabilities": {
      "0": 0.31,
      "1": 0.46,
      "2": 0.16,
      "3": 0.05,
      "4": 0.02,
      "5": 0.00
    },

    "expected_priority": 1.03,

    "archive_probabilities": {
      "agents": 0.05,
      "sop": 0.08,
      "history": 0.72,
      "lessons": 0.15
    },

    "learning_phase": "PHASE_1_HUMAN_REVIEW"
  }
}
```

---

# 83. Project-QA outcome layer

Curation accuracy alone does not establish project benefit.

Create a separate downstream-outcome layer.

Potential observable outcomes:

```text
same regression reappeared
similar failure reappeared
same configuration mistake repeated
rollback/revert occurred
hotfix required
test-failure count
time to resolve related failure
repeated incident count
same lesson referenced
same SOP referenced
canonical entry retrieved
canonical entry cited by later work
entry retained through compaction
entry superseded
entry marked obsolete
```

---

# 84. QA outcome windows

Use fixed prospective windows when practical:

```text
30 days
60 days
90 days
180 days
```

Potential variables:

```text
repeat_failure_30d
repeat_failure_90d
regression_count_90d
rollback_30d
time_to_related_resolution
entry_reference_count_90d
retained_at_180d
superseded_by_180d
```

Future outcomes must never be inserted retroactively into the original pre-review feature vector.

---

# 85. QA denominator controls

Raw counts are misleading when development activity changes.

Normalize appropriate quantities.

For example:

$$
RegressionRate
=
\frac{
N_{\text{regressions}}
}{
N_{\text{relevant development changes}}
}.
$$

Similarly:

$$
RollbackRate
=
\frac{
N_{\text{rollbacks}}
}{
N_{\text{relevant deployments or changes}}
}.
$$

Use denominators such as:

```text
tasks completed
test runs
deployments
changesets
agent sessions
release count
```

where appropriate.

---

# 86. Retrospective human utility audit

Some significance cannot be inferred objectively.

At 90 or 180 days, sample prior reviews and show:

```text
original event
original AI proposal
original human decision
available subsequent QA evidence
```

Ask bounded questions:

```json
{
  "retrospective_review": {
    "still_correct": {
      "selected": "yes",
      "options": ["yes","no","uncertain"]
    },

    "usefulness": {
      "selected": 2,
      "options": ["0:none","1:limited","2:useful","3:high","4:critical"]
    },

    "germane": {
      "selected": "yes",
      "options": ["yes","superseded","obsolete","uncertain"]
    }
  }
}
```

Rejected records may ask:

```json
{
  "should_have_recorded": {
    "selected": "no",
    "options": ["yes","no","uncertain"]
  }
}
```

Use sampling so retrospective review remains lightweight.

---

# 87. Human-versus-AI assumption matrix

Classify original disposition proposals into:

```text
AI approve / Human approve
AI approve / Human reject
AI reject  / Human approve
AI reject  / Human reject
```

The disagreement cells are especially informative.

Compare later outcomes across these groups:

```text
retrospective usefulness
repeat regression
repeat failure
entry reuse
rollback
retention
supersession
```

---

# 88. Override benefit

For observations with `$AI_i\neq Human_i$`, later evidence may resolve the disagreement as:

```text
supports_human
supports_ai
indeterminate
```

Define:

$$
HumanOverrideSupportRate
=
\frac{
N_{\text{supports human}}
}{
N_{\text{resolvable disagreements}}
}.
$$

Define:

$$
AISupportRate
=
\frac{
N_{\text{supports AI}}
}{
N_{\text{resolvable disagreements}}
}.
$$

Indeterminate cases are excluded from both numerators and reported separately.

---

# 89. Association is not causation

The system is observational.

Approved and rejected events differ systematically.

Therefore:

> “Approved entries were associated with fewer repeat failures”

does not imply:

> “Approving entries caused fewer repeat failures.”

Reports should use language such as:

```text
associated with
corresponded to
predicted
was followed by
```

unless a controlled design supports stronger causal conclusions.

---

# 90. Event-level binary QA models

For binary QA outcome `$Q_i\in\{0,1\}$`, use regularized logistic regression:

$$
P(Q_i=1\mid Z_i)
=
\sigma\left(
\gamma_0+\gamma^\top Z_i
\right).
$$

Potential `$Z_i$` values include:

```text
event evidence
AI proposal
human decision
AI-human disagreement
relevant baseline covariates
```

---

# 91. Human-versus-AI QA interaction model

A descriptive adjusted model may use:

$$
\operatorname{logit}[P(Q_i=1)]
=
\gamma_0
+
\gamma_1 AI_i
+
\gamma_2 Human_i
+
\gamma_3(AI_i\times Human_i)
+
\delta^\top Z_i.
$$

Interpret coefficients as adjusted associations, not causal effects.

---

# 92. Count QA models

For count outcome `$C_i$`, Poisson regression may use:

$$
C_i\sim Poisson(\mu_i)
$$

with:

$$
\log(\mu_i)
=
\gamma_0+\gamma^\top Z_i.
$$

Use Poisson only if its dispersion assumptions are credible.

When counts are materially overdispersed, prefer:

$$
C_i\sim NegBin(\mu_i,\alpha)
$$

with:

$$
\log(\mu_i)
=
\gamma_0+\gamma^\top Z_i.
$$

A practical warning condition is `$\operatorname{Var}(C)>E(C)$` by a meaningful margin.

---

# 93. Time-to-event QA outcomes

For time-to-event variable `$T$`, define the survival function:

$$
S(t)=P(T>t).
$$

Potential outcomes:

```text
time until similar regression
time until entry superseded
time until related incident recurs
time until resolution
```

With sufficient observations, use Kaplan–Meier descriptive curves and potentially a Cox model:

$$
h(t\mid X)
=
h_0(t)\exp(\beta^\top X).
$$

Do not use the Cox model without checking whether the proportional-hazards assumption is reasonable.

---

# 94. Phase-transition QA analysis

When enough pre/post observations exist, project-quality measure `$Q_t$` may be evaluated with an interrupted time-series model:

$$
Q_t
=
\beta_0
+
\beta_1 Time_t
+
\beta_2 Phase_t
+
\beta_3 TimeAfterPhase_t
+
\gamma^\top Z_t
+
\epsilon_t.
$$

Interpretation:

```text
β0 = baseline level
β1 = pre-transition trend
β2 = immediate level change associated with phase transition
β3 = post-transition trend change
Zt = development-volume and other relevant covariates
```

This remains observational unless the rollout design supports causal interpretation.

---

# 95. Difference-in-differences if real controls later exist

Only if comparable treated and untreated units genuinely exist, such as repositories, services, or modules, consider:

$$
Y_{it}
=
\beta_0
+
\beta_1 Treated_i
+
\beta_2 Post_t
+
\beta_3(Treated_i\times Post_t)
+
\gamma^\top X_{it}
+
\epsilon_{it}.
$$

The conventional difference-in-differences effect is `$\beta_3$`.

Do not use this without a defensible comparison group and parallel-trends reasoning.

---

# 96. No opaque QA score

Do not initially collapse project quality into one weighted score.

Keep separate:

```text
regression recurrence
failure recurrence
rollback rate
resolution time
reuse
retention
retrospective usefulness
```

A composite score may be introduced only with explicit documented weights and justification.

---

# 97. Model improvement versus project improvement

Reports must distinguish three things.

### AI model improvement

```text
lower Brier score
lower log loss
better calibration
lower priority MAE
lower archive error
fewer human corrections
```

### Human-review efficiency

```text
higher one-action rate
higher unchanged approval rate
lower correction count
```

### Project QA improvement

```text
lower normalized regression recurrence
lower repeated-failure rate
lower rollback rate
faster related resolution
higher useful-knowledge reuse
```

Improvement in one category must not be described as proof of improvement in another.

---

# 98. Knowledge reuse and retention metrics

For approved canonical entries:

$$
ReuseRate
=
\frac{
N_{\text{entries later referenced or reused}}
}{
N_{\text{eligible approved entries}}
}.
$$

At horizon `$h$`:

$$
RetentionRate_h
=
\frac{
N_{\text{entries still germane at }h}
}{
N_{\text{entries eligible for evaluation at }h}
}.
$$

For example, `$\operatorname{RetentionRate}_{180d}$` measures the proportion still germane at 180 days.

---

# 99. Model bundle

Persist:

```json
{
  "model_version": "...",
  "trained_at": "...",

  "window_start": "...",
  "window_end": "...",

  "observation_count": 0,

  "feature_extractor_version": "...",
  "feature_vocabulary": [],

  "approval_model": {},
  "priority_model": {},
  "archive_model": {},

  "validation": {},
  "calibration": {},
  "correction_metrics": {},
  "drift": {},

  "automation_eligibility": {},

  "implementation_version": "..."
}
```

Canonical serialization should produce a model hash.

---

# 100. Determinism

Given identical:

```text
input observations
configuration
software version
```

analysis should reproduce equivalent output within documented floating-point tolerance.

Requirements:

```text
stable sort
stable category ordering
fixed initialization
fixed optimization tolerance
fixed maximum iterations
canonical serialization
versioned feature extractor
versioned model implementation
fixed resampling seed if resampling is used
```

---

# 101. Reporting commands

Add operations equivalent to:

```text
curator learning-status
curator learning-report
curator learning-recompute
curator learning-category <category>
curator learning-model <version>
curator learning-qa-report
curator review
curator retrospective-review
```

Equivalent MCP operations may expose the same data.

---

# 102. Learning status report

Show:

```text
current phase
automation enabled/disabled
dataset start/end
active observation count
approved count
rejected count
pending count
human audit count
review revision count
safe-summary coverage
event-category support
last recomputation
next recomputation due
model versions
drift warnings
automation eligibility
```

---

# 103. Statistical report

Show:

```text
approval log loss
Brier score
calibration intercept/slope
precision/recall
false-rejection rate

priority MAE
priority signed bias
priority exact agreement
priority within-one agreement

archive log loss
archive accuracy
archive confusion

disposition correction rate
priority correction rate
archive correction rate

one-action review rate
unchanged approval rate
```

---

# 104. QA report

Show available:

```text
regression recurrence
failure recurrence
rollback/revert rate
resolution time
entry reuse
entry retention
supersession
retrospective usefulness

AI/human agreement groups
human override support
AI support in disagreements

pre/post automation QA trends
```

Clearly mark unavailable or immature analyses.

Never manufacture a value simply because the report contains a field for it.

---

# 105. Category report example

```json
{
  "category": {
    "activity_class": "test",
    "result_class": "routine"
  },

  "reviewed": 84,
  "approved": 1,
  "rejected": 83,

  "observed_approval_rate": 0.0119,

  "confidence_95": {
    "lower": 0.002,
    "upper": 0.064
  },

  "recent_reviewed": 18,

  "proposal_correction_rate": 0.024,

  "automation": {
    "eligible": false,
    "reason": "approval upper confidence bound exceeds configured auto-reject threshold"
  }
}
```

Avoid statements such as:

```text
98% AI confidence
```

unless the exact statistical meaning is stated.

---

# 106. Error handling

One malformed event must not abort an entire run.

Return record-level errors:

```json
{
  "status": "invalid",
  "record_id": "...",
  "errors": [
    "review.selection.priority.selected must be integer 0-5"
  ]
}
```

Continue processing remaining records.

---

# 107. Migration compatibility

Existing fields such as:

```text
kind
rationale
impact
```

must remain readable.

Normalize old candidates into the new internal representation.

Do not destructively rewrite all historical inbox records merely to migrate schema.

---

# 108. Privacy boundaries

Do not automatically commit:

```text
native inbox
raw response
learning observations
model bundle
QA linkage state
retrospective review state
generated archive changes
```

Approved Markdown may modify the working tree.

Repository commit remains an explicit separate operation.

---

# 109. Test suite — Hermes/Codex producer

Test:

```text
schema-v3 event generation
structured result fields
safe summary generated before redaction
raw response not persisted
summary bounded
summary sanitized
secret patterns removed
meaningful result preserved
unknown enum handled
legacy schema accepted
```

---

# 110. Test suite — Curator ingestion

Test:

```text
v2 normalization
v3 normalization
missing safe summary
unknown category
malformed category
duplicate record
fingerprint handling
record_id handling
schema migration
one malformed record does not abort run
```

---

# 111. Test suite — candidate generation

Test:

```text
deterministic prose
date included
provider included
profile included
model included
event type included
safe result included
fingerprint included
record_id included
bounded description
routine lifecycle event does not dominate meaningful result
```

---

# 112. Test suite — review UX

Test:

```text
horizontal option arrays generated
only selected value interpreted
approved selection works
do-not-record works
priority 0-5 validation
archive validation
significance validation
change-class validation
optional review reason
human text edits preserved
pending edits preserved
priority 5 confirmation
```

---

# 113. Test suite — persistence

Test:

```text
approved appends correct file
rejected modifies no canonical file
idempotent record_id
duplicate approval does not duplicate entry
transaction rollback
observation and Markdown stay consistent
manual review correction produces revision
```

---

# 114. Test suite — learning store

Test:

```text
human finalized decisions eligible
pending excluded
automatic decisions excluded
superseded revisions excluded
latest active revision included
free text excluded from predictor matrix
six-month active training window
nine-month event-level retention
21-day recomputation
rejected records excluded from archive training
stable feature vocabulary
unknown maps to __OTHER__
```

---

# 115. Test suite — approval model

Using fixed synthetic data, verify:

```text
coefficient determinism
probability range
regularization
convergence
separation robustness
prediction interval behavior
log loss
Brier score
precision
recall
calibration calculations
```

---

# 116. Test suite — priority model

Verify:

```text
threshold ordering
category probabilities sum to 1
expected priority
regularization
MAE
signed bias
exact agreement
within-one agreement
```

---

# 117. Test suite — archive model

Verify:

```text
probabilities sum to 1
stable softmax
regularization
multiclass log loss
accuracy
confusion matrix
unknown feature handling
rejected records excluded
```

---

# 118. Test suite — temporal evaluation

Verify:

```text
future observations never enter prior model
prediction snapshot immutable
rolling-origin ordering
model version preserved
retraining does not overwrite old prediction
prospective metric uses original prediction
```

This test is essential.

---

# 119. Test suite — human/AI correction analysis

Verify:

```text
disposition correction
priority signed correction
priority absolute correction
archive correction for approved records only
rejected records excluded from archive correction metrics
text correction
one-action rate
unchanged approval rate
rolling metrics
```

---

# 120. Test suite — QA linkage

Using synthetic event sequences, verify:

```text
30-day window
60-day window
90-day window
180-day window
repeat event detection
regression recurrence
rollback linkage
reference count
retention
supersession
future outcome never becomes original predictor
```

---

# 121. Test suite — automation safety

Verify:

```text
Phase 0 never automates
Phase 1 never automates
less than 180 days never enters Phase 2/3
sparse category never automates
wide interval blocks automation
unknown category blocks automation
missing safe summary blocks or downgrades automation
drift warning blocks automation

Phase 2 only rejects eligible records
automatic rejection is not a human training label

Phase 3 disabled by default
Phase 3 requires explicit enablement
priority 5 still human-confirmed

human audit sample continues
audit human decisions become labels
automatic decisions do not
```

---

# 122. Test suite — project-QA analysis

Verify formulas and logic for:

```text
normalized regression rate
failure recurrence
rollback rate
time-to-event censoring
negative-binomial inputs
retrospective usefulness
AI/human agreement matrix
override support
phase-transition analysis
```

Do not run advanced models below configured support thresholds.

---

# 123. Implementation order

Implement in this sequence:

```text
1. Hermes/Codex schema-v3 contract

2. pre-redaction safe semantic summary

3. Hermes sanitization and event-envelope updates

4. Curator v2/v3 normalization

5. new candidate schema

6. painless multiple-choice JSON review block

7. pending/finalized review state machine

8. canonical archive persistence + record_id idempotency

9. external immutable learning observations

10. prediction snapshot infrastructure

11. deterministic feature extraction

12. descriptive learning report

13. approval logistic model

14. calibration and uncertainty

15. temporal/prequential evaluation

16. ordinal priority model

17. multinomial archive model

18. human-versus-AI correction analysis

19. Phase 0/Phase 1 state machine

20. evidence gates

21. Phase 2 auto-rejection + mandatory human audit

22. Phase 3 implementation, disabled by default

23. QA outcome linkage

24. retrospective utility review

25. human-versus-AI QA analysis

26. drift detection

27. champion/challenger model comparison

28. phase-transition QA analysis
```

Do not begin with automation.

The critical foundation is:

```text
trustworthy evidence
+
safe summary
+
clean human labels
+
immutable prospective predictions
```

---

# 124. Initial acceptance criteria

The system is ready for human-learning operation when:

1. Codex/Hermes emit structured event-result evidence.
2. Safe summary is produced before response redaction.
3. Raw unredacted response need not be persisted.
4. CuratorMD accepts v2 and v3.
5. Candidate prose is deterministic.
6. Review choices are generated as horizontal options.
7. Human normally edits only `selected`.
8. Pending is never treated as rejection.
9. Approved records append idempotently.
10. Rejected records never modify archive Markdown.
11. Human and AI values remain separately stored.
12. Prediction snapshots are immutable.
13. External learning store is outside repository.
14. Free text is absent from initial model features.
15. 21-day full recomputation works.
16. Six-month active training window works.
17. Temporal validation prevents future leakage.
18. Human correction metrics work.
19. Phase 1 cannot automate.
20. Existing CuratorMD tests continue to pass.

---

# 125. Automation acceptance criteria

Phase 2 or Phase 3 may operate only when:

```text
minimum history satisfied
minimum category support satisfied
recent human evidence exists
calibration acceptable
temporal validation acceptable
uncertainty bounds pass threshold
no drift warning
human audit stream enabled
operator configuration permits phase
```

The report must state the precise gate decision.

---

# 126. Longitudinal success criteria

The project should eventually be able to answer with evidence:

### Curation learning

What kinds of development events does the human consistently consider worth chronicling?

### Priority learning

Which observable event characteristics correspond to higher human priority?

### Archive learning

Which event characteristics correspond to `agents`, `sop`, `history`, or `lessons`?

### AI proposal improvement

Are CuratorMD's prospective proposals becoming more accurate and better calibrated?

### Human-effort reduction

Is the human increasingly able to accept proposals without correction?

### Human-versus-AI disagreement

In which event classes does the human systematically override the AI, and in which direction?

### Retrospective validity

When human and AI judgments disagreed, which judgment was more often supported by later evidence?

### QA association

Are particular curation practices associated with reduced recurrence, faster resolution, greater knowledge reuse, or improved project continuity?

### Automation safety

Does automation maintain human-equivalent decision quality under continuing audit?

---

# 127. Final conceptual architecture

The immediate learning loop is:

$$
\boxed{
\text{Codex Result}
\rightarrow
\text{Hermes Evidence}
\rightarrow
\text{CuratorMD Proposal}
\rightarrow
\text{Human Judgment}
\rightarrow
\text{Statistical Learning}
\rightarrow
\text{Improved Proposal}
}
$$

The prospective model-evaluation loop is:

$$
\boxed{
\text{AI Prediction}_t
\rightarrow
\text{Human Decision}_t
\rightarrow
\text{Prediction Error}_t
\rightarrow
\text{Model Evaluation}
}
$$

The longer-term quality loop is:

$$
\boxed{
\text{Development Event}
\rightarrow
\text{AI/Human Curation Judgment}
\rightarrow
\text{Later Project Outcomes}
\rightarrow
\text{Retrospective Utility Evidence}
}
$$

The operational objective is to separately optimize:

- lower human curation burden
- better-calibrated AI proposals
- higher preservation of genuinely useful project knowledge
- lower loss of important project knowledge

while continuously validating those assumptions against later project evidence.

The system should learn what the human values without assuming the human is infallible, learn from AI mistakes without allowing the AI to train on its own decisions, and evaluate both against later project evidence without overstating observational associations as causation.
