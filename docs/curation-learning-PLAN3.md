Below is a complete replacement for the original plan. It preserves its core requirements—four archives, independent priority/disposition, six-month external learning state, 21-day recomputation, pending reprocessability, human-first automation, legacy compatibility, and no automatic commits—while making the producer/liaison/curator boundaries, review UX, statistical design, downstream QA evaluation, and implementation criteria explicit.

# CuratorMD Human-Guided Curation, Statistical Learning, and QA Validation Plan

## 1. Purpose

Extend CuratorMD from a lifecycle-event curator into a longitudinal, human-supervised decision system that learns which software-development events deserve durable project chronicle entries, how important those entries are, where they belong, and—over time—whether the human and AI assumptions behind those decisions are associated with measurable project quality outcomes.

The system must not merely learn:

> “What did the human approve?”

It must progressively distinguish three questions:

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

The implementation must follow these principles.

### 2.1 Evidence, proposal, decision, and outcome are different things

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

- AI proposal != human label
- human approval != objective QA benefit
- AI confidence != statistical evidence
- automatic decision != human label

---

## 2.2 The producer reports facts; CuratorMD evaluates importance

Codex/Hermes should provide structured evidence describing the event.

They should not authoritatively decide whether the event belongs in project history.

For example:

GOOD PRODUCER FACTS

- test failed
- architecture changed
- dependency changed
- three tests failed
- rollback occurred
- decision was made
- configuration changed
- new procedure introduced

Avoid treating fields such as:

- `important=true`
- `should_archive=true`
- `priority=5`

as ground truth.

A producer may provide such opinions as audit metadata, but they must not automatically become Curator labels or regression outcomes.

---

## 2.3 Human review is the initial supervisory source

During the human-learning phases, the human's finalized review becomes the supervised curation label.

Pending records are unlabeled.

Automatic decisions are not human labels.

---

## 2.4 Downstream project quality is a separate evidentiary layer

The system must later evaluate whether curation judgments remain useful when tested against observable future project behavior.

Examples include:

- repeat regressions
- repeat incidents
- rollback/revert
- time to resolution
- test failure recurrence
- entry reuse
- entry survival through compaction
- procedure reuse
- lesson reuse
- supersession
- manual retrospective usefulness

These outcomes must remain separate from the original review labels.

---

## 2.5 Human review must be almost frictionless

CuratorMD performs the writing.

The human supplies judgment.

The normal workflow should therefore be:

```text
proposal correct
    -> choose approved

proposal irrelevant
    -> choose do-not-record

proposal mostly correct
    -> change one or two selections
    -> approve
```

The reviewer must not manually reconstruct metadata already known to the system.

---

# 3. Preserve the existing Hermes–Codex liaison architecture

The existing Hermes/Codex topology shown in the attached liaison diagram remains authoritative for transport and execution relationships.

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

# 4. Division of responsibilities

## 4.1 Codex responsibilities

Codex is closest to the semantic meaning of the completed development operation.

Codex should therefore produce bounded structured evidence while it still possesses the complete execution context.

Codex responsibilities:

- execute development work
- know the task intent
- know the actual result
- know whether tests passed or failed
- know whether files/configuration/dependencies changed
- know whether a fix was made
- know whether a project decision occurred
- know the unredacted final response before persistence redaction
- produce a safe semantic summary before that information is lost

Codex must not:

- append canonical CuratorMD archives
- create human labels
- train the CuratorMD statistical models
- silently auto-approve chronicle entries
- treat its own proposed importance as ground truth

---

# 5. Safe semantic summary requirement

The current payload contains:

```json
"response": "[REDACTED]"
```

Once the response has reached that state, CuratorMD cannot recover its semantic content.

Therefore a **safe semantic summary derived from the unredacted response must be produced before redaction**.

The required processing sequence is:

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

CuratorMD does **not** need the original unredacted response.

It needs the meaningful development result preserved safely.

---

# 6. Safe-summary requirements

The summary must preserve, where applicable:

- what was attempted
- what was actually accomplished
- important test result
- important failure
- important regression
- important discovery
- root cause
- fix
- persistent project change
- architectural consequence
- dependency consequence
- configuration consequence
- interface consequence
- project decision
- new procedure
- unresolved issue

It should suppress routine narration such as:

- agent started
- agent stopped
- agent:end occurred
- tool finished
- session closed

unless that lifecycle behavior itself was the object of the test.

Recommended default limits:

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

- passwords
- API keys
- access tokens
- refresh tokens
- private keys
- authorization headers
- cookies
- credential-bearing URLs
- credential-bearing connection strings
- secret environment variables
- private secrets
- unnecessary personal identifiers
- unbounded logs
- unbounded file contents

Replacement placeholders may include:

- `[SECRET]`
- `[TOKEN]`
- `[CREDENTIAL]`
- `[PRIVATE_VALUE]`
- `[PRIVATE_PATH]`

The safe summary itself may remain semantically unredacted with respect to ordinary project information.

That is, do not turn:

> “The OAuth refresh path failed because token expiry was incorrectly calculated.”

into:

> “[REDACTED] failed because [REDACTED].”

Only the sensitive value should be removed.

---

# 8. Hermes responsibilities

Hermes owns the durable event-envelope and liaison/security boundary.

Hermes responsibilities include:

- capture lifecycle event
- receive structured Codex result
- receive safe semantic summary
- validate event schema
- validate enum values
- sanitize again if necessary
- redact raw response before persistence
- assign or retain `record_id`
- assign `source_id`
- assign timestamp
- assign cursor
- assign fingerprint
- identify provider/profile/model/platform/scope/session
- deduplicate transport events
- persist temporary inbox record
- deliver event to CuratorMD
- preserve schema version

Hermes should not decide:

- whether an event deserves recording
- canonical archive
- human priority
- human disposition
- future automation phase

---

# 9. Requested Hermes/Codex schema v3

Existing schema-v2 payloads remain readable.

New producers should emit schema v3.

Example:

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

Use bounded enums.

## `activity_class`

- `test`
- `build`
- `deploy`
- `implementation`
- `refactor`
- `debug`
- `configuration`
- `dependency`
- `migration`
- `documentation`
- `research`
- `design`
- `review`
- `release`
- `security`
- `data`
- `other`
- `unknown`

## `status`

- `success`
- `failure`
- `partial`
- `blocked`
- `cancelled`
- `unknown`

## `result_class`

- `routine`
- `validation`
- `change`
- `fix`
- `failure`
- `discovery`
- `decision`
- `milestone`
- `regression`
- `artifact`
- `unknown`

## `failure_class`

- `none`
- `test`
- `runtime`
- `integration`
- `configuration`
- `dependency`
- `data`
- `security`
- `regression`
- `environment`
- `unknown`

Unknown producer values map to:

- `unknown`
- `__OTHER__`

during statistical encoding.

Never dynamically invent model categories during inference.

---

# 11. Legacy payload behavior

For schema v2:

### Case A — response still available

Generate a safe summary before redaction.

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

CuratorMD may still evaluate metadata.

Its report must expose:

```text
safe_summary_available = false
```

---

# 12. CuratorMD responsibilities

CuratorMD owns everything related to curation policy and learning.

Responsibilities:

- ingest Hermes records
- normalize v2/v3 events
- validate evidence
- generate deterministic candidate
- derive bounded features
- run current statistical model in inference mode
- show AI proposal separately from human decision
- generate painless review block
- persist pending edits
- finalize human review
- append approved Markdown idempotently
- avoid persistence on rejection
- write immutable learning observation
- maintain rolling six-month learning dataset
- recompute models every 21 days
- evaluate model calibration and accuracy
- evaluate user corrections versus AI proposals
- link later QA outcomes
- perform retrospective utility analysis
- detect drift
- manage automation phases
- generate reports

---

# 13. Canonical archives

Allowed archive values:

- `agents`
- `sop`
- `history`
- `lessons`

Definitions:

### `agents`

Stable knowledge concerning:

- agent/provider/profile capabilities
- agent constraints
- agent behavioral expectations
- durable model/profile integration behavior

### `sop`

Repeatable practices:

- testing procedures
- deployment procedures
- validation procedures
- recovery procedures
- security procedures
- review procedures
- operating practices

### `history`

Chronological project knowledge:

- major decisions
- architecture changes
- migrations
- releases
- milestones
- important implementation changes
- important results

### `lessons`

Knowledge intended to prevent recurrence:

- failures
- root causes
- regressions
- constraints
- pitfalls
- corrective practices
- important fixes

Archive is nominal.

Do not statistically encode:

- `agents=1`
- `sop=2`
- `history=3`
- `lessons=4`

as if those numbers imply ordering.

---

# 14. Priority scale

Priority remains independent from disposition.

- **0:** none
- **1:** low
- **2:** moderate
- **3:** high
- **4:** maximum
- **5:** immutable

Definitions:

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

### 5 — immutable

Foundational durable information whose removal could materially damage:

- project intent
- architectural understanding
- safety
- critical operating procedure
- critical historical interpretation

Priority `5` requires explicit human confirmation.

---

# 15. Disposition

Allowed:

- `pending`
- `approved`
- `do-not-record`

Meanings:

- `pending`: review incomplete
- `approved`: append canonical entry and record human decision
- `do-not-record`: record human decision but do not change canonical archive

`pending` is missing outcome data.

It is not:

```text
approved = 0
```

and must not be included as a rejected training example.

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

The candidate must describe the meaningful result rather than merely repeating:

```text
agent:end
```

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

Example:

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

      "priority": {"selected":1,"options":["0:none","1:low","2:moderate","3:high","4:max","5:immutable"]},

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

Only:

- `selection.*.selected`

represents a human selection.

The arrays:

- `selection.*.options`

are interface metadata.

They are never treated as observed statistical values.

---

# 20. Mandatory versus optional review selections

The core human labels are:

- `disposition`
- `priority`
- `archive`

`archive` is required only for approved records.

CuratorMD preselects:

- `priority`
- `archive`
- `significance`
- `change_class`
- `review_reason`

The human changes only incorrect selections.

A correct proposal should require only:

```text
pending -> approved
```

A rejection should require only:

```text
pending -> do-not-record
```

Free-text rationale is never mandatory.

---

# 21. Human correction semantics

Suppose Curator proposed:

```text
priority = 1
archive = history
```

and human selects:

```text
priority = 3
archive = lessons
disposition = approved
```

Store separately:

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

The user should not need to explain it.

---

# 22. Human text edits

If the user edits:

- `title`
- `content`
- `utility`
- `impact`

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

These differences are audit/proposal-quality information.

They are excluded from the initial regression feature matrix.

---

# 23. Review convenience metrics

Measure the burden placed on the user.

Track:

- number of selections changed
- number of text fields edited
- review actions
- proposal accepted unchanged

Primary UX measures:

$$
UnchangedApprovalRate
=
\frac{\text{approved without corrections}}
{\text{all approved}}
$$

$$
MeanCorrections
=
\frac{\text{total corrected fields}}
{\text{reviewed events}}
$$

$$
OneActionRate
=
\frac{\text{reviews requiring only disposition change}}
{\text{all finalized reviews}}
$$

Do not rely on review elapsed time by default because interruptions and multitasking make it noisy.

---

# 24. Review state machine

Use explicit state:

- `received`
- `candidate-generated`
- `pending-review`
- `finalizing`
- `approved`
- `do-not-record`
- `learning-recorded`

A record is never considered permanently processed merely because a candidate was generated.

Pending records remain editable and reprocessable.

Malformed review data remains recoverable.

---

# 25. Review revision behavior

If a finalized human decision is corrected later:

Do not silently destroy the old label.

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

Approved entries append to:

- `agents.md`
- `sop.md`
- `history.md`
- `lessons.md`

as configured by the project.

Do not commit automatically.

Use `record_id` for idempotency.

Recommended hidden marker:

```html
<!-- curatormd:record_id=68b3db3f6a430b8f09e7917a6626ec81 -->
```

Before append:

```text
if record_id already present:
    do not append duplicate
```

---

# 27. Atomic review finalization

Approval/rejection should behave transactionally.

Conceptually:

```text
BEGIN

validate human selection
validate candidate
persist final human review
append Markdown if approved
write learning observation
mark record finalized

COMMIT
```

If a required step fails:

```text
ROLL BACK
```

Avoid states such as:

```text
Markdown appended but learning observation absent
```

or:

```text
human label stored but archive append silently failed
```

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

Active model-training observations use a rolling six-month window:

$$
D_t
=
\{i : t-6\text{ months}\le t_i\le t\}
$$

The entire active retained dataset is recomputed every 21 days.

Do not rely on irreversible online-only coefficient updates.

---

# 30. Long-term aggregate metrics

Event-level learning records may expire after six months.

However, non-sensitive aggregate longitudinal model-performance summaries may be retained longer, for example:

- monthly Brier score
- monthly log loss
- monthly correction rate
- monthly priority MAE
- monthly archive accuracy
- monthly QA rates
- phase-transition metrics

This permits long-term improvement analysis without indefinitely retaining event-level learning content.

---

# 31. Statistical observation schema

Every finalized human review creates one active observation.

Example:

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
    "archive_changed": false,
    "text_changed": false
  },

  "audit": {
    "review_source": "human",
    "producer_schema_version": 3,
    "feature_extractor_version": "1",
    "proposal_generator_version": "1"
  },

  "analysis_eligible": true,
  "active": true
}
```

---

# 32. Training eligibility

A record becomes human-supervised training data only when:

$$
review\_source = human
$$

and:

$$
disposition
\in
\{approved,do\text{-}not\text{-}record\}
$$

and:

```text
active = true
```

Exclude:

- pending records
- malformed records
- machine-only decisions
- superseded review revisions

---

# 33. Predictor/label separation

At proposal time define:

$$
X_i
=
\text{information legitimately available before human review}
$$

Human outcomes:

$$
Y_i
=
\text{review decisions made after seeing the proposal}
$$

Never include post-review variables as predictors of the same review.

Examples of leakage that are prohibited:

- `review_reason` -> approval predictor
- human-edited significance -> approval predictor for same observation
- human archive correction -> archive predictor for same observation
- retrospective usefulness -> original approval predictor

They may become outcomes or features for later, separately defined models.

---

# 34. Initial regression feature policy

Eligible predictors include bounded structured metadata.

Examples:

- `dependency_changed`
- `documentation_changed`
- `data_changed`
- `tests_executed`
- `tests_failed`
- `files_changed_count`
- `tool_count`
- `safe_summary_available`
- `event_type`
- `provider`
- `profile`
- `model family`
- `platform`
- `scope`
- `activity_class`
- `status`
- `result_class`
- `failure_class`
- `changed_project`
- `decision_made`
- `configuration_changed`
- `dependency_changed`
- `interface_changed`
- `architecture_changed`
- `documentation_changed`
- `security_changed`
- `data_changed`
- `tests_executed`
- `tests_failed`
- `files_changed_count`
- `tool_count`
- `safe_summary_available`

---

# 35. Historical frequency features

CuratorMD may derive features using only information existing before the current event:

- same event-class count in previous 7 days
- same event-class count in previous 30 days
- same result-class count in previous 30 days
- days since last same class
- first occurrence indicator
- known category indicator
- recent failure frequency
- recent regression frequency

For event \(i\), never calculate these using events after \(i\).

That would create future leakage.

---

# 36. Count transformations

Raw counts can dominate small models.

Use deterministic transformations.

Example:

$$
x'=\log(1+x)
$$

or predefined buckets:

- `0`
- `1`
- `2-5`
- `6-20`
- `21+`

The transformation must be serialized in the model bundle.

Training and inference use exactly the same mapping.

---

# 37. Categorical feature encoding

Use deterministic one-hot encoding.

Example:

- `activity_class.test`
- `activity_class.debug`
- `activity_class.deploy`
- `result_class.routine`
- `result_class.validation`
- `result_class.failure`
- `architecture_changed.true`

Requirements:

- stable lexical column ordering
- persisted vocabulary
- fixed reference convention
- unseen values -> `__OTHER__`
- no inference-time vocabulary expansion

An unseen high-impact category causes abstention from automation.

---

# 38. Free-text feature policy

Initial predictive models must not use:

- raw response
- safe-summary text
- candidate title
- candidate content
- candidate utility
- candidate impact
- human text
- LLM embedding
- sentiment
- arbitrary language-model importance score

The prose remains evidence for human review.

It is deliberately excluded from the first statistical model so the system can be inspected and audited.

A future text-model experiment must be:

- separate
- versioned
- shadow-mode first
- prospectively evaluated

before it can affect automation.

---

# 39. Model family overview

The initial statistical system uses three distinct response models:

- $\text{Approval model}$
- $\text{Priority model}$
- $\text{Archive model}$

They must not be collapsed into one arbitrary score.

---

# 40. Approval model

Define:

$$
Y_i^{A}
=
\begin{cases}
1,& approved\\
0,& do\text{-}not\text{-}record
\end{cases}
$$

Primary model:

**L2-regularized logistic regression.**

$$
p_i
=
P(Y_i^A=1\mid X_i)
$$

$$
p_i
=
\frac{1}
{1+\exp[-(\beta_0+\beta^T X_i)]}
$$

Estimate:

$$
\hat\beta
=
\arg\min_\beta
\left[
-\ell(\beta)
+
\lambda\sum_{j=1}^{p}\beta_j^2
\right]
$$

Do not penalize the intercept.

Default:

```json
{
  "regularization": "l2",
  "lambda": 1.0
}
```

All configuration remains versioned.

---

# 41. Why regularized logistic regression

The active six-month dataset is likely to begin relatively small while containing multiple categorical predictors.

Regularization:

- reduces coefficient instability
- reduces complete-separation failure
- limits extreme probabilities
- preserves interpretability
- supports deterministic local implementation

This is preferred to unregularized logistic regression for the baseline model.

---

# 42. Sparse-category partial pooling

When sufficient implementation maturity exists, category-specific effects may use a deterministic multilevel/MAP extension.

For category \(g\):

$$
\beta_g
\sim
N(\mu,\tau^2)
$$

This allows sparse categories to borrow information from related categories rather than estimating unstable independent coefficients.

The result is partial pooling:

- large well-supported category -> estimate driven mainly by its own data
- small sparse category -> estimate shrinks toward population behavior

Until this is implemented and validated, use regularized fixed effects plus explicit sparse-category abstention.

Do not fake partial pooling through arbitrary hand weighting.

---

# 43. Approval output

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

Interpret this as:

> Estimated probability that the human reviewer would approve an event with these structured features, under the current model.

Do not phrase it as:

> The event is 14% important.

---

# 44. Priority model

Priority is ordered:

$$
0<1<2<3<4<5
$$

but differences between adjacent levels are not assumed equal.

Use a **regularized proportional-odds ordinal logistic model**.

$$
P(Y^P\le k\mid X)
=
\sigma(\theta_k-\beta^T X)
$$

for:

$$
k=0,\ldots,4
$$

with:

$$
\theta_0<\theta_1<\theta_2<\theta_3<\theta_4
$$

---

# 45. Ordered-threshold implementation

Parameterize:

$$
\theta_0=a_0
$$

and:

$$
\theta_k
=
\theta_{k-1}
+
\exp(\delta_k)
$$

for:

$$
k=1,\ldots,4
$$

This guarantees ordered thresholds during optimization.

---

# 46. Priority outputs

Return full probability distribution:

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

Compute:

$$
E[P\mid X]
=
\sum_{k=0}^{5}
kP(Y^P=k\mid X)
$$

The expected value is advisory.

The distribution is the primary probabilistic result.

---

# 47. Proportional-odds diagnostic

The proportional-odds assumption must not be silently assumed forever.

Periodically compare threshold-specific cumulative binary models.

If feature effects vary materially by threshold:

- flag ordinal-model-assumption warning
- reduce automation confidence

Do not automatically replace the model with a more complex model unless the replacement is separately implemented, versioned, tested, and prospectively validated.

---

# 48. Archive model

For approved human observations:

$$
Y_i^R
\in
\{
agents,
sop,
history,
lessons
\}
$$

Use L2-regularized multinomial logistic regression.

For archive \(j\):

$$
P(Y^R=j\mid X)
=
\frac{\exp(\beta_j^T X)}
{\sum_m\exp(\beta_m^T X)}
$$

Use stable softmax:

$$
z_j
=
\beta_j^T X
-
\max_m(\beta_m^T X)
$$

before exponentiation.

---

# 49. Archive output

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

- top archive
- top probability
- runner-up probability
- probability margin

Do not automate archive selection merely because one category is largest.

---

# 50. Statistical optimization

No external Python ML runtime is required.

Use the existing CuratorMD runtime.

For logistic models, deterministic Newton-Raphson/IRLS is acceptable.

For binary logistic:

$$
p=\sigma(X\beta)
$$

$$
W=\operatorname{diag}(p_i(1-p_i))
$$

A penalized Newton update is based on:

$$
X^TWX+\lambda I
$$

with deterministic:

- initialization
- feature ordering
- convergence tolerance
- maximum iterations
- linear solver
- serialization

If a small numerical library is introduced, it must be pinned and documented.

---

# 51. Pre-review prediction snapshot

This is critical.

Immediately before the human sees the proposal, persist an immutable:

```text
prediction_snapshot
```

containing:

- model version
- feature extractor version
- feature vector hash
- approval probability
- priority probabilities
- archive probabilities
- candidate priority
- candidate archive
- candidate text hash
- timestamp

The snapshot must never be overwritten after human review.

This is the only legitimate basis for claiming how well the AI predicted that decision.

---

# 52. No retrospective prediction inflation

After retraining, do not rerun the new model over old observations and call those values historical prediction accuracy.

That would leak known outcomes into evaluation.

Distinguish:

```text
in-sample fitted value
```

from:

```text
prospective pre-review prediction
```

Only the second measures real operational prediction quality.

---

# 53. Temporal/prequential evaluation

Because project behavior changes over time, evaluation must preserve chronology.

For event \(t\):

```text
train only on reviews before t
predict t
observe human decision
record error
```

Never allow future reviews into past predictions.

Use rolling-origin/prequential validation.

When reconstructing evaluation during development, sort strictly by:

```text
review_timestamp
```

and refit only from prior observations.

---

# 54. Recompute cycle

Every 21 days:

1. load active observations;
2. expire observations outside six-month active window;
3. resolve review revisions;
4. validate schemas;
5. exclude ineligible observations;
6. construct deterministic vocabulary;
7. construct features using past-only transformations;
8. fit approval model;
9. fit priority model;
10. fit archive model;
11. run temporal validation;
12. calculate performance metrics;
13. calculate calibration metrics;
14. calculate category support;
15. calculate uncertainty;
16. calculate human-correction metrics;
17. calculate drift metrics;
18. link available QA outcomes;
19. evaluate automation eligibility;
20. persist model bundle;
21. generate report.

Support manual recomputation.

---

# 55. Approval-model performance

Report at minimum:

## Log loss

$$
LogLoss
=
-\frac{1}{n}
\sum_i
[
y_i\log p_i
+
(1-y_i)\log(1-p_i)
]
$$

## Brier score

$$
Brier
=
\frac{1}{n}
\sum_i
(p_i-y_i)^2
$$

## Precision

$$
Precision
=
\frac{TP}{TP+FP}
$$

## Recall

$$
Recall
=
\frac{TP}{TP+FN}
$$

Also:

- specificity
- negative predictive value
- false-rejection rate
- false-approval rate
- PR-AUC when class imbalance makes it informative
- ROC-AUC as secondary discrimination measure

Do not rely on raw accuracy alone.

---

# 56. Calibration

Probability calibration matters because automation decisions depend on probabilities, not merely ranking.

Report:

- calibration intercept
- calibration slope
- reliability table
- Brier score
- log loss

For sufficiently large datasets also show a reliability diagram.

An ideal calibration relationship is approximately:

- predicted 0.10 -> observed approval about 10%
- predicted 0.50 -> observed approval about 50%
- predicted 0.90 -> observed approval about 90%

Do not describe a model as high confidence merely because its predictions are numerically extreme.

---

# 57. Priority performance

Report:

## Mean absolute error

$$
MAE_P
=
\frac1n
\sum_i
|\hat P_i-P_i|
$$

Also:

- exact-match rate
- within-one-level rate
- signed mean error
- median absolute error
- quadratic weighted agreement
- priority confusion matrix

Signed mean error detects systematic:

```text
over-prioritization
```

or:

```text
under-prioritization
```

---

# 58. Archive performance

Report:

- exact accuracy
- multiclass log loss
- macro F1
- per-archive precision
- per-archive recall
- confusion matrix
- top-two probability margin

Macro metrics must be interpreted cautiously for very sparse archives.

---

# 59. Measuring human changes versus AI proposal

For each review record:

## Disposition correction

$$
C_D
=
I(H_D\ne A_D)
$$

## Priority signed correction

$$
\Delta_P
=
H_P-A_P
$$

## Priority absolute correction

$$
|\Delta_P|
$$

## Archive correction

$$
C_R
=
I(H_R\ne A_R)
$$

## Significance correction

$$
C_S
=
I(H_S\ne A_S)
$$

## Change-class correction

$$
C_C
=
I(H_C\ne A_C)
$$

These provide direct evidence of where the AI misunderstands the human's curation policy.

---

# 60. Proposal-correction report

Report over rolling windows:

- disposition correction rate
- priority correction rate
- archive correction rate
- significance correction rate
- change-class correction rate
- mean signed priority correction
- mean absolute priority correction
- unchanged approval rate
- one-action review rate

Break down by:

- activity class
- result class
- event type
- provider
- profile
- model
- archive
- project-change status

subject to minimum support.

---

# 61. AI proposal accuracy improvement over time

Historical performance must use predictions actually issued at the time.

Track rolling:

- 21-day
- 63-day
- 180-day

performance where sample size allows.

Primary trend metrics:

- approval log loss
- approval Brier score
- approval calibration
- false-rejection rate
- priority MAE
- archive log loss
- archive accuracy
- human correction rate
- one-action review rate

Improvement should appear as:

- lower log loss
- lower Brier score
- better calibration
- lower false-rejection rate
- lower priority MAE
- lower correction rate
- higher one-action review rate

not merely:

```text
more confident predictions
```

---

# 62. Model-version comparison

Use champion/challenger evaluation.

When a new model is produced:

```text
current active model = champion
new candidate model = challenger
```

For subsequent human-reviewed events, generate predictions from both.

Only the champion controls the visible proposal unless configured otherwise.

Record both predictions.

After sufficient paired prospective observations compare them on the same events.

This provides a fairer model-version comparison than comparing different historical periods.

---

# 63. Paired model-comparison statistics

For the same prospective observations:

For binary hard decisions:

```text
McNemar-style paired error comparison
```

For probabilistic predictions compare:

$$
L_i^{new}-L_i^{old}
$$

where \(L_i\) is observation-level log loss.

Report:

- mean paired log-loss difference
- median paired difference
- proportion of observations won by challenger

For priority compare paired:

$$
|e_i^{new}|-|e_i^{old}|
$$

For archive compare paired log loss and correctness.

If resampling confidence intervals are used, use a fixed documented seed and stable algorithm so results are reproducible.

---

# 64. Category-level empirical evidence

For each important category or bounded category combination, retain:

- n reviewed
- n approved
- n rejected
- approval rate
- confidence interval
- recent count

For a binomial rate:

$$
\hat p=\frac{x}{n}
$$

Use a Wilson confidence interval rather than relying on:

$$
\hat p \pm 1.96\sqrt{\frac{\hat p(1-\hat p)}n}
$$

for sparse categories.

---

# 65. Model prediction uncertainty

For binary logistic prediction:

$$
\eta=x^T\hat\beta
$$

Approximate covariance:

$$
\Sigma_\beta
\approx
(X^TWX+\lambda I)^{-1}
$$

Then:

$$
SE_\eta
=
\sqrt{x^T\Sigma_\beta x}
$$

Construct:

$$
\eta_L
=
\eta-zSE_\eta
$$

$$
\eta_U
=
\eta+zSE_\eta
$$

Transform:

$$
p_L=\sigma(\eta_L)
$$

$$
p_U=\sigma(\eta_U)
$$

Automation uses conservative bounds rather than point estimates alone.

---

# 66. Abstention

The statistical system must be allowed to say:

```text
insufficient evidence
```

Automation is prohibited when:

- new feature category
- sparse category
- model not calibrated
- large prediction interval
- drift warning
- producer evidence incomplete
- safe summary unavailable
- model version not prospectively validated

Abstention is preferred to false certainty.

---

# 67. Concept drift

The user's judgment and the project itself may evolve.

Monitor:

- recent approval rate vs older approval rate
- recent correction rate vs older correction rate
- recent log loss vs older log loss
- recent Brier score vs older Brier score
- recent priority MAE
- feature/category distribution shifts

Maintain exponentially weighted moving summaries where useful.

A meaningful deterioration generates:

```text
drift_warning = true
```

Affected categories return to human-only review.

---

# 68. Automation phases

## Phase 0 — instrumentation

Purpose:

Ensure trustworthy event data before trusting statistics.

Behavior:

- capture schema-v3 events
- capture safe summaries
- generate proposals
- collect human labels
- record prediction snapshots
- record corrections
- no automation

---

# 69. Phase 1 — human-only learning

Behavior:

- fit models
- show predictions
- show suggested priority
- show suggested archive
- show uncertainty
- require human final disposition

No automatic approval.

No automatic rejection.

The first six months remain human-review-only for automation purposes.

---

# 70. Phase 2 — conservative auto-rejection

Disabled by default until evidence gate passes.

An event may be automatically `do-not-record` only if all configured conditions pass.

Example statistical requirement:

$$
p_U<T_{reject}
$$

and category empirical evidence satisfies:

$$
WilsonUpper<T_{reject}
$$

Example starting policy:

```json
{
  "auto_reject": {
    "enabled": false,
    "approval_upper_bound_threshold": 0.05
  }
}
```

This means the evidence must indicate that even the conservative upper bound on approval probability is very small.

---

# 71. Phase-2 error metric

The most important Phase-2 safety error is:

> An event automatically rejected that the human would have approved.

Track:

$$
FalseRejectRate
=
P(HumanApprove\mid AutoReject)
$$

This matters more than overall accuracy.

A model that rejects 99% of events but misses important project knowledge is not successful.

---

# 72. Phase 3 — optional auto-approval

Implemented but disabled by default.

Require explicit operator configuration.

An event may be automatically approved only when:

$$
p_L>T_{approve}
$$

and:

$$
WilsonLower>T_{approve}
$$

plus:

- archive confidence sufficient
- priority confidence sufficient
- no drift warning
- adequate category support
- recent human audit evidence

Example starting configuration:

```json
{
  "auto_approve": {
    "enabled": false,
    "approval_lower_bound_threshold": 0.95
  }
}
```

Priority 5 remains human-confirmed unless an additional explicit configuration later changes that rule.

---

# 73. Evidence gate

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

These are policy defaults, not universal laws.

The report must show exactly which condition blocks automation.

---

# 74. Automatic decisions must not become human labels

Example:

```json
{
  "review_source": "automatic",
  "analysis_eligible_as_human_label": false
}
```

Otherwise:

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

This feedback loop is prohibited.

---

# 75. Mandatory human audit stream

After automation begins, human review must continue on a deterministic sample.

Example:

```text
hash(record_id) mod 10 == 0
```

selects approximately one tenth.

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

This is deterministic and reproducible.

Human audit observations continue to provide unbiased evidence about automated categories.

---

# 76. Routine lifecycle suppression

Lifecycle events such as:

- `agent:end`
- `tool:end`
- `test:end`

should not automatically become durable history.

Significance derives from result evidence.

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

# 77. Deterministic pre-model heuristics

Before enough data exists, use transparent rules.

Examples:

```text
routine success + no persistent change + no decision
    -> priority 0-1

important failure without lesson
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

# 78. Statistical proposal integration

The model should influence proposals conservatively.

Do not simply replace every deterministic proposal with the maximum-probability statistical output.

Expose:

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

# 79. Project-QA outcome layer

Curation accuracy alone does not establish project benefit.

Create a separate downstream-outcome layer.

Where observable, link later project events to earlier reviewed events.

Potential objective outcomes:

- test-failure count
- same regression reappeared
- similar failure reappeared
- same configuration mistake repeated
- rollback/revert occurred
- hotfix required
- test-failure count
- time to resolve related failure
- repeated incident count
- same lesson referenced
- same SOP referenced
- canonical entry retrieved
- canonical entry cited by later work
- entry retained through compaction
- entry superseded
- entry marked obsolete

---

# 80. QA outcome windows

Use fixed prospective windows where possible:

- 30 days
- 60 days
- 90 days
- 180 days

For event \(i\), examples:

- `repeat_failure_30d`
- `repeat_failure_90d`
- `regression_count_90d`
- `rollback_30d`
- `time_to_related_resolution`
- `entry_reference_count_90d`
- `retained_at_180d`
- `superseded_by_180d`

Do not use future outcomes to change the original event feature vector.

They are outcomes.

---

# 81. QA denominator controls

Raw counts can be misleading when development activity changes.

Normalize appropriate QA measures using activity denominators such as:

- deployments
- tasks completed
- test runs
- deployments
- changesets
- agent sessions
- release count

For example:

$$
RegressionRate
=
\frac{\text{regressions}}
{\text{relevant development changes}}
$$

rather than simply counting regressions.

---

# 82. Retrospective human utility audit

Some project significance cannot be inferred objectively.

Introduce a very lightweight retrospective audit on a sample of old decisions.

At 90 or 180 days show:

- original event
- original AI proposal
- original human decision
- available subsequent QA evidence

Ask only bounded multiple-choice questions.

Example:

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

Rejected records may additionally ask:

```json
{
  "should_have_recorded": {
    "selected": "no",
    "options": ["yes","no","uncertain"]
  }
}
```

Use a sampled subset so retrospective review does not become burdensome.

---

# 83. Human-versus-AI assumption matrix

For original disposition proposals classify:

- AI approve / Human approve
- AI approve / Human reject
- AI reject / Human approve
- AI reject / Human reject

The disagreement cells are especially informative.

For each group compare later:

- retrospective usefulness
- repeat regression
- repeat failure
- entry reuse
- rollback
- retention
- supersession

---

# 84. Override benefit

For cases where:

$$
AI_i\ne Human_i
$$

later evidence can indicate whether the human override was directionally supported.

Define, when retrospectively resolvable:

- `supports_human`
- `supports_ai`
- `indeterminate`

Then:

$$
HumanOverrideSupportRate
=
\frac{\text{disagreements later supporting human}}
{\text{resolvable disagreements}}
$$

and:

$$
AISupportRate
=
\frac{\text{disagreements later supporting AI}}
{\text{resolvable disagreements}}
$$

Do not force unresolved events into either category.

---

# 85. Important limitation: association is not causation

The system is observational.

Approved and rejected events differ systematically.

Therefore a finding such as:

> Approved entries were associated with fewer repeat failures

does not prove:

> Approving entries caused fewer repeat failures.

Reports must use:

- associated with
- corresponded to
- predicted
- was followed by

rather than causal claims unless a controlled design exists.

---

# 86. Event-level QA statistical models

Use model family appropriate to the outcome.

## Binary outcomes

Examples:

- repeat regression yes/no
- rollback yes/no
- retained yes/no
- retrospectively useful yes/no

Use regularized logistic regression.

---

# 87. Count QA outcomes

Examples:

- number of repeat failures
- number of related regressions
- number of later references

Prefer negative-binomial regression when variance materially exceeds the mean.

Use Poisson only when its dispersion assumption is credible.

---

# 88. Time-to-event QA outcomes

Examples:
- time until entry superseded
- time until similar failure recurs
- time until issue resolved
- time until entry superseded

With sufficient observations:

- Kaplan-Meier descriptive curves
- Cox proportional-hazards model

If sample size is insufficient, report medians and observed event rates instead of unstable survival models.

---

# 89. Human-versus-AI QA model

When enough observations exist, an event-level QA model may include:

$$
QAOutcome
\sim
AIProposal
+
HumanDecision
+
AI\times Human
+
EventCovariates
$$

This helps describe whether later outcomes differ among concordant and discordant decisions while adjusting for observable event characteristics.

Interpret it as adjusted association, not causal effect.

---

# 90. Phase-transition QA analysis

When automation phases change, track project QA metrics before and after.

Use weekly or other stable time units.

Potential segmented model:

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
\gamma^T Z_t
+
\epsilon_t
$$

where \(Z_t\) may include development-activity volume.

This is an interrupted-time-series analysis.

Do not perform it until enough pre/post periods exist.

---

# 91. Stronger causal evaluation if multiple comparable units become available

If the project later has comparable:

- repositories
- modules
- services
- teams

with phased feature adoption, a difference-in-differences or controlled rollout may provide stronger causal evidence.

Do not manufacture a control group when none exists.

---

# 92. No single opaque “QA score”

Do not initially collapse project quality into one weighted score.

Keep distinct:

- regression recurrence
- failure recurrence
- rollback rate
- resolution time
- reuse
- retention
- retrospective usefulness

A composite score may be added later only with explicit documented weights and justification.

---

# 93. Model improvement versus project improvement

Reports must distinguish:

## AI model improvement

Examples:

- lower Brier score
- lower log loss
- better calibration
- lower priority MAE
- lower archive error
- fewer human corrections

## Human-review efficiency

Examples:

- higher one-action rate
- higher unchanged approval rate
- lower correction count

## Project QA improvement

Examples:

- lower normalized regression recurrence
- lower repeated-failure rate
- lower rollback rate
- faster related resolution
- higher useful-knowledge reuse

Improvement in one category must not be presented as proof of improvement in another.

---

# 94. Model bundle

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

# 95. Determinism

Given identical:

- input observations
- configuration
- software version

analysis should reproduce the same output within documented floating-point tolerance.

Requirements:

- stable sort
- stable category ordering
- fixed initialization
- fixed optimization tolerance
- fixed maximum iterations
- canonical serialization
- versioned feature extractor
- versioned model implementation
- fixed resampling seed if resampling is used

---

# 96. Reporting commands

Add operations similar to:

- `curator learning-status`
- `curator learning-report`
- `curator learning-recompute`
- `curator learning-category <category>`
- `curator learning-model <version>`
- `curator learning-qa-report`
- `curator review`
- `curator retrospective-review`

Equivalent MCP operations may expose the same data.

---

# 97. Learning status report

Show:

- current phase
- automation enabled/disabled
- dataset start/end
- active observation count
- approved count
- rejected count
- pending count
- human audit count
- review revision count
- safe-summary coverage
- event-category support
- last recomputation
- next recomputation due
- model versions
- drift warnings
- automation eligibility

---

# 98. Statistical report

Show:

- approval log loss
- Brier score
- calibration intercept/slope
- precision/recall
- false-rejection rate
- priority MAE
- priority signed bias
- priority exact agreement
- priority within-one agreement
- archive log loss
- archive accuracy
- archive confusion
- disposition correction rate
- priority correction rate
- archive correction rate
- one-action review rate
- unchanged approval rate

---

# 99. QA report

Show available:

- regression recurrence
- failure recurrence
- rollback/revert rate
- resolution time
- entry reuse
- entry retention
- supersession
- retrospective usefulness
- AI/human agreement groups
- human override support
- AI support in disagreements
- pre/post automation QA trends

Clearly mark unavailable or immature analyses.

Never manufacture a metric because a report field exists.

---

# 100. Category report example

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

Avoid meaningless wording such as:

```text
98% AI confidence
```

without explaining what it means.

---

# 101. Error handling

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

# 102. Migration compatibility

Existing fields such as:

- `kind`
- `rationale`
- `impact`

must remain readable.

Normalize old candidates into the new internal representation.

Do not destructively rewrite all historical inbox records simply to migrate schema.

---

# 103. Privacy boundaries

Do not automatically commit:

- native inbox
- raw response
- learning observations
- model bundle
- QA linkage state
- retrospective review state
- generated archive changes

Approved Markdown may modify the working tree.

Repository commit remains an explicit separate operation.

---

# 104. Test suite — Hermes/Codex producer

Test:

- schema-v3 event generation
- structured result fields
- safe summary generated before redaction
- raw response not persisted
- summary bounded
- summary sanitized
- secret patterns removed
- meaningful result preserved
- unknown enum handled
- legacy schema accepted

---

# 105. Test suite — Curator ingestion

Test:

- v2 normalization
- v3 normalization
- missing safe summary
- unknown category
- malformed category
- duplicate record
- fingerprint handling
- record_id handling
- schema migration
- one malformed record does not abort run

---

# 106. Test suite — candidate generation

Test:

- deterministic prose
- date included
- provider included
- profile included
- model included
- event type included
- safe result included
- fingerprint included
- record_id included
- bounded description
- routine lifecycle event does not dominate meaningful result

---

# 107. Test suite — review UX

Test:

- horizontal option arrays generated
- only selected value interpreted
- approved selection works
- do-not-record works
- priority 0-5 validation
- archive validation
- significance validation
- change-class validation
- optional review reason
- human text edits preserved
- pending edits preserved
- priority 5 confirmation

---

# 108. Test suite — persistence

Test:

- approved appends correct file
- rejected modifies no canonical file
- idempotent record_id
- duplicate approval does not duplicate entry
- transaction rollback
- observation and Markdown stay consistent
- manual review correction produces revision

---

# 109. Test suite — learning store

Test:

- human finalized decisions eligible
- pending excluded
- automatic decisions excluded
- superseded revisions excluded
- latest active revision included
- free text excluded from predictor matrix
- six-month expiry
- 21-day recomputation
- stable feature vocabulary
- unknown maps to `__OTHER__`

---

# 110. Test suite — binary model

Use fixed synthetic data.

Verify:

- coefficient determinism
- probability range
- regularization
- convergence
- separation robustness
- prediction interval behavior
- log loss
- Brier score
- precision
- recall
- calibration calculations

---

# 111. Test suite — priority model

Verify:

- threshold ordering
- category probabilities sum to 1
- expected priority
- regularization
- MAE
- signed bias
- exact agreement
- within-one agreement

---

# 112. Test suite — archive model

Verify:

- probabilities sum to 1
- stable softmax
- regularization
- multiclass log loss
- accuracy
- confusion matrix
- unknown feature handling

---

# 113. Test suite — temporal evaluation

Verify:

- future observations never enter prior model
- prediction snapshot immutable
- rolling-origin ordering
- model version preserved
- retraining does not overwrite old prediction
- prospective metric uses original prediction

This test is essential.

---

# 114. Test suite — human/AI correction analysis

Verify:

- disposition correction
- priority signed correction
- priority absolute correction
- archive correction
- text correction
- one-action rate
- unchanged approval rate
- rolling metrics

---

# 115. Test suite — QA linkage

Use synthetic event sequences.

Verify:

- 30-day window
- 60-day window
- 90-day window
- 180-day window
- repeat event detection
- regression recurrence
- rollback linkage
- reference count
- retention
- supersession
- future outcome never becomes original predictor

---

# 116. Test suite — automation safety

Verify:

- automatic rejection not training label
- audit human decisions become labels
- automatic decisions do not
- Phase 0 never automates
- Phase 1 never automates
- <180 days never enters Phase 2/3
- sparse category never automates
- wide interval blocks automation
- unknown category blocks automation
- missing safe summary blocks or downgrades automation
- drift warning blocks automation
- Phase 2 only rejects eligible records
- automatic rejection not training label
- Phase 3 disabled by default
- Phase 3 explicit enable required
- priority 5 still human-confirmed
- human audit sample continues
- audit human decisions become labels
- automatic decisions do not

---

# 117. Test suite — project-QA analysis

Verify formulas for:

- normalized regression rate
- failure recurrence
- rollback rate
- time-to-event censoring
- negative-binomial inputs
- retrospective usefulness
- AI/human agreement matrix
- override support
- phase transition analysis

Do not run advanced models below configured support thresholds.

---

# 118. Implementation order

Implement in this sequence:

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

# 119. Initial acceptance criteria

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

# 120. Automation acceptance criteria

Phase 2 or Phase 3 may operate only when:

- minimum history satisfied
- minimum category support satisfied
- recent human evidence exists
- calibration acceptable
- temporal validation acceptable
- uncertainty bounds pass threshold
- no drift warning
- human audit stream enabled
- operator configuration permits phase

The report must state the precise gate decision.

---

# 121. Longitudinal success criteria

The project should eventually be able to answer with evidence:

### Curation learning

> What kinds of development events does the human consistently consider worth chronicling?

### Priority learning

> Which observable event characteristics correspond to higher human priority?

### Archive learning

> Which event characteristics correspond to agents, SOP, history, or lessons?

### AI proposal improvement

> Are CuratorMD's prospective proposals becoming more accurate and better calibrated?

### Human-effort reduction

> Is the human increasingly able to accept proposals without correction?

### Human-versus-AI disagreement

> In which event classes does the human systematically override the AI, and in which direction?

### Retrospective validity

> When human and AI judgments disagreed, which judgment was more often supported by later evidence?

### QA association

> Are particular curation practices associated with reduced recurrence, faster resolution, greater knowledge reuse, or improved project continuity?

### Automation safety

> Does automation maintain human-equivalent decision quality under continuing audit?

---

# 122. Final conceptual architecture

The immediate learning loop is:

$$
\boxed{
Codex\ Result
\rightarrow
Hermes\ Evidence
\rightarrow
CuratorMD\ Proposal
\rightarrow
Human\ Judgment
\rightarrow
Statistical\ Learning
\rightarrow
Better\ Proposal
}
$$

The proposal-quality loop is:

$$
\boxed{
AI\ Prediction_t
\rightarrow
Human\ Decision_t
\rightarrow
Prediction\ Error_t
\rightarrow
Prospective\ Model\ Evaluation
}
$$

The longer-term quality loop is:

$$
\boxed{
Event
\rightarrow
AI/Human\ Curation\ Judgment
\rightarrow
Later\ Project\ Outcomes
\rightarrow
Retrospective\ Utility
}
$$

And the system's final objective is:

$$
\boxed{
\text{reduce curation burden}
+
\text{improve prediction quality}
+
\text{preserve important project knowledge}
+
\text{verify that preservation policy remains useful over time}
}
$$

The system should learn what the human values without assuming the human is infallible, learn from AI mistakes without allowing the AI to train on its own decisions, and evaluate both against later project evidence without overstating observational associations as causation.

The statistical choices here deliberately emphasize **prospective calibration and temporal validation**, not just classification accuracy. Proper probabilistic scores such as log loss and Brier score measure the quality of probability predictions, while calibration requires separate reliability assessment rather than assuming a low Brier score alone means good calibration. ([Scikit-learn][1]) Rolling-origin evaluation likewise ensures only earlier observations are used to predict later ones, which is the correct direction for a system that evolves with the project. ([OTexts: Online, open-access textbooks][2])

For sparse categories, the plan leaves a path to multilevel partial pooling rather than fitting unstable independent category effects; hierarchical logistic models are specifically useful because they sit between complete pooling and completely separate per-group estimation. ([Stan][3])

[1]: https://scikit-learn.org/1.8/modules/calibration.html?utm_source=chatgpt.com "1.16. Probability calibration — scikit-learn 1.8.0 documentation"
[2]: https://otexts.com/fpp3/tscv.html?utm_source=chatgpt.com "5.10 Time series cross-validation | Forecasting: Principles and Practice (3rd ed)"
[3]: https://mc-stan.org/docs/2_28/stan-users-guide/hierarchical-logistic-regression.html?utm_source=chatgpt.com "1.9 Hierarchical logistic regression | Stan User’s Guide"
