# CuratorMD review learning and proposal workflow

## Summary

Extend CuratorMD so lifecycle events become human-readable review proposals, approved entries append to the selected persistence Markdown file, and finalized review decisions feed an external six-month learning dataset.

The system will recompute its analysis every 21 days and remain human-review-only until statistically meaningful baselines exist.

## Key changes

- Replace the current candidate shape with:

  ```json
  {
    "reviewed": false,
    "candidate": {
      "priority": 0,
      "archive": "history",
      "title": "Short description",
      "content": "Human-readable proposed entry.",
      "utility": "Why this is useful.",
      "impact": "What changes going forward.",
      "disposition": "pending"
    }
  }
  ```

- Generate deterministic proposals containing date, provider, profile, model, event type, fingerprint, and record ID. Additional details remain quoted and bounded.
- Support `archive` values `agents`, `sop`, `history`, and `lessons`; append approved entries to the bottom of that file.
- Treat dispositions as:
  - `pending`: remains for review.
  - `approved`: append to Markdown and record the decision.
  - `do-not-record`: record the feedback decision but do not modify Markdown.
- Keep `priority` independent from disposition, using integer values `0`–`5`.
- Fix processing so pending or incomplete records are not permanently marked processed. Existing records can be edited and reviewed later.
- Validate malformed candidates without aborting the complete curator run.
- Preserve compatibility with existing `kind`, `rationale`, and `impact` candidates during migration.

## Learning dataset

- Store bounded, redacted decision JSON in external CuratorMD plugin state, not the repository.
- Record event metadata, disposition, priority, archive, and bounded content/utility/impact audit data.
- Exclude free text from regression features; use only metadata and review labels.
- Retain six months of decisions.
- Recompute the complete retained dataset every 21 days.
- Produce deterministic regression outputs for:
  - approval versus do-not-record likelihood;
  - expected priority;
  - likely archive.
- Keep sparse event categories in Phase 1 until they have at least six months of data and sufficient reviewed examples for a conservative confidence gate.

## Automation phases

- Phase 1: generate suggestions only; human review is required.
- Phase 2: optionally auto-reject strongly established routine categories, while recording every automatic decision.
- Phase 3: optionally auto-approve strongly established categories only after the same evidence gate and an explicit operator configuration change.
- Routine events such as test completion default to low priority and should be suppressed or downgraded unless they contain a significant result, failure, fix, or project decision.

## Interface and documentation

- Add decision-analysis status to the curator result and status output.
- Add a report command/MCP operation showing learning phase, dataset age, sample counts, recomputation time, and category confidence.
- Update the CuratorMD README, SOP, and tests with the new approval and learning workflow.
- Do not commit inbox records, plugin state, or generated Markdown automatically.

## Test plan

- Deterministic human-readable proposal generation.
- Valid and invalid disposition, priority, and archive values.
- Approved entries append to the selected Markdown file.
- Do-not-record decisions never modify persistence files.
- Pending records remain reprocessable after manual edits.
- Existing legacy candidates still promote correctly.
- Decision data is redacted, external, bounded, and retained for six months.
- Recalculation runs over the full retained dataset every 21 days.
- Sparse categories remain Phase 1.
- Routine test-ending events receive low-priority suggestions.
- Regression results are deterministic and never auto-approve before the configured evidence gate.
- Existing CuratorMD tests continue to pass.

## Assumptions

- The raw native inbox remains temporary and retains its existing 30-day cleanup policy.
- The six-month decision dataset is separate from canonical project knowledge.
- Phase 3 is implemented but remains disabled until explicitly enabled after the evidence report is reviewed.
- No external Python ML dependency is added; the regression implementation remains local and deterministic.
