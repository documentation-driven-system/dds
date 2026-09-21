# AGENTS.md

This repository is governed by the Documentation-Driven System (DDS): `.dds/` is the reference description of system behaviour, and the protocols under `.dds/meta/` are the source of truth for how to change it.

## Working here

1. Before changing code, a schema, an API, or documentation, read `.dds/meta/manifesto.dds.md` end to end and follow the domain protocol it routes you to. Done when the document that governs your change is open in front of you.
2. Code you change is governed by a module document whose `sources:` matches it. When none does, follow `.dds/meta/adopt.dds.md` and create a `status: draft` document before touching the code.
3. `.dds/product/constraints.dds.md` holds the non-negotiable constraints. A change that conflicts with one stops and goes to a human.
4. Stage the governing document together with the code, then run `python .dds/meta/scripts/dds.py check --gate --staged` and clear every ERROR. Code staged under an `active` document without that document fails the gate. The commit is ready when the gate prints `RESULT: PASS`.

`python .dds/meta/scripts/dds.py --help` lists the tooling (check, impact, lock/unlock, tree); use it instead of searching `.dds/` by hand. Agents with Agent Skills support also find these steps as the `dds` skill.
