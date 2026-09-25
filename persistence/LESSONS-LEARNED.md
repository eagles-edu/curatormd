# Lessons learned

- A shared tool can live beside consumer repositories without making any consumer repository its system repository. Keep shared implementation ownership explicit and keep per-project state rooted in each consumer.
- Shared CuratorMD integrations must not default to `gptmd-coding` or the GPTMD root. Require a project root/profile marker, write the matching profile into workspace settings, and keep native events and review state under that repository's ignored `.curatormd/` directory.
