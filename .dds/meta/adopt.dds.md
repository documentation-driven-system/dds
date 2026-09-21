---
id: meta-adopt
type: meta
status: active
dependencies: [meta-manifesto, meta-schema]
last_updated: 2026-09-18
description: Protocol for introducing DDS into an existing codebase (brownfield adoption) without declaring all existing code defective.
---

# SYSTEM_DIRECTIVE: ADOPTION_PROTOCOL (EXISTING CODEBASES)

## [0] DEFINITION & SCOPE

On day one of adoption, `.dds/` is empty and the codebase is not. Applied literally, manifesto law [1].1 would declare every line of existing code a defect. This protocol suspends that law PER AREA until documentation catches up, using `status: draft`, and defines the gate policy for the transition.
EXECUTOR (AI Agent or Human) MUST follow this protocol whenever the repository contains code that no `active` module document governs.

## [1] BOOTSTRAP

1. COPY the `.dds/` template into the repository root: `meta/`, the empty tier folders (`product/`, `architecture/`, `modules/`, `archive/`), and the tree skeletons. Do NOT copy `examples/` or `docs/` from the DDS repository.
2. INSTALL the adapters from the DDS repository's `templates/adapters/`: `AGENTS.md` (plus `CLAUDE.md` importing it), the `dds` skill into `.claude/skills/` and/or `.agents/skills/`, and the commit gate (git pre-commit hook and/or agent hook, CI job).
3. SET in `.dds/tree.dds.md`: `dds_version` (as shipped), `locking` (default `off`; `on` only when several executors share one working copy), and `gate: warn`. Humans start in warn mode.
4. RUN `python .dds/meta/scripts/dds.py check`. The empty skeleton MUST pass before any document is written.

## [2] INVENTORY (TOP-DOWN)

1. **Product:** WRITE two global documents following `dds.product/write.dds.md`: `vision.dds.md` and `constraints.dds.md` (id `product-constraints`, the non-negotiable security/legal/safety rules). SET `status: draft` until a product owner reviews them; `gate: strict` stays unavailable until `product-constraints` is `active`.
2. **Architecture:** WRITE `tech-stack.dds.md` and, if a database exists, `core-database.dds.md` from the actual code and schema, following `dds.architecture/write.dds.md`. SET `status: draft`.
3. **Modules:** LIST the logical features of the codebase (features, NOT files: `login.tsx` + `login.css` + `login.test.ts` are one feature). For each, CREATE `.dds/modules/<domain>/<feature>.dds.md` with `status: draft` and a `sources:` list pointing at the code it governs, using the REVERSE_DOCUMENTATION rules in `dds.modules/update.dds.md` [3].
4. RUN `python .dds/meta/scripts/dds.py check --coverage`. The report lists source directories not matched by any module `sources:` glob. REPEAT step 3 until the team accepts the remaining gaps.

## [3] DRAFT_TO_ACTIVE PROMOTION

1. A human reviews the draft against the real behavior AND against the tier above it (a module draft against its architecture and product documents).
2. FIX the code OR the document so they agree. While the document is `draft`, the code is the reference and the document adapts.
3. SET `status: active`, UPDATE `last_updated`, APPEND a Changelog entry: `- [YYYY-MM-DD]: Promoted from draft after review.`
4. From this moment the document is authoritative for everything under its `sources:`.

## [4] GATE_POLICY

- **AI agents: strict from day one.** An agent MUST NOT change code that no module document's `sources:` covers; it MUST first create a `draft` via [2].3. An agent MUST NOT commit while `check --gate --staged` reports errors; code staged under an `active` document requires that document in the same commit.
- **Humans: `gate: warn`** until the team decides coverage is sufficient, then `gate: strict`. In warn mode the pre-commit hook prints the errors and lets the commit through.
- **`check --sync` (warning only):** lists documents whose `sources:` files changed in the working tree while the document itself did not. Use it to spot drift; it never blocks.

## [5] PRE-FLIGHT_SELF_CORRECTION

1. Did I mark every reverse-documented file `draft`? -> IF NO, fix it. A guess is not an authority.
2. Did I document features, not files? -> IF a document maps 1:1 to a source file, merge it into its feature.
3. Does `python .dds/meta/scripts/dds.py check` pass? -> IF NO, fix the reported errors before continuing.

*Output: EXECUTOR returns `STATUS: ADOPTED` ONLY IF the skeleton passes `check` and every written document is indexed and marked `draft`.*

# END_OF_DIRECTIVE
