---
name: dds
description: Governance protocol for repositories that carry a `.dds/` directory (Documentation-Driven System). Load before changing code, a schema, an API, or documentation; before any git commit; when adding, updating, or retiring a feature; and when asked about `.dds`, DDS, product/architecture/module documents, tombstones, or the Truth Hierarchy.
license: MIT
metadata:
  dds_version: "2.1.0"
---

# DDS — Documentation-Driven System

`.dds/` is this repository's reference description of behaviour; the protocols under `.dds/meta/` are the source of truth. This skill routes you to them.

1. Read `.dds/meta/manifesto.dds.md` end to end: laws, routing precedence, routing matrix. Done when you can name the tier (product, architecture, modules) and the action (create, update, deprecate) of your task.
2. Open the domain rule set the manifesto routes you to and follow its write, update, or deprecate protocol step by step. Done when the protocol's own FINAL_CHECK passes.
3. Run the tooling instead of simulating it: `python .dds/meta/scripts/dds.py --help` (check, impact, lock/unlock, tree). Cascade sets come from `impact <id> --down`, never from a manual search.
4. Code with no governing module document (`sources:` in `.dds/modules/**`) is adopted first: `.dds/meta/adopt.dds.md`, a `status: draft` document, then the change.
5. Stage the governing document with the code, then run `python .dds/meta/scripts/dds.py check --gate --staged` and clear every ERROR. Done when it prints `RESULT: PASS`.

`.dds/meta/manifesto.dds.md` and `.dds/meta/schema.dds.md` change only through a DDS version bump; task work leaves them untouched.
