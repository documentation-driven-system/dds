@AGENTS.md

## Claude Code

- `.claude/settings.json` runs the DDS gate (`dds.py check --gate --staged`) before `git commit …`, `git -C <path> commit …`, and `git -c key=value commit …`. When it blocks, fix the reported errors (or stage the governing document) and commit again.
- Use plan mode for changes under `.dds/product/` and `.dds/architecture/`; those tiers cascade downward.
