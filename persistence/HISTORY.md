# Decision history

## 2026-09-26 — Create a dedicated CuratorMD repository

**Decision:** Establish `/home/eaglesvn/dockerz/curatormd` as the standalone owner of shared CuratorMD source, capture hooks, status extension, and documentation.

**Rationale:** GPTMD is a separate medical-doctor application repository. Keeping CuratorMD source in its own sibling repository prevents product code, project memory, and shared system code from being conflated. Consumer repositories retain their own profiles and private state.

## 2026-09-26 — Add project-scoped SDE capture and clarify review/poll state

**Decision:** Bundle before/after SDE vocabulary capture with the CuratorMD Codex plugin, create one safe review candidate per turn, and expose its cue JSON, proposal, and editable decision separately. Bind every consumer through an ignored root/profile marker and workspace-scoped VS Code profile/poll settings.

**Rationale:** Trigger-only records had no usable proposal text, implicit GPTMD profile defaults risked cross-repository confusion, and the status bar gave no indication that its timer was refreshing. The current workflow retains only whitelisted cues and hashed references, shows the last status check, and leaves all candidate decisions to a human.
