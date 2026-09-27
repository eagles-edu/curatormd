# CuratorMD

CuratorMD is the standalone Markdown project curation system. This repository owns its shared Codex/Hermes plugin, SDE capture hooks, VS Code status extension, and documentation.

Each enabled repository keeps its own Git root, Hermes profile, `.curatormd/` inbox and runtime state, and four `persistence/` documents. The shared plugin reads and writes only the selected consumer root. Consumer applications remain separate repositories and are not part of this system repository.

See [`docs/ENABLE-REPO.md`](docs/ENABLE-REPO.md) to enable an isolated project, [`docs/SDE-CAPTURE.md`](docs/SDE-CAPTURE.md) for the automatic SDE capture vocabulary and privacy rules, and [`docs/CURATORMD-USER-GUIDE.md`](docs/CURATORMD-USER-GUIDE.md) for the tool and review workflows.
