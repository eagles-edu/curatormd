# Lessons learned

- A shared tool can live beside consumer repositories without making any consumer repository its system repository. Keep shared implementation ownership explicit and keep per-project state rooted in each consumer.
- Shared CuratorMD integrations must not default to a consumer profile or repository root. Require a project root/profile marker, write the matching profile into workspace settings, and keep native events and review state under that repository's ignored `.curatormd/` directory.
- Pyright's project `include` list can omit an open runtime module while Pylance still analyzes it under workspace strictness. Keep runtime modules explicitly included, choose checking mode for the module's data boundary, and narrow JSON objects once before accessing nested fields.
