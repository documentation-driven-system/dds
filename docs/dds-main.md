# Documentation-Driven System (DDS): Overview

The human-facing guide to the framework. The protocols under `.dds/meta/` are the source of truth; this page explains them, it does not replace them.

---

## 1. The problem DDS answers

AI coding agents start every session without memory of the last one. A repository whose behaviour lives in code, chat history, and people's heads gives each session a different picture, and the code drifts. DDS keeps the description of the system in one governed place, `.dds/`, tells people and agents how to change it, and checks that place before every commit.

The claim is modest and mechanical: a change is not committable until the documents describe the behaviour the code now has, and a script can tell when the documents contradict each other. What the code actually does is still established by review and tests.

## 2. The laws

Section [1] of `.dds/meta/manifesto.dds.md` holds six laws; the summary:

0. **Non-negotiable constraints.** Security, legal and compliance, safety, and physical constraints live in `.dds/product/constraints.dds.md`. No tier, KPI, or business goal overrides them; a conflict stops the work and goes to a human.
1. **Single source of truth.** A change may start anywhere, a business decision, a schema migration, a code edit. Before the commit, the governing documents describe the new behaviour. At commit time, an `active` document is the reference and code that contradicts it is a defect; if the document is what is wrong, the document is fixed first. A `draft` document is not yet authoritative.
2. **Truth hierarchy.** Conflicts between *rules* resolve top-down: product over architecture over modules; the lower document is corrected. KPIs are targets, never rules, and override nothing.
3. **Threshold-based sync.** No commit while `dds.py check --gate` reports errors. Agents and CI are always strict; humans follow `gate:` in `.dds/tree.dds.md`, which starts at `warn` during adoption.
4. **Schema conformance.** Every `.dds.md` file follows `schema.dds.md`; locks are transient and never committed.
5. **Tombstones.** Nothing in `.dds/` is deleted. A retired document moves to `.dds/archive/` and leaves a Tombstone line in the index that pointed to it.

Section [2] adds the routing precedence: multi-tier work is decided top-down (product first) and, for deprecations, executed leaves-first (modules first); a task that matches no tier changes no document; a tie goes to the higher tier; code no document governs goes through `adopt.dds.md` before anything else.

## 3. Layout

```text
/ (Project Root)
├── AGENTS.md                   # Always-on entry point for agents; CLAUDE.md imports it.
├── .claude/skills/dds/, .agents/skills/dds/   # The same steps as an Agent Skill, loaded on demand.
└── .dds/
    ├── meta/                   # Protocols and tooling. Changing these is a DDS version change.
    │   ├── manifesto.dds.md    # Constitution, routing precedence, routing matrix, tooling contract.
    │   ├── schema.dds.md       # The single frontmatter / id / tree grammar; every ENFORCED rule.
    │   ├── adopt.dds.md        # Bringing DDS into an existing codebase.
    │   ├── dds.product/        # rules / write / update / deprecate for the Product tier.
    │   ├── dds.architecture/   # The same four protocols for the Architecture tier.
    │   ├── dds.modules/        # The same four protocols for the Modules tier.
    │   └── scripts/dds.py      # check | impact | lock | unlock | tree (standard library only).
    ├── tree.dds.md             # Root index; carries dds_version, locking, gate.
    ├── product/                # Why: vision, constraints, personas, KPIs, epics.
    │   └── product.tree.dds.md
    ├── architecture/           # Where: tech stack, data models, infrastructure, API boundaries.
    │   └── architecture.tree.dds.md
    ├── modules/                # How: one document per logical feature, in sub-folders.
    │   └── modules.tree.dds.md
    └── archive/                # Retired documents and emptied index trees, mirrored by tier.
```

Each tier has a human guide: `dds-product.md`, `dds-architecture.md`, `dds-modules.md`.

## 4. The mechanics, and what each one does and does not do

- **One schema.** Flat YAML frontmatter with a fixed field set: `id`, `type`, `status` (`draft` / `active` / `deprecated`), `dependencies` (ids, never paths), `last_updated`, optional `description`, and for module documents `sources:` globs naming the code the document governs. Ids are permanent and prefixed by tier. `check` rejects anything else. An `active` document also has every required section of its template non-empty and every `sources:` glob matching at least one file; a `draft` gets warnings for the same.
- **Index trees.** Every folder has a `<folder>.tree.dds.md`; every document is listed exactly once in its folder's tree; every tree is reachable from the root through one chain of pointers. Orphaned knowledge is an error, not a smell.
- **Dependency graph.** Dependencies point upward only (a module obeys architecture and product; architecture obeys product; product obeys product) and the graph is acyclic; `check` rejects the reverse. `impact <id>` lists direct dependents, `--down` the transitive cascade set, `--up` what a document itself obeys. The deprecate protocols use it instead of asking anyone to search.
- **Deprecation lifecycle.** A retirement is decided top-down and executed leaves-first: modules first, the origin last, so no active document ever depends on a retired one. Members of the same cascade set do not block each other; a dependent outside the set does. Retired documents keep their id forever under `.dds/archive/`; the tree line that named them becomes a Tombstone with the reason. An emptied local tree moves to the archive too.
- **The gate.** `check --gate --staged` is what the commit hooks run. Plain `check` reports the same errors and shows locks as information; the gate treats a present lock as an error. `--staged` reads the git index: code staged under an `active` document's `sources:` without that document staged is an error in gate mode, a warning otherwise. There is no bypass at the gate; humans under `gate: warn` are let through by their hook, and a `DDS-No-Doc:` commit trailer is a CI-era audit mark, not a switch. `--coverage` lists code files no module document governs; `--sync` warns when governed code changed and its document did not. `--sync` is a drift detector, touching the document silences it, and human review is what establishes correctness.
- **Locks.** Off by default. With `locking: on`, `dds.py lock` coordinates executors that share one working copy through an exclusive-create sidecar under `.dds/.locks/`, a 40-minute takeover rule computed from a timestamp, and a mirror in the frontmatter that is never committed. Across clones, branches do this job.
- **Capped changelog.** Ten entries per document; older ones are trimmed and remain in `git log`.
- **Writing conventions.** Headers no deeper than H3, headers that carry their context, and referents named inside the section they are used in, so a section still makes sense when a retrieval tool hands it over alone. These are conventions checked by convention (and optionally by Vale), except header depth, which `check` warns about.

What the tooling does not do: it does not orchestrate agents (update cascades are executor discipline plus `--sync` warnings), and it does not verify that code behaves as documented.

## 5. Adoption

`.dds/meta/adopt.dds.md` is the protocol for a codebase that already exists. Copy the template, install the adapters, set `gate: warn`, and write documents as `status: draft` from the code, features rather than files, with `sources:` pointing at what they govern. `check --coverage` shows what is still ungoverned. A human review promotes a draft to `active`; from that moment the document is authoritative for its sources. Agents are held to the strict gate from day one and must create a draft before touching ungoverned code.

## 6. How agents find any of this

Nothing reads `.dds/` unless an entry point says so. `templates/adapters/` holds the always-on file (`AGENTS.md`; `CLAUDE.md` imports it for Claude Code), the same steps as an Agent Skill for `.claude/skills/` and `.agents/skills/`, a Claude Code hook that runs the gate before `git commit`, a git pre-commit hook for humans, and a CI job. `templates/adapters/README.md` maps each agent to what it reads.

## 7. Versioning

`dds_version` lives in `.dds/tree.dds.md` and `.dds/meta/manifesto.dds.md` and must match; `dds.py` warns when its own version differs. Once a version is tagged, protocol text under `.dds/meta/` changes only with a version bump (MINOR for compatible protocol edits, MAJOR when the schema breaks). `v1.0.0` is the original prose release; `v2.0.0` (2026-09-18) introduced the schema and the validator and breaks the 1.0 frontmatter; `2.1.0` is the current line and adds the code-facing gate rules (`--staged`, dependency direction and cycles, non-empty `active` documents) as a MINOR bump.
