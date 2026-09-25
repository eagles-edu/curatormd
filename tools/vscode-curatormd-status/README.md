# CuratorMD Status LED for VS Code

This extension adds a colored status-bar indicator for the Hermes profile
configured by the active workspace. It checks local commands and that
workspace's CuratorMD state only; it does not read or print credentials.

The status tooltip shows the last check time and configured polling
interval. Change `curatormdStatus.pollSeconds` in workspace settings to control
how often it refreshes; the extension resets its timer when the setting changes.

Status precedence:

- Green: Hermes, Codex, and CuratorMD are healthy and idle.
- Blue: review notes are waiting in the CuratorMD native inbox.
- Purple: Hermes is unhealthy.
- Yellow: Codex authentication/runtime is unhealthy.
- Cyan: CuratorMD is actively running a curation lock.
- Red: more than one system is unhealthy.

## Install for this workspace

From the repository root:

```bash
cd tools/vscode-curatormd-status
npx --yes @vscode/vsce package --no-dependencies
code --install-extension curatormd-status-0.2.5.vsix
```

Reload VS Code after installation. Click the LED for review notes when they
are pending, or run `CuratorMD: Open Review Notes` and
`CuratorMD: Refresh Status` from the Command Palette.

## Review pending notes

When notes are waiting, clicking the blue status LED or choosing **Open Review
Notes** in the notification prepares any eligible bounded proposals and opens
`.curatormd/reviews/pending-review.md` in the editor. That file is local,
generated, and ignored by Git. Each ready candidate has **Approve…** and **Do
not record…** CodeLens actions. Approval asks you to choose priority and the
destination persistence document; priority 5 requires a second confirmation.

Notes without a safe summary remain visible in the queue but have no approval
action. CuratorMD does not invent missing candidate text. Approving a candidate
is an explicit human action and writes only that entry to the selected
`persistence/*.md` file.
