# Standard operating procedures

## Start a system-repository change

Read all four persistence files, inspect the relevant CuratorMD-owned implementation, then make the narrowest change that preserves consumer-repository isolation.

## Enable a consumer repository

Use `plugins/gptmd-memory/scripts/enable_repo.py` with an absolute Git root, a dedicated Hermes profile, and an unused local schedule. Preserve existing consumer files and keep generated runtime state ignored.

## SDE capture

Capture only bounded vocabulary cues and safe metadata. Never persist raw prompts, responses, tool arguments, credentials, or unrelated paths. Keep candidates pending until explicit human review.
