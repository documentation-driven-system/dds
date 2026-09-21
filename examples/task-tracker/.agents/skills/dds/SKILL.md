---
name: dds
description: Governance protocol for repositories that carry a `.dds/` directory (Documentation-Driven System). Load before changing code, a schema, an API, or documentation; before any git commit; when adding, updating, or retiring a feature; and when asked about `.dds`, DDS, product/architecture/module documents, tombstones, or the Truth Hierarchy. Do NOT use in a repository without a `.dds/` directory, for writing skills or CLAUDE.md files, or for reviewing the code quality of a diff.
license: MIT
metadata:
  dds_version: "2.1.0"
---

# DDS — Documentation-Driven System

`.dds/` is this repository's reference description of behaviour; the protocols under `.dds/meta/` are the source of truth. This skill routes you to them.

## Prerequisites
- `.dds/meta/scripts/dds.py` exists. If it does not, this repository has not adopted DDS: stop and say so instead of improvising a `.dds/`.
- `python` (or `python3`, or the path in `DDS_PYTHON`) is on PATH; the gate cannot run without it.

## Steps
1. Read `.dds/meta/manifesto.dds.md` end to end: laws, routing precedence, routing matrix. Done when you can name the tier (product, architecture, modules) and the action (create, update, deprecate) of your task.
2. Open the domain rule set the manifesto routes you to and follow its write, update, or deprecate protocol step by step. Done when the protocol's own FINAL_CHECK passes.
3. Run the tooling instead of simulating it: `python .dds/meta/scripts/dds.py --help` (check, impact, lock/unlock, tree). Cascade sets come from `impact <id> --down`, never from a manual search.
4. Code with no governing module document (`sources:` in `.dds/modules/**`) is adopted first: `.dds/meta/adopt.dds.md`, a `status: draft` document, then the change.
5. Stage the governing document with the code, then run `python .dds/meta/scripts/dds.py check --gate --staged` and clear every ERROR. Done when it prints `RESULT: PASS`.

## Gotchas
- A new document that is not listed in its folder's `<folder>.tree.dds.md` fails the gate ("indexed 0 time(s)"); indexing is part of writing it.
- Code staged without its governing document fails the gate; there is no bypass flag. Stage both, or ask the human.
- A document written from existing code is `status: draft` until a human reviews it; `active` claims the document is the reference, and the gate then requires every template section filled and every `sources:` glob matched.
- Retiring a whole domain moves its emptied tree to `.dds/archive/` with a Tombstone in the parent tree; a tree does not stay behind unreachable.
- `impact <id> --down` lists everything that stands on a dependency, including documents two tiers away (a login module on the database that serves an epic). That is the cascade set, not a bug.

`.dds/meta/manifesto.dds.md` and `.dds/meta/schema.dds.md` change only through a DDS version bump; task work leaves them untouched.
