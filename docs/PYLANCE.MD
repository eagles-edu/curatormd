# Pylance and Pyright diagnostics

This document records the analysis and cleanup of the Pylance Problems export
for `plugins/gptmd-memory/scripts/curation_learning.py`.

## Result

The original export contained 90 error-severity diagnostics:

| Diagnostic                  | Count | Cause                                                                                      |
| --------------------------- | ----: | ------------------------------------------------------------------------------------------ |
| `reportUnknownVariableType` |    33 | JSON objects and intermediate collections had no concrete value type.                      |
| `reportUnknownMemberType`   |    33 | The unknown JSON types propagated into calls such as `.get()`, `.append()`, and `.sort()`. |
| `reportUnknownArgumentType` |    17 | Values from those untyped structures reached typed functions.                              |
| `reportUnknownLambdaType`   |     2 | The active-row sort key inherited unknown values.                                          |
| `reportPrivateUsage`        |     4 | The learning module imported private state and file helpers from `gptmd_memory.py`.        |
| `reportUnusedFunction`      |     1 | The analyzer did not connect `_meaningful()` to its dynamic import caller.                 |

The main cause was decoded JSON being narrowed only to a generic `dict`, which
leaves its keys and values unknown in strict type checking. The optimizer also
initialized its cumulative-threshold list without an element type. The
Problems export was a snapshot; it is replaced here by this readable report
instead of being kept as a 1,890-line diagnostics dump.

The current configured strict check is clean:

```bash
pyright --project pyrightconfig.json
```

Verified with Pyright 1.1.414: **0 errors, 0 warnings, 0 information** across
the configured learning module. `git diff --check` also passed. No test suite
was run as part of this diagnostics task.

## Repairs made

- Added `_as_object()` as the checked boundary for decoded JSON mappings. It
  keeps dynamic payload values typed as `Any` while making mapping keys
  predictably strings.
- Added explicit annotations for feature maps, training rows, threshold lists,
  calibration bins, and filesystem path collections.
- Added public `plugin_data_root()`, `atomic_json()`, and `create_json_once()`
  wrappers in `gptmd_memory.py`. Learning code now uses these APIs rather than
  importing private helpers.
- Promoted `_meaningful()` to the public `meaningful()` API and updated its
  dynamic-import caller. This makes the module boundary explicit and preserves
  candidate gating behavior.
- Added a scoped [`pyrightconfig.json`](../pyrightconfig.json) so VS Code
  Pylance and the CLI both use strict checking for this module without
  changing the checking mode for every Python file in the repository.

The runtime behavior remains the same: JSON payloads are still checked before
use, summaries remain redacted and bounded, and the public helper wrappers
delegate to the existing atomic storage operations.

## Pylance and the command line

Pylance is the VS Code language support extension. Microsoft documents Pyright
as the command-line type checker and the core typing engine used by Pylance.
The two may differ when their versions or settings differ, so use the workspace
configuration and check the VS Code Problems panel after edits. See the
[Pylance project documentation](https://github.com/microsoft/pylance-release/blob/main/README.md?plain=1)
and [Pylance and Pyright together](https://github.com/microsoft/pylance-release/blob/main/USING_WITH_PYRIGHT.md).

To run the scoped CLI check:

```bash
pyright --project pyrightconfig.json
```

To inspect machine-readable results:

```bash
pyright --project pyrightconfig.json --outputjson
```
